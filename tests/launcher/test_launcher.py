"""End-to-end tests of the packaged launcher against a local fake release feed (spec 4 and 7).

Skipped unless running on Windows with dist\\POKKER\\POKKER.exe built (scripts\\package.ps1).
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request

import pytest
from conftest import (
    AVAILABLE,
    DIST,
    NEW_VERSION,
    SKIP_REASON,
    Install,
    NewPackage,
    processes_under,
    sha256_upper,
)

pytestmark = [pytest.mark.launcher, pytest.mark.skipif(not AVAILABLE, reason=SKIP_REASON)]

BOM = b"\xef\xbb\xbf"
CLOSE_AFTER = "--cerrar-tras=4"
PIECES = (
    "app\\VERSION",
    "app\\server\\pokker-server.exe",
    "app\\web\\index.html",
    "app\\update.json",
)


def sha_file(sha: str, bom: bool) -> bytes:
    return (BOM if bom else b"") + sha.encode("ascii")


@pytest.mark.parametrize(
    ("bom", "with_db"),
    [(False, True), (True, True), (False, False)],
    ids=["sha256-plain", "sha256-with-bom", "no-database"],
)
def test_update_without_asking_replaces_app_and_launcher(
    install: Install, new_package: NewPackage, old_version: str, bom: bool, with_db: bool
) -> None:
    install.feed.publish(NEW_VERSION, new_package.zip_path, sha_file(new_package.sha, bom))
    if with_db:
        install.make_database()

    proc = install.start("--permitir-feed-local", "--actualizar-sin-preguntar", CLOSE_AFTER)
    # The relaunched (new) POKKER.exe starts the server: it must report the new version.
    port = install.wait_for(install.running_port, 120, "running.json of the updated POKKER")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=10) as r:
        info = json.loads(r.read())
    assert info["app"] == NEW_VERSION
    assert info["packaged"] is True
    install.wait_all_exited(proc, 120)

    log = install.log()
    assert f"Actualización aplicada: {old_version} -> {NEW_VERSION}" in log
    assert "POKKER.exe nuevo copiado" in log
    assert f"--actualizado={NEW_VERSION}" in log  # the new launcher was started with it
    assert f"Globito: POKKER se actualizó a {NEW_VERSION}" in log
    if with_db:
        assert "Copia de la base en" in log
    else:
        assert "No hay base de datos todavía: no hago copia" in log
    assert log.count("=== POKKER cerrado") == 1  # only the relaunched one ran the server

    assert install.version() == NEW_VERSION
    assert sha256_upper(install.exe) == new_package.exe_sha
    for leftover in ("app.nuevo", "app.viejo", "POKKER.exe.viejo", "POKKER.exe.nuevo"):
        assert not (install.root / leftover).exists(), leftover
    assert not list((install.data / "updates").glob("*")), "the download must be removed"

    backup = install.data / "datos.anterior" / "poker.sqlite3"
    if with_db:
        assert backup.is_file()
        with sqlite3.connect(backup) as db:
            rows = db.execute("SELECT v FROM pokker_test_marker").fetchall()
        db.close()
        assert rows == [("antes de actualizar",)]
        # The live database survived too: the new server migrated it in place.
        with sqlite3.connect(install.data / "poker.sqlite3") as db:
            live = db.execute("SELECT v FROM pokker_test_marker").fetchall()
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
        db.close()
        assert live == [("antes de actualizar",)]
        assert "alembic_version" in tables
    else:
        assert not (install.data / "datos.anterior").exists()

    # Everything is down: no process from this copy, no running.json.
    assert not processes_under(install.base)
    assert not (install.data / "running.json").exists()


def test_update_with_the_real_package_zip(install: Install, old_version: str) -> None:
    """Feeds the launcher the dist\\POKKER-<ver>.zip written by package.ps1 (.NET ZipArchive)."""
    zip_path = DIST.parent / f"POKKER-{old_version}.zip"
    sha_path = DIST.parent / f"POKKER-{old_version}.zip.sha256"
    if not zip_path.is_file() or not sha_path.is_file():
        pytest.skip(f"{zip_path.name} (+ .sha256) not built: run scripts\\package.ps1")
    (install.root / "app" / "VERSION").write_text("0.0.1\n", encoding="utf-8", newline="\n")
    install.feed.publish(old_version, zip_path, sha_path.read_bytes())
    install.make_database()

    proc = install.start("--permitir-feed-local", "--actualizar-sin-preguntar", CLOSE_AFTER)
    port = install.wait_for(install.running_port, 120, "running.json of the updated POKKER")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=10) as r:
        info = json.loads(r.read())
    assert info["app"] == old_version
    install.wait_all_exited(proc, 120)

    log = install.log()
    assert "SHA-256 verificado" in log
    assert f"Actualización aplicada: 0.0.1 -> {old_version}" in log
    assert "POKKER.exe no cambió" in log  # same launcher as dist: no relaunch
    assert install.version() == old_version
    for piece in PIECES:
        assert (install.root / piece).is_file(), piece
    for leftover in ("app.nuevo", "app.viejo", "POKKER.exe.viejo", "POKKER.exe.nuevo"):
        assert not (install.root / leftover).exists(), leftover
    with sqlite3.connect(install.data / "poker.sqlite3") as db:
        rows = db.execute("SELECT v FROM pokker_test_marker").fetchall()
    db.close()
    assert rows == [("antes de actualizar",)]
    assert not processes_under(install.base)


def test_bad_hash_rolls_back_completely(
    install: Install, new_package: NewPackage, old_version: str
) -> None:
    install.feed.publish(NEW_VERSION, new_package.zip_path, sha_file("0" * 64, bom=False))
    install.make_database()
    exe_before = sha256_upper(install.exe)

    install.run("--permitir-feed-local", "--actualizar-sin-preguntar", CLOSE_AFTER)

    log = install.log()
    assert f"/POKKER-{NEW_VERSION}.zip" in install.feed.requests  # it did download
    assert "la descarga está dañada" in log
    assert "Actualización fallida" in log and "vuelta atrás" in log
    assert f"Versión de la app: {old_version}" in log  # kept going with the old one
    assert "POKKER listo en" in log

    assert install.version() == old_version
    assert sha256_upper(install.exe) == exe_before
    for leftover in ("app.nuevo", "app.viejo", "POKKER.exe.viejo", "POKKER.exe.nuevo"):
        assert not (install.root / leftover).exists(), leftover
    assert not list((install.data / "updates").glob("*"))
    assert not (install.data / "datos.anterior").exists()
    assert not processes_under(install.base)


def test_package_without_version_rolls_back_after_unpacking(
    install: Install, package_without_version: NewPackage, old_version: str
) -> None:
    pkg = package_without_version
    install.feed.publish(NEW_VERSION, pkg.zip_path, sha_file(pkg.sha, bom=False))
    install.make_database()
    exe_before = sha256_upper(install.exe)

    install.run("--permitir-feed-local", "--actualizar-sin-preguntar", CLOSE_AFTER)

    log = install.log()
    assert "SHA-256 verificado" in log  # it got past the download and the hash check
    assert "el paquete nuevo no trae app\\VERSION" in log
    assert "Actualización fallida" in log and "vuelta atrás" in log
    assert f"Versión de la app: {old_version}" in log
    assert "POKKER listo en" in log

    assert install.version() == old_version
    assert sha256_upper(install.exe) == exe_before
    for leftover in ("app.nuevo", "app.viejo", "POKKER.exe.viejo", "POKKER.exe.nuevo"):
        assert not (install.root / leftover).exists(), leftover
    assert not list((install.data / "updates").glob("*"))
    assert not (install.data / "datos.anterior").exists()
    assert not processes_under(install.base)


def test_read_only_folder_keeps_old_version(
    install: Install, new_package: NewPackage, old_version: str, deny_write: str
) -> None:
    install.feed.publish(NEW_VERSION, new_package.zip_path, sha_file(new_package.sha, bom=False))

    install.run("--permitir-feed-local", "--actualizar-sin-preguntar", CLOSE_AFTER)

    log = install.log()
    assert "No puedo actualizar" in log
    assert f"Versión de la app: {old_version}" in log
    assert "POKKER listo en" in log
    assert f"/POKKER-{NEW_VERSION}.zip" not in install.feed.requests
    assert install.version() == old_version
    assert not (install.root / "app.nuevo").exists()
    assert not processes_under(install.base)


def test_second_instance_does_not_start_another_server(install: Install) -> None:
    first = install.start("--sin-actualizar", "--cerrar-tras=15")
    install.wait_for(install.running_port, 90, "running.json of the first POKKER")

    second = install.start("--sin-actualizar")
    assert second.wait(30) == 0
    assert "Ya hay un POKKER abierto" in install.log()
    servers = [p for p in processes_under(install.base).values() if p.endswith("pokker-server.exe")]
    assert len(servers) == 1, servers
    assert install.log().count("Servidor lanzado") == 1

    install.wait_all_exited(first, 90)
    assert first.returncode == 0
    assert not (install.data / "running.json").exists()


def test_diagnostics_reports_no_missing_pieces(install: Install, old_version: str) -> None:
    report_file = install.base / "diagnostico.json"
    proc = install.run(f"--diagnostico={report_file}", timeout=60)
    assert proc.returncode == 0
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["faltantes"] == []
    assert report["version"] == old_version
    assert report["app_escribible"] is True
    assert set(report["encontradas"]) == set(PIECES)
    assert not (install.data / "running.json").exists()
