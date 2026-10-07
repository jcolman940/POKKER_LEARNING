"""Harness for the end-to-end tests of the packaged launcher (spec section 7).

Runs the real dist\\POKKER\\POKKER.exe built by scripts\\package.ps1 against a local fake
release feed (http.server on 127.0.0.1, random port). Every test works on its own copy of
dist\\POKKER and its own --datos folder; nothing touches %LOCALAPPDATA%\\POKKER.

Run from backend\\: uv run pytest -q ../tests/launcher   (or scripts\\test.ps1 launcher)
"""

from __future__ import annotations

import ctypes
import getpass
import hashlib
import http.server
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST = REPO_ROOT / "dist" / "POKKER"
DIST_EXE = DIST / "POKKER.exe"
NEW_VERSION = "9.9.9"
T = TypeVar("T")

AVAILABLE = sys.platform == "win32" and DIST_EXE.is_file()
SKIP_REASON = (
    "needs Windows and a built package (dist\\POKKER\\POKKER.exe): run scripts\\package.ps1"
)


def pytest_configure(config: pytest.Config) -> None:
    # Also registered in backend/pyproject.toml; repeated here because pytest may pick another
    # rootdir/configfile when it is given ../tests/launcher.
    config.addinivalue_line("markers", "launcher: end-to-end tests of the packaged POKKER.exe")


# ---------------------------------------------------------------------------------- processes


def _image_paths() -> dict[int, str]:
    """pid -> full image path of every process we may query (ctypes; no psutil needed)."""
    psapi = ctypes.WinDLL("psapi")
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.OpenProcess.restype = ctypes.c_void_p
    count = 4096
    while True:
        pids = (ctypes.c_uint32 * count)()
        needed = ctypes.c_uint32()
        if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed)):
            raise OSError("EnumProcesses failed")
        if needed.value < ctypes.sizeof(pids):
            break
        count *= 2
    result: dict[int, str] = {}
    buf = ctypes.create_unicode_buffer(32768)
    for pid in pids[: needed.value // ctypes.sizeof(ctypes.c_uint32)]:
        if pid == 0:
            continue
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            continue
        try:
            size = ctypes.c_uint32(len(buf))
            if kernel32.QueryFullProcessImageNameW(
                ctypes.c_void_p(handle), 0, buf, ctypes.byref(size)
            ):
                result[pid] = buf.value
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    return result


def processes_under(root: Path) -> dict[int, str]:
    """POKKER.exe / pokker-server.exe processes whose executable lives under root."""
    prefix = str(root.resolve()).lower().rstrip("\\") + "\\"
    return {
        pid: path
        for pid, path in _image_paths().items()
        if path.lower().startswith(prefix)
        and Path(path).name.lower() in ("pokker.exe", "pokker-server.exe")
    }


def kill_under(root: Path) -> list[str]:
    """taskkill /T /F every POKKER process under root; returns what was still alive."""
    alive = processes_under(root)
    for pid in alive:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
    if alive:
        deadline = time.monotonic() + 10
        while processes_under(root) and time.monotonic() < deadline:
            time.sleep(0.2)
    return [f"{Path(p).name} ({pid})" for pid, p in alive.items()]


def foreign_launchers(base: Path) -> list[str]:
    prefix = str(base.resolve()).lower()
    return [
        f"{path} ({pid})"
        for pid, path in _image_paths().items()
        if Path(path).name.lower() == "pokker.exe" and not path.lower().startswith(prefix)
    ]


# ---------------------------------------------------------------------------------- feed


class _Handler(http.server.BaseHTTPRequestHandler):
    server: _FeedHTTPServer

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        feed = self.server.feed
        path = self.path.split("?", 1)[0]
        feed.requests.append(path)
        body = feed.routes.get(path)
        if body is None:
            self.send_error(404)
            return
        if isinstance(body, Path):
            size = body.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with body.open("rb") as f:
                shutil.copyfileobj(f, self.wfile, 1024 * 1024)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


class _FeedHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    feed: Feed


@dataclass
class Feed:
    """GitHub-like releases/latest feed plus the release files, on 127.0.0.1:<random>."""

    routes: dict[str, bytes | Path] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)

    def start(self) -> None:
        self._httpd = _FeedHTTPServer(("127.0.0.1", 0), _Handler)
        self._httpd.feed = self
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(10)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    @property
    def url(self) -> str:
        return self.base + "/releases/latest"

    def publish(self, version: str, zip_path: Path, sha_file: bytes) -> None:
        name = f"POKKER-{version}.zip"
        self.routes[f"/{name}"] = zip_path
        self.routes[f"/{name}.sha256"] = sha_file
        release = {
            "tag_name": f"v{version}",
            "body": f"Novedades de la {version} (feed local de pruebas).",
            "html_url": f"{self.base}/releases",
            "assets": [
                {
                    "name": name,
                    "browser_download_url": f"{self.base}/{name}",
                    "size": zip_path.stat().st_size,
                },
                {
                    "name": f"{name}.sha256",
                    "browser_download_url": f"{self.base}/{name}.sha256",
                    "size": len(sha_file),
                },
            ],
        }
        self.routes["/releases/latest"] = json.dumps(release).encode()


# ---------------------------------------------------------------------------------- packages


