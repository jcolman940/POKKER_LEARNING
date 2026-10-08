from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import PreflopChart
from app.recommend.charts import (
    ChartIn,
    ChartOut,
    ChartSource,
    ExchangeChart,
    ExchangeFile,
)

router = APIRouter(prefix="/charts", tags=["charts"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get(session: Session, chart_id: int) -> PreflopChart:
    chart = session.get(PreflopChart, chart_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="Rango no encontrado")
    return chart


@router.get("", response_model=list[ChartOut])
def list_charts(session: SessionDep) -> list[PreflopChart]:
    return list(
        session.scalars(
            select(PreflopChart).order_by(
                PreflopChart.game_format,
                PreflopChart.players,
                PreflopChart.situation,
                PreflopChart.position,
                PreflopChart.stack_bb,
            )
        )
    )


@router.post("", response_model=ChartOut, status_code=201)
def create_chart(body: ChartIn, session: SessionDep) -> PreflopChart:
    chart = PreflopChart(**body.model_dump(mode="json"))
    session.add(chart)
    session.commit()
    return chart


class ImportResult(BaseModel):
    created: int
    errors: list[str]


@router.post("/import", response_model=ImportResult)
def import_charts(body: ExchangeFile, session: SessionDep) -> ImportResult:
    created, errors = 0, []
    for i, item in enumerate(body.charts, start=1):
        try:
            chart_in = item.to_chart_in()
        except ValueError as e:
            errors.append(f"Rango {i} ({item.name}): {e}")
            continue
        session.add(PreflopChart(**chart_in.model_dump(mode="json")))
        created += 1
    session.commit()
    return ImportResult(created=created, errors=errors)


@router.get("/export", response_model=ExchangeFile)
def export_charts(
    session: SessionDep,
    source: Annotated[list[ChartSource] | None, Query()] = None,
) -> ExchangeFile:
    stmt = select(PreflopChart).order_by(PreflopChart.id)
    if source:
        stmt = stmt.where(PreflopChart.source.in_([s.value for s in source]))
    charts = [ChartIn.model_validate(c, from_attributes=True) for c in session.scalars(stmt)]
    return ExchangeFile(charts=[ExchangeChart.from_chart(c) for c in charts])


@router.get("/{chart_id}", response_model=ChartOut)
def get_chart(chart_id: int, session: SessionDep) -> PreflopChart:
    return _get(session, chart_id)


@router.put("/{chart_id}", response_model=ChartOut)
def update_chart(chart_id: int, body: ChartIn, session: SessionDep) -> PreflopChart:
    chart = _get(session, chart_id)
    for key, value in body.model_dump(mode="json").items():
        setattr(chart, key, value)
    session.commit()
    return chart


@router.delete("/{chart_id}", status_code=204)
def delete_chart(chart_id: int, session: SessionDep) -> Response:
    session.delete(_get(session, chart_id))
    session.commit()
    return Response(status_code=204)
