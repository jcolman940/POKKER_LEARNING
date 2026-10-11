from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.domain.hand import HandRecord
from app.domain.scenario import GameFormat


@dataclass(frozen=True)
class RawHand:
    text: str
    start_line: int  # 1-based line of the hand's first line in its file


@dataclass(frozen=True)
class TournamentSummary:
    """Hero's result in one tournament, from a room's tournament summary file."""

    site: str
    tournament_id: str
    game_type: GameFormat
    played_at: datetime
    buy_in: float  # prize pool part
    fee: float
    prize: float
    finish: int | None
    entrants: int | None
    currency: str | None


class ParseError(ValueError):
    """A hand could not be parsed. `line` is relative to the hand (1 = first line)."""

    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


class HandHistoryParser(ABC):
    """Interface every room parser implements."""

    site: str  # stable id stored with each hand, e.g. "pokerstars"
    label: str  # name shown in the UI

    @abstractmethod
    def detect(self, text: str) -> bool:
        """True when the file content belongs to this room."""

    @abstractmethod
    def split(self, text: str) -> list[RawHand]:
        """Splits a file into hands, keeping each hand's starting line."""

    @abstractmethod
    def parse(self, raw: RawHand) -> HandRecord:
        """Parses one hand. Raises ParseError (or ValueError) when it cannot."""

    def parse_summary(self, text: str) -> TournamentSummary | None:
        """Reads a tournament summary file. None when the text is not one;
        ParseError when it is one but cannot be read. Rooms without summaries
        keep this default."""
        return None


def split_on(pattern: re.Pattern[str], text: str) -> list[RawHand]:
    """Splits text at every line matching `pattern` (the first line of each hand)."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if pattern.match(line)]
    hands = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            hands.append(RawHand(text=body, start_line=start + 1))
    return hands
