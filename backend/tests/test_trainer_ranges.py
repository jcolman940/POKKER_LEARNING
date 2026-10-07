import random

import numpy as np
import pytest

from app.db.models import PreflopChart
from app.recommend.preflop_equity import class_names, combos_per_class
from app.trainer.ranges import generate_range_drill, score_range


def _target() -> list[float]:
    names = class_names()
    return [1.0 if n in ("AA", "KK", "AKs", "AKo", "72o") else 0.0 for n in names]


def _chart(**kw) -> PreflopChart:
    base = dict(
        name="BTN RFI",
        source="custom",
        game_format="cash",
        players=6,
        position="BTN",
        stack_bb=100.0,
        situation="rfi",
        actions={"raise": _target(), "call": [0.0] * 169},
    )
    base.update(kw)
    return PreflopChart(**base)


def test_identical_is_perfect():
    t = _target()
    r = score_range(t, list(t))
    assert r.precision == 1.0 and r.error == 0.0 and r.verdict == "correct"
    assert all(d == 0 for d in r.diff_grid)


def test_empty_vs_nonempty_is_zero():
    r = score_range(_target(), [0.0] * 169)
    assert r.precision == 0.0 and r.verdict == "error"


def test_both_empty_is_perfect():
    r = score_range([0.0] * 169, [0.0] * 169)
    assert r.error == 0.0 and r.verdict == "correct"


def test_half_combos_missing():
    names = class_names()
    t = [1.0 if n in ("AA", "AKo") else 0.0 for n in names]  # 6 + 12 combos
    p = [1.0 if n == "AKo" else 0.0 for n in names]  # missing AA: 6 of 18
    r = score_range(t, p)
    assert r.precision == pytest.approx(12 / 18)
    p2 = [1.0 if n == "AA" else 0.0 for n in names]  # missing AKo: 12 of 18
    assert score_range(t, p2).precision == pytest.approx(6 / 18)


def test_top_classes_sorted_by_weight():
    t = _target()
    r = score_range(t, [0.0] * 169)
    weights = {c["hand_class"]: c["weight"] for c in r.top_classes}
    assert weights == {"72o": 12.0, "AKo": 12.0, "AA": 6.0, "KK": 6.0, "AKs": 4.0}
    ws = [c["weight"] for c in r.top_classes]
    assert ws == sorted(ws, reverse=True)
    assert len(score_range(t, [0.5] * 169).top_classes) == 10
    top = r.top_classes[0]
    assert set(top) == {"hand_class", "target", "painted", "weight"}


def test_diff_grid_is_painted_minus_target():
    t = _target()
    p = [0.5] * 169
    r = score_range(t, p)
    assert np.allclose(r.diff_grid, np.array(p) - np.array(t))
    assert combos_per_class().sum() == 1326


@pytest.mark.parametrize(
    "bad", [[0.0] * 168, [0.0] * 170, [1.5] + [0.0] * 168, [-0.1] + [0.0] * 168]
)
def test_validation(bad):
    with pytest.raises(ValueError, match="169 valores entre 0 y 1"):
        score_range(_target(), bad)


def test_generate_without_charts_is_none(db_session):
    assert generate_range_drill(db_session, random.Random(1), {}) is None


def test_generate_drill_and_filters(db_session):
    db_session.add(_chart())
    db_session.add(_chart(name="x", game_format="mtt", position="CO", situation="vs_open"))
    db_session.commit()
    d = generate_range_drill(db_session, random.Random(1), {"formats": ["cash"]})
    assert d is not None and d.action == "raise"  # call has no frequency
    assert d.card_key == f"range|{d.chart_id}|raise"
    assert d.title == "Pintá el rango de raise: BTN RFI · cash 6 jugadores · 100bb"
    assert generate_range_drill(db_session, random.Random(1), {"positions": ["SB"]}) is None
    d2 = generate_range_drill(db_session, random.Random(1), {"situations": ["vs_open"]})
    assert d2 is not None and "vs open" in d2.title
