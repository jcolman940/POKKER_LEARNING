import random
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from app.db.session import run_migrations
from app.trainer.srs import INITIAL_EASE, MIN_EASE, CardState, pick_kind, relearn_offset, schedule

NOW = datetime(2026, 10, 7, tzinfo=UTC)
NEW = CardState(ease=INITIAL_EASE, interval_days=0, due_at=None, reps=0, lapses=0)


def test_correct_grows_interval():
    s1 = schedule(NEW, "correct", NOW)
    assert s1.interval_days == 1 and s1.due_at == NOW + timedelta(days=1)
    s2 = schedule(s1, "correct", NOW)
    assert s2.interval_days == 3
    s3 = schedule(s2, "correct", NOW)
    assert s3.interval_days == round(3 * s2.ease)


def test_acceptable_keeps_interval_and_lowers_ease():
    s = schedule(CardState(2.5, 3, NOW, 2, 0), "acceptable", NOW)
    assert s.interval_days == 3 and s.ease == 2.45


def test_error_resets_and_floors_ease():
    s = schedule(CardState(1.4, 10, NOW, 5, 0), "error", NOW)
    assert s.interval_days == 0 and s.ease == MIN_EASE and s.lapses == 1 and s.due_at == NOW


def test_relearn_offset_range():
    rng = random.Random(1)
    assert all(3 <= relearn_offset(rng) <= 5 for _ in range(100))


def test_pick_kind_mix():
    rng = random.Random(7)
    kinds = [pick_kind(rng, has_due=True, has_relearn_due=False) for _ in range(1000)]
    assert 0.65 < kinds.count("due") / 1000 < 0.75
    assert pick_kind(rng, has_due=True, has_relearn_due=True) == "relearn"
    assert pick_kind(rng, has_due=False, has_relearn_due=False) == "new"


def test_migration_creates_trainer_tables_and_builtin_payouts(tmp_path):
    url = f"sqlite:///{tmp_path / 't.sqlite3'}"
    run_migrations(url)
    engine = sa.create_engine(url)
    tables = sa.inspect(engine).get_table_names()
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(sa.text("select name from payout_structures"))}
    engine.dispose()
    for t in ("trainer_sessions", "trainer_cards", "trainer_attempts", "payout_structures"):
        assert t in tables
    assert names == {"Mesa final 9 (100)", "Burbuja SNG 4 de 3 premios"}
