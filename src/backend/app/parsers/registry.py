from __future__ import annotations

from app.parsers.base import HandHistoryParser

_PARSERS: list[HandHistoryParser] = []


def register(parser: HandHistoryParser) -> None:
    if any(p.site == parser.site for p in _PARSERS):
        raise ValueError(f"parser for {parser.site!r} already registered")
    _PARSERS.append(parser)


def unregister(site: str) -> None:
    _PARSERS[:] = [p for p in _PARSERS if p.site != site]


def registered_parsers() -> list[HandHistoryParser]:
    return list(_PARSERS)


def detect_parser(text: str) -> HandHistoryParser | None:
    """First registered parser that recognizes the content."""
    head = text[:20_000]
    return next((p for p in _PARSERS if p.detect(head)), None)
