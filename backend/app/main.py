from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import system
from app.config import get_settings
from app.db import run_migrations


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if get_settings().auto_migrate:
        run_migrations()
    yield


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
    return app


app = create_app()
