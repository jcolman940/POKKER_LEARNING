from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.hand import HandRecord


@dataclass(frozen=True)
class RawHand:
    text: str
    start_line: int  # 1-based line of the hand's first line in its file


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
