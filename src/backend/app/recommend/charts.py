"""Preflop charts: validation, exchange format and matching against a scenario."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PreflopChart
from app.domain.positions import MAX_PLAYERS, MIN_PLAYERS, position_names
from app.domain.scenario import TOURNAMENT_FORMATS, GameFormat, Situation
from app.recommend.preflop_equity import grid_to_text, range_vector

EXCHANGE_FORMAT = "poker-study-ranges"
EXCHANGE_VERSION = 1


class ChartSource(StrEnum):
    POKALAB = "pokalab"
    PREFLOPRANGES = "preflopranges"
    CUSTOM = "custom"
    COMPUTED = "computed"


SOURCE_LABEL = {
    ChartSource.POKALAB: "fuente externa: Pokalab",
    ChartSource.PREFLOPRANGES: "fuente externa: preflopranges.app",
    ChartSource.CUSTOM: "rango propio",
    ChartSource.COMPUTED: "calculado por el sistema",
}

ACTIONS = ("raise", "limp", "call", "3bet", "4bet", "5bet", "allin")
AGGRESSIVE = {"raise", "3bet", "4bet", "5bet", "allin"}


class ChartBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source: ChartSource = ChartSource.CUSTOM
    game_format: GameFormat
    players: int = Field(ge=MIN_PLAYERS, le=MAX_PLAYERS)
    position: str
    vs_position: str | None = None
    stack_bb: float = Field(gt=0)
    situation: Situation
    open_size_bb: float | None = Field(default=None, gt=0)
    rake: str | None = None
    ante_bb: float = Field(default=0.0, ge=0)
    note: str = ""

    @model_validator(mode="after")
    def _positions(self):
        names = position_names(self.players)
        if self.position not in names:
            raise ValueError(f"Posición {self.position} no existe en una mesa de {self.players}")
        if self.vs_position is not None:
            if self.vs_position not in names:
                raise ValueError(
                    f"Posición {self.vs_position} no existe en una mesa de {self.players}"
                )
            if self.vs_position == self.position:
                raise ValueError("La posición rival no puede ser la misma que la propia")
        return self


def _check_actions(actions: dict[str, list[float]]) -> dict[str, list[float]]:
    if not actions:
        raise ValueError("El rango necesita al menos una acción")
    for name, grid in actions.items():
        if name not in ACTIONS:
            raise ValueError(f"Acción desconocida: {name}")
        if len(grid) != 169:
            raise ValueError(f"La acción {name} debe tener 169 valores")
        if any(not 0.0 <= w <= 1.0 for w in grid):
            raise ValueError(f"Las frecuencias de {name} deben estar entre 0 y 1")
    for i in range(169):
        if sum(grid[i] for grid in actions.values()) > 1.0 + 1e-6:
            raise ValueError("Las frecuencias de una mano no pueden sumar más de 100%")
    return actions


class ChartIn(ChartBase):
    actions: dict[str, list[float]]

    _validate_actions = field_validator("actions")(_check_actions)


class ChartOut(ChartIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ExchangeChart(ChartBase):
    """Chart in the exchange file: actions in range notation (PioViewer style weights)."""

    actions: dict[str, str]

    def to_chart_in(self) -> ChartIn:
        grids = {}
        for action, text in self.actions.items():
            try:
                grids[action] = range_vector(normalize_range_text(text)).tolist()
            except ValueError as e:
                raise ValueError(f"Rango inválido en {action}: {e}") from e
        return ChartIn(**self.model_dump(exclude={"actions"}), actions=grids)

    @classmethod
    def from_chart(cls, chart: ChartIn) -> ExchangeChart:
        return cls(
            **chart.model_dump(include=set(ChartBase.model_fields)),
            actions={a: grid_to_text(g) for a, g in chart.actions.items()},
        )


class ExchangeFile(BaseModel):
    format: str = EXCHANGE_FORMAT
    version: int = EXCHANGE_VERSION
    charts: list[ExchangeChart]

    @model_validator(mode="after")
    def _known_format(self):
        if self.format != EXCHANGE_FORMAT:
            raise ValueError("El archivo no es un set de rangos de Poker Study")
        if self.version > EXCHANGE_VERSION:
            raise ValueError("El archivo es de una versión más nueva de la app")
        return self


def normalize_range_text(text: str) -> str:
    """Accepts PioViewer / ProPokerTools .txt files: one or many lines, comma separated."""
    return ",".join(part for part in text.replace("\r", "\n").replace("\n", ",").split(","))


# ---- Matching -------------------------------------------------------------------


@dataclass(frozen=True)
class ChartQuery:
    game_format: GameFormat
    players: int
    position: str
    situation: Situation
    stack_bb: float
    vs_position: str | None = None
    ante_bb: float = 0.0


@dataclass(frozen=True)
class ChartMatch:
    chart: PreflopChart
    exact: bool
    mismatches: list[str]


FORMAT_LABEL = {
    GameFormat.CASH: "cash",
    GameFormat.MTT: "MTT",
    GameFormat.SNG: "SNG",
    GameFormat.SPIN: "Spin & Go",
}


def _distance(chart: PreflopChart, q: ChartQuery) -> tuple[float, list[str]]:
    cost = 0.0
    notes: list[str] = []
    fmt = GameFormat(chart.game_format)
    if fmt != q.game_format:
        same_family = (fmt in TOURNAMENT_FORMATS) == (q.game_format in TOURNAMENT_FORMATS)
        cost += 1.0 if same_family else 4.0
        notes.append(
            f"Formato del rango: {FORMAT_LABEL[fmt]} (escenario: {FORMAT_LABEL[q.game_format]})"
        )
    if chart.players != q.players:
        cost += abs(chart.players - q.players) * 0.5
        notes.append(f"Mesa del rango: {chart.players} jugadores (escenario: {q.players})")
    ratio = abs(math.log(chart.stack_bb / q.stack_bb)) if q.stack_bb > 0 else 10.0
    if ratio > math.log(1.1):  # more than ~10% apart
        cost += 3.0 * ratio
        notes.append(f"Stack del rango: {chart.stack_bb:g}bb (escenario: {q.stack_bb:g}bb)")
    if (chart.ante_bb > 0) != (q.ante_bb > 0):
        cost += 1.0
        notes.append(f"Ante del rango: {chart.ante_bb:g}bb (escenario: {q.ante_bb:g}bb)")
    if q.vs_position and chart.vs_position and chart.vs_position != q.vs_position:
        cost += 2.0
        notes.append(f"Rival del rango: {chart.vs_position} (escenario: {q.vs_position})")
    return cost, notes


def find_chart(session: Session, q: ChartQuery) -> ChartMatch | None:
    """Best chart for the spot. Situation and hero position must match; everything
    else (format, table size, stack, ante, rival position) is scored by distance."""
    candidates = session.scalars(
        select(PreflopChart).where(
            PreflopChart.situation == q.situation, PreflopChart.position == q.position
        )
    ).all()
    if not candidates:
        return None
    scored = [(_distance(c, q), c.id, c) for c in candidates]
    (_, notes), _, best = min(scored, key=lambda x: (x[0][0], x[1]))
    return ChartMatch(chart=best, exact=not notes, mismatches=notes)