def sha256_upper(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


@dataclass(frozen=True)
class NewPackage:
    zip_path: Path
    sha: str  # uppercase hex
    exe_sha: str  # SHA-256 of the POKKER.exe inside the zip (differs from dist's)


@pytest.fixture(scope="session")
def old_version() -> str:
    return (DIST / "app" / "VERSION").read_text(encoding="utf-8").strip()


@pytest.fixture(scope="session")
def new_package(tmp_path_factory: pytest.TempPathFactory) -> NewPackage:
    """dist\\POKKER as version 9.9.9, zipped like package.ps1 ('/' names under POKKER/).

    Its POKKER.exe gets a few trailing bytes (ignored by the PE loader) so the update also
    exercises the "new launcher" path: POKKER.exe -> POKKER.exe.viejo + relaunch.
    """
    staging = tmp_path_factory.mktemp("nuevo") / "POKKER"
    shutil.copytree(DIST, staging)
    (staging / "app" / "VERSION").write_text(NEW_VERSION + "\n", encoding="utf-8", newline="\n")
    with (staging / "POKKER.exe").open("ab") as f:
        f.write(b"\0POKKER-test-9.9.9\0")
    zip_path = staging.parent / f"POKKER-{NEW_VERSION}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for file in sorted(p for p in staging.rglob("*") if p.is_file()):
            zf.write(file, "POKKER/" + file.relative_to(staging).as_posix())
    return NewPackage(zip_path, sha256_upper(zip_path), sha256_upper(staging / "POKKER.exe"))


# ---------------------------------------------------------------------------------- installs


@dataclass
class Install:
    """A private copy of dist\\POKKER (root) with its own data folder and feed."""

    base: Path
    root: Path
    data: Path
    feed: Feed

    @property
    def exe(self) -> Path:
        return self.root / "POKKER.exe"

    @property
    def log_file(self) -> Path:
        return self.data / "pokker.log"

    def log(self) -> str:
        if not self.log_file.exists():
            return ""
        return self.log_file.read_text(encoding="utf-8", errors="replace")

    def version(self) -> str:
        return (self.root / "app" / "VERSION").read_text(encoding="utf-8").strip()

    def args(self, *extra: str) -> list[str]:
        return [str(self.exe), "--sin-navegador", f"--datos={self.data}", *extra]

    def start(self, *extra: str) -> subprocess.Popen[bytes]:
        return subprocess.Popen(self.args(*extra), cwd=self.base)

    def wait_all_exited(self, proc: subprocess.Popen[bytes], timeout: float) -> None:
        """Waits for proc and for every POKKER process under root (a relaunched launcher too)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None and not processes_under(self.root):
                return
            time.sleep(0.25)
        raise AssertionError(
            f"POKKER did not finish in {timeout:.0f} s; alive: {processes_under(self.root)}\n"
            f"--- pokker.log ---\n{self.log()[-4000:]}"
        )

    def run(self, *extra: str, timeout: float = 180) -> subprocess.Popen[bytes]:
        proc = self.start(*extra)
        self.wait_all_exited(proc, timeout)
        return proc

    def wait_for(self, predicate: Callable[[], T | None], timeout: float, what: str) -> T:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(
            f"timed out waiting for {what}\n--- pokker.log ---\n{self.log()[-4000:]}"
        )

    def running_port(self) -> int | None:
        try:
            info = json.loads((self.data / "running.json").read_text(encoding="utf-8-sig"))
            return int(info["port"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def make_database(self) -> None:
        """A real SQLite file with a marker table (the server migrates it alongside)."""
        self.data.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.data / "poker.sqlite3") as db:
            db.execute("CREATE TABLE pokker_test_marker (v TEXT)")
            db.execute("INSERT INTO pokker_test_marker VALUES ('antes de actualizar')")
        db.close()


@pytest.fixture(scope="session", autouse=True)
def _no_foreign_pokker(tmp_path_factory: pytest.TempPathFactory) -> None:
    if not AVAILABLE:
        return
    base = tmp_path_factory.getbasetemp()
    others = foreign_launchers(base)
    if others:
        pytest.fail(
            "another POKKER.exe is running (it owns the Local\\POKKER mutex); close it first: "
            + ", ".join(others)
        )


@pytest.fixture
def install(tmp_path: Path) -> Iterator[Install]:
    """tmp/v1 = copy of dist\\POKKER whose update.json points at a local feed (started)."""
    root = tmp_path / "v1"
    shutil.copytree(DIST, root)
    feed = Feed()
    feed.start()
    (root / "app" / "update.json").write_text(
        json.dumps({"feed": feed.url}), encoding="utf-8", newline="\n"
    )
    inst = Install(base=tmp_path, root=root, data=tmp_path / "datos", feed=feed)
    try:
        yield inst
    finally:
        try:
            killed = kill_under(tmp_path)
            if killed:
                print(f"teardown: killed {', '.join(killed)}")
        finally:
            feed.stop()


@pytest.fixture
def deny_write(install: Install) -> Iterator[str]:
    """Denies write on tmp/v1 to the current user with icacls; restored on teardown.

    Only the data-write rights (WD,AD,WEA,WA): the generic (W) also denies SYNCHRONIZE, and
    then Windows refuses to start POKKER.exe from that folder at all ("Access is denied").
    """
    user = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    account = f"{domain}\\{user}" if domain else user
    target = str(install.root)
    res = subprocess.run(
        ["icacls", target, "/deny", f"{account}:(OI)(CI)(WD,AD,WEA,WA)"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        pytest.skip(f"icacls /deny is not possible here: {res.stdout.strip()} {res.stderr.strip()}")
    try:
        yield account
    finally:
        kill_under(install.base)  # before restoring: nothing may hold the folder
        subprocess.run(
            ["icacls", target, "/remove:d", account, "/T", "/C", "/Q"],
            capture_output=True,
            check=False,
        )
