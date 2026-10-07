from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import charts, hands, pushfold, ranges, simulator, solver, stats, system
from app.config import get_settings
from app.db import run_migrations
from app.db.session import _session_factory
from app.solver.worker_registry import start_worker, stop_worker
from app.stats.decisions import backfill_decisions


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if get_settings().auto_migrate:
        run_migrations()
        with _session_factory()() as session:
            backfill_decisions(session)
    start_worker()  # no-op unless POKER_SOLVER_PATH points to an existing binary
    yield
    stop_worker()


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
    app.include_router(solver.router, prefix=settings.api_prefix)

    # Domain and core errors (bad cards, empty ranges, impossible deals) are user input
    # problems: report them as 422 with a readable message.
    @app.exception_handler(ValueError)
    @app.exception_handler(RuntimeError)
    async def _input_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
