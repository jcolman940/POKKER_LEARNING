from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.stats import FilterDep
from app.db import get_session
from app.leaks.finder import LeakDetail, LeakReport, find_leaks, leak_detail

router = APIRouter(prefix="/leaks", tags=["leaks"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=LeakReport)
def leaks(session: SessionDep, filters: FilterDep) -> LeakReport:
    return find_leaks(session, filters)


@router.get("/detail", response_model=LeakDetail)
def detail(session: SessionDep, filters: FilterDep, key: str) -> LeakDetail:
    result = leak_detail(session, filters, key)
    if result is None:
        raise HTTPException(status_code=404, detail="Ese leak no existe con los filtros actuales")
    return result
