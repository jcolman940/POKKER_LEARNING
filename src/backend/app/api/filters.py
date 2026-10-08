from datetime import datetime
from typing import Annotated

from fastapi import Query

from app.stats.engine import StatsFilter


def stats_filter(
    sites: Annotated[list[str] | None, Query()] = None,
    game_types: Annotated[list[str] | None, Query()] = None,
    positions: Annotated[list[str] | None, Query()] = None,
    table_sizes: Annotated[list[int] | None, Query()] = None,
    hand_classes: Annotated[list[str] | None, Query()] = None,
    stack_min: float | None = None,
    stack_max: float | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> StatsFilter:
    return StatsFilter(
        sites=sites or [],
        game_types=game_types or [],
        positions=positions or [],
        table_sizes=table_sizes or [],
        hand_classes=hand_classes or [],
        stack_min=stack_min,
        stack_max=stack_max,
        date_from=date_from,
        date_to=date_to,
    )
