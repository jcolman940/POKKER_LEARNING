"""Packaged-mode support: heartbeat, idle watchdog, shutdown hook, Host check, SPA serving."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})

_shutdown_callback: Callable[[], None] | None = None


def set_shutdown_callback(fn: Callable[[], None] | None) -> None:
    """Register what ``request_shutdown`` does (server_main: ``server.should_exit = True``)."""
    global _shutdown_callback
    _shutdown_callback = fn


def request_shutdown() -> None:
    if _shutdown_callback is None:
        logger.warning("Shutdown requested but no callback is registered")
        return
    _shutdown_callback()


class Heartbeat:
    """Last time the frontend said it is alive (monotonic clock)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._last: float | None = None

    def beat(self) -> None:
        self._last = self._clock()

    def age(self) -> float | None:
        """Seconds since the last beat, or None before the first one."""
        if self._last is None:
            return None
        return self._clock() - self._last


class Watchdog:
    """Shuts the server down once heartbeats stop and the solver has nothing to do."""

    def __init__(
        self,
        heartbeat: Heartbeat,
        timeout_s: float,
        solver_busy: Callable[[], bool],
        check_every: float = 5.0,
        on_timeout: Callable[[], None] | None = None,
    ) -> None:
        self._heartbeat = heartbeat
        self._timeout_s = timeout_s
        self._solver_busy = solver_busy
        self._check_every = check_every
        self._on_timeout = on_timeout or request_shutdown
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check(self) -> bool:
        """Evaluate once; returns True (and fires the shutdown) when the app is abandoned."""
        age = self._heartbeat.age()
        if age is None or age <= self._timeout_s:
            return False
        try:
            if self._solver_busy():
                return False
        except Exception:  # an unreadable queue must never kill the app by itself
            logger.exception("Watchdog could not read the solver queue")
            return False
        logger.info("No heartbeat for %.0fs and no solver work: shutting down", age)
        self._on_timeout()
        return True

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="heartbeat-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.wait(self._check_every):
            if self.check():
                return


def host_allowed(host_header: str | None) -> bool:
    if not host_header:
        return False
    host = host_header.rsplit(":", 1)[0] if ":" in host_header else host_header
    return host.lower() in ALLOWED_HOSTS


def install_host_check(app: FastAPI) -> None:
    @app.middleware("http")
    async def _host_check(request: Request, call_next):
        if not host_allowed(request.headers.get("host")):
            return JSONResponse(status_code=400, content={"detail": "Host no permitido"})
        return await call_next(request)


class SpaStaticFiles(StaticFiles):
    """Static files with an index.html fallback for client-side routes (not /api, not files)."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            parts = path.replace("\\", "/").strip("/").split("/")  # Windows gives backslashes
            first, last = parts[0], parts[-1]
            if first == "api" or "." in last:
                raise
            return await super().get_response("index.html", scope)


def mount_web(app: FastAPI, web_dir: Path) -> None:
    app.mount("/", SpaStaticFiles(directory=web_dir, html=True), name="web")
