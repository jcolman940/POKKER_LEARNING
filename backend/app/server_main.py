"""Entry point of the packaged executable: one uvicorn server on loopback."""

from __future__ import annotations

import sys

import uvicorn

from app.config import get_settings
from app.main import create_app
from app.packaged import set_shutdown_callback


def main() -> int:
    settings = get_settings()
    if settings.host != "127.0.0.1":
        print(f"Host no permitido: {settings.host} (solo 127.0.0.1)", file=sys.stderr)
        return 2
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=settings.host,
            port=settings.port,
            log_config=None,
            access_log=False,
        )
    )

    def _stop() -> None:
        server.should_exit = True

    set_shutdown_callback(_stop)
    try:
        server.run()
    finally:
        set_shutdown_callback(None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
