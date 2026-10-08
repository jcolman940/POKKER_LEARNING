import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    app_control,
    charts,
    hands,
    leaks,
    pushfold,
    ranges,
    simulator,
    solver,
    stats,
    system,
    trainer,
)
from app.config import get_settings
from app.db import run_migrations
from app.db.session import _session_factory
from app.packaged import Heartbeat, Watchdog, install_host_check, mount_web
from app.solver.worker_registry import start_worker, stop_worker, worker_running
from app.stats.decisions import backfill_decisions

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().auto_migrate:
        run_migrations()
        try:
            with _session_factory()() as session:
                backfill_decisions(session)
        except Exception:  # a failed backfill must never keep the app from booting
            logger.exception("Decision backfill failed")
    start_worker()  # no-op unless POKER_SOLVER_PATH points to an existing binary
    watchdog = None
    settings = get_settings()
    if settings.packaged:
        watchdog = Watchdog(
            app.state.heartbeat,
            settings.heartbeat_timeout_s,
            solver_busy=_solver_has_work,
            check_every=getattr(app.state, "watchdog_check_every", 5.0),
        )
        watchdog.start()
    yield
    if watchdog is not None:
        watchdog.stop()
    stop_worker()


def _solver_has_work() -> bool:
    from app.api.app_control import solver_activity

    if not worker_running():  # no solver: queued jobs can never run
        return False
    with _session_factory()() as session:
        busy, pending = solver_activity(session)
    return busy or pending > 0


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system.router, prefix=settings.api_prefix)
    app.include_router(simulator.router, prefix=settings.api_prefix)
    app.include_router(ranges.router, prefix=settings.api_prefix)
    app.include_router(charts.router, prefix=settings.api_prefix)
    app.include_router(pushfold.router, prefix=settings.api_prefix)
    app.include_router(hands.router, prefix=settings.api_prefix)
    app.include_router(stats.router, prefix=settings.api_prefix)
    app.include_router(leaks.router, prefix=settings.api_prefix)
    app.include_router(solver.router, prefix=settings.api_prefix)
    app.include_router(trainer.router, prefix=settings.api_prefix)
    if settings.packaged:
        app.state.heartbeat = Heartbeat()
        app.include_router(app_control.router, prefix=settings.api_prefix)

    # Domain and core errors (bad cards, empty ranges, impossible deals) are user input
    # problems: report them as 422 with a readable message.
    @app.exception_handler(ValueError)
    @app.exception_handler(RuntimeError)
    async def _input_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    # Packaged mode: serve the built frontend on the same port (after every /api route) and
    # only accept loopback Host headers. Added last so the check runs first.
    if settings.packaged:
        if settings.web_dir is not None:
            mount_web(app, settings.web_dir)
        install_host_check(app, settings.port)

    return app


app = create_app()
