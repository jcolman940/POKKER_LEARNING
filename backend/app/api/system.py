from typing import Annotated

import pokercore
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session

router = APIRouter(tags=["system"])


class VersionInfo(BaseModel):
    app: str
    core: str


class HealthInfo(BaseModel):
    status: str
    database: bool


@router.get("/version", response_model=VersionInfo)
def version(settings: Annotated[Settings, Depends(get_settings)]) -> VersionInfo:
    return VersionInfo(app=settings.app_version, core=pokercore.version())


@router.get("/health", response_model=HealthInfo)
def health(session: Annotated[Session, Depends(get_session)]) -> HealthInfo:
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return HealthInfo(status="ok" if db_ok else "degraded", database=db_ok)
