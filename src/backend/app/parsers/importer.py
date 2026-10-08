"""Importing hand history files (.txt or .zip) into the database.

- Each file is matched to a room parser by content.
- Import is idempotent: hands are deduplicated by (site, hand_id), against the
  database and within the same batch.
- A hand that fails to parse never aborts the batch: it is listed in the report
  with its file, position and line.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Hand, ImportBatch, TournamentResult
from app.domain.hand import HandRecord
from app.parsers.base import ParseError, RawHand
from app.parsers.registry import detect_parser
from app.stats.decisions import decision_rows
from app.stats.facts import hero_facts

MAX_ZIP_MEMBERS = 20_000
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024  # 1 GiB per import
MAX_ERRORS_IN_REPORT = 500


@dataclass
class ImportIssue:
    file: str
    message: str
    hand: int | None = None  # 1-based position of the hand in the file
    line: int | None = None  # 1-based line in the file
    excerpt: str | None = None


@dataclass
class FileReport:
    name: str
    site: str | None = None
    hands: int = 0
    imported: int = 0
    duplicates: int = 0
    failed: int = 0


@dataclass
class ImportReport:
    files: list[FileReport] = field(default_factory=list)
    errors: list[ImportIssue] = field(default_factory=list)
    errors_truncated: bool = False

    @property
    def totals(self) -> dict[str, int]:
        return {
            "files": len(self.files),
            "hands_found": sum(f.hands for f in self.files),
            "imported": sum(f.imported for f in self.files),
            "duplicates": sum(f.duplicates for f in self.files),
            "failed": sum(f.failed for f in self.files),
        }

    def add_error(self, error: ImportIssue) -> None:
        if len(self.errors) < MAX_ERRORS_IN_REPORT:
            self.errors.append(error)
        else:
            self.errors_truncated = True


def decode(data: bytes) -> str:
    """Hand histories come as UTF-8 (with or without BOM), UTF-16 or Windows-1252."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def expand_files(files: list[tuple[str, bytes]], report: ImportReport) -> list[tuple[str, str]]:
    """Turns uploads into (name, text) pairs, opening .zip archives."""
    out: list[tuple[str, str]] = []
    total = 0
    for name, data in files:
        if not name.lower().endswith(".zip"):
            out.append((name, decode(data)))
            continue
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            report.add_error(ImportIssue(file=name, message="El .zip está dañado o no es un zip"))
            continue
        with archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            if len(members) > MAX_ZIP_MEMBERS:
                report.add_error(
                    ImportIssue(file=name, message="El .zip tiene demasiados archivos")
                )
                continue
            for member in members:
                inner = f"{name}/{member.filename}"
                if member.filename.startswith("__MACOSX/") or not member.filename.lower().endswith(
                    ".txt"
                ):
                    continue
                total += member.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    report.add_error(
                        ImportIssue(file=inner, message="El .zip descomprimido es demasiado grande")
                    )
                    return out
                out.append((inner, decode(archive.read(member))))
    return out


def _resolve_hero(record: HandRecord) -> HandRecord:
    """Rooms usually name the hero ("Dealt to ..."). If not, use the configured names."""
    if record.hero is not None:
        return record
    names = set(get_settings().hero_names)
    match = next((s.name for s in record.seats if s.name in names), None)
    return record.model_copy(update={"hero": match}) if match else record


def _excerpt(raw: RawHand, line: int | None) -> str:
    lines = raw.text.splitlines()
    index = (line - 1) if line and 0 < line <= len(lines) else 0
    return lines[index][:200] if lines else ""


def hand_row(record: HandRecord, raw_text: str, import_id: int | None) -> Hand:
    facts = hero_facts(record)
    row = Hand(
        site=record.site,
        hand_id=record.hand_id,
        played_at=record.played_at,
        game_type=record.game_type.value,
        tournament_id=record.tournament.tournament_id if record.tournament else None,
        bb=record.bb,
        import_id=import_id,
        record=record.model_dump(mode="json"),
        raw_text=raw_text,
        has_hero=int(facts is not None),
        hero=record.hero,
        hero_cards=record.hero_cards,
    )
    if facts is not None:
        for key, value in facts.as_dict().items():
            setattr(row, key, value)
    row.decisions = decision_rows(record)
    return row


def _tournament_result(session: Session, record: HandRecord) -> None:
    t = record.tournament
    if t is None or t.finish is None or t.buy_in is None:
        return
    existing = session.scalar(
        select(TournamentResult).where(
            TournamentResult.site == record.site, TournamentResult.tournament_id == t.tournament_id
        )
    )
    values = dict(
        game_type=record.game_type.value,
        played_at=record.played_at,
        buy_in=t.buy_in,
        fee=t.fee or 0.0,
        prize=t.prize or 0.0,
        finish=t.finish,
        currency=t.currency,
    )
    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
    else:
        session.add(TournamentResult(site=record.site, tournament_id=t.tournament_id, **values))


def import_files(
    session: Session, files: list[tuple[str, bytes]]
) -> tuple[ImportBatch, ImportReport]:
    report = ImportReport()
    batch = ImportBatch()
    session.add(batch)
    session.flush()

    seen: set[tuple[str, str]] = set()
    for name, text in expand_files(files, report):
        file_report = FileReport(name=name)
        report.files.append(file_report)
        parser = detect_parser(text)
        if parser is None:
            report.add_error(
                ImportIssue(file=name, message="No se reconoce la sala o el formato del archivo")
            )
            continue
        file_report.site = parser.site

        raws = parser.split(text)
        file_report.hands = len(raws)
        parsed: list[tuple[RawHand, HandRecord]] = []
        for index, raw in enumerate(raws, start=1):
            try:
                parsed.append((raw, _resolve_hero(parser.parse(raw))))
            except (ParseError, ValidationError, ValueError) as e:
                file_report.failed += 1
                line = getattr(e, "line", None)
                report.add_error(
                    ImportIssue(
                        file=name,
                        hand=index,
                        line=raw.start_line + (line - 1 if line else 0),
                        message=str(e).splitlines()[0][:300],
                        excerpt=_excerpt(raw, line),
                    )
                )

        keys = [(r.site, r.hand_id) for _, r in parsed]
        existing: set[tuple[str, str]] = set()
        for start in range(0, len(keys), 500):
            chunk = keys[start : start + 500]
            existing |= set(
                session.execute(
                    select(Hand.site, Hand.hand_id).where(
                        tuple_(Hand.site, Hand.hand_id).in_(chunk)
                    )
                ).all()
            )

        for index, (raw, record) in enumerate(parsed, start=1):
            key = (record.site, record.hand_id)
            if key in existing or key in seen:
                file_report.duplicates += 1
                continue
            try:
                row = hand_row(record, raw.text, batch.id)
            except ValueError as e:
                file_report.failed += 1
                report.add_error(
                    ImportIssue(
                        file=name,
                        hand=index,
                        line=raw.start_line,
                        message=f"Error al analizar: {e}",
                    )
                )
                continue
            seen.add(key)
            session.add(row)
            _tournament_result(session, record)
            file_report.imported += 1

    totals = report.totals
    batch.files = totals["files"]
    batch.hands_found = totals["hands_found"]
    batch.imported = totals["imported"]
    batch.duplicates = totals["duplicates"]
    batch.failed = totals["failed"]
    batch.report = report_to_dict(report)
    session.commit()
    return batch, report


def report_to_dict(report: ImportReport) -> dict:
    return {
        "totals": report.totals,
        "files": [f.__dict__ for f in report.files],
        "errors": [e.__dict__ for e in report.errors],
        "errors_truncated": report.errors_truncated,
    }
