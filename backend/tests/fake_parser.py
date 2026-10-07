"""Test-only room: each hand is a HandRecord as JSON after a "#FAKE-HAND" line.

It exists to exercise the import pipeline (detection, splitting, errors,
deduplication, zip handling) without inventing any real room's format.
"""

from __future__ import annotations

import json
import re

from app.domain.hand import HandRecord
from app.parsers import HandHistoryParser, ParseError, RawHand
from app.parsers.base import split_on

HEADER = re.compile(r"^#FAKE-HAND\b")


class FakeParser(HandHistoryParser):
    site = "fake"
    label = "Sala de prueba"

    def detect(self, text: str) -> bool:
        return text.lstrip().startswith("#FAKE-HAND")

    def split(self, text: str) -> list[RawHand]:
        return split_on(HEADER, text)

    def parse(self, raw: RawHand) -> HandRecord:
        body = raw.text.split("\n", 1)[1] if "\n" in raw.text else ""
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise ParseError(f"JSON inválido: {e.msg}", line=e.lineno + 1) from e
        return HandRecord.model_validate(data)


def fake_file(*records: HandRecord | str) -> bytes:
    parts = []
    for r in records:
        body = r if isinstance(r, str) else r.model_dump_json(indent=1)
        parts.append(f"#FAKE-HAND\n{body}\n")
    return "\n".join(parts).encode()
