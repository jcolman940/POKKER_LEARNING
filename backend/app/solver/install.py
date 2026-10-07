"""Download and install TexasSolver (AGPL, never bundled) into ``<data_dir>/tools``."""

from __future__ import annotations

import hashlib
import shutil
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings

TEXASSOLVER_URL = (
    "https://github.com/bupticybee/TexasSolver/releases/download/v0.2.0/"
    "TexasSolver-v0.2.0-Windows.zip"
)
TEXASSOLVER_SHA256 = "0A9122FA0CD9384E6C1CBE0492E8A3B8AC7809890C649E1A53F77A59D6D50A7C"
TOOLS_SUBDIR = "tools/TexasSolver"
EXE_RELATIVE = "TexasSolver-v0.2.0-Windows/console_solver.exe"
CHUNK = 64 * 1024

ERR_DOWNLOAD = "No se pudo descargar TexasSolver (sin conexión o GitHub no respondió)."
ERR_HASH = "La descarga no coincide con el archivo oficial (hash distinto); no se instaló."
ERR_EXTRACT = "No se pudo descomprimir TexasSolver: "

_RUNNING = ("downloading", "verifying", "extracting")


def detected_solver_path(settings: Settings) -> Path | None:
    """The configured solver if it exists, else the one installed from the app."""
    if settings.solver_path is not None and settings.solver_path.is_file():
        return settings.solver_path
    installed = settings.data_dir / TOOLS_SUBDIR / EXE_RELATIVE
    return installed if installed.is_file() else None


@dataclass(frozen=True)
class InstallStatus:
    state: str = "idle"  # idle | downloading | verifying | extracting | done | error
    bytes: int = 0
    total: int | None = None
    error: str | None = None


class _InstallError(Exception):
    pass


class Installer:
    _instance: Installer | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = InstallStatus()

    @classmethod
    def get(cls) -> Installer:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._instance_lock:
            cls._instance = None

    def status(self) -> InstallStatus:
        with self._lock:
            return self._status

    def _set(self, **changes) -> None:
        with self._lock:
            self._status = InstallStatus(**{**self._status.__dict__, **changes})

    def start(self, url: str | None = None, sha256: str | None = None) -> InstallStatus:
        url = url or TEXASSOLVER_URL
        sha256 = sha256 or TEXASSOLVER_SHA256
        with self._lock:
            if self._status.state in _RUNNING:
                return self._status
            self._status = InstallStatus(state="downloading")
            current = self._status
        threading.Thread(target=self._run, args=(url, sha256), daemon=True).start()
        return current

    def _run(self, url: str, sha256: str) -> None:
        tools = get_settings().data_dir / "tools"
        tmp = tools / ".tmp"
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            archive = tmp / "TexasSolver.zip"
            self._download(url, archive)
            self._set(state="verifying")
            if _sha256_of(archive).lower() != sha256.lower():
                raise _InstallError(ERR_HASH)
            self._set(state="extracting")
            extract = tmp / "extract"
            try:
                _safe_extract(archive, extract)
            except (zipfile.BadZipFile, OSError, ValueError) as exc:
                raise _InstallError(ERR_EXTRACT + str(exc)) from exc
            target = tools / "TexasSolver"
            shutil.rmtree(target, ignore_errors=True)
            extract.rename(target)
        except _InstallError as exc:
            error = str(exc)
        except Exception as exc:  # unexpected: still report it in Spanish, never crash silently
            error = ERR_EXTRACT + str(exc)
        else:
            error = None
        shutil.rmtree(tmp, ignore_errors=True)
        if error is not None:
            self._set(state="error", error=error)
            return
        self._set(state="done")
        from app.solver.worker_registry import start_worker

        start_worker()

    def _download(self, url: str, dest: Path) -> None:
        try:
            with urllib.request.urlopen(url, timeout=30) as resp, dest.open("wb") as out:  # noqa: S310
                length = resp.headers.get("Content-Length")
                self._set(total=int(length) if length and length.isdigit() else None)
                done = 0
                while chunk := resp.read(CHUNK):
                    out.write(chunk)
                    done += len(chunk)
                    self._set(bytes=done)
        except (OSError, ValueError) as exc:  # URLError/HTTPError/timeouts are OSError
            raise _InstallError(ERR_DOWNLOAD) from exc


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            if not (root / member.filename).resolve().is_relative_to(root):
                raise ValueError(f"entrada insegura en el zip: {member.filename}")
        zf.extractall(dest)
