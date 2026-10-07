import pytest

from app.db.models import PreflopChart, SolverJob
from app.solver.flops import representative_flops
from app.solver.library import build_line_spots, enqueue_line, library_status, load_library

FLOP = representative_flops()[0]  # library_status only lists the representative flops


def grid(classes):
    import pokercore

    return [classes.get(n, 0.0) for n in pokercore.hand_class_names()]


def add_cash_btn_bb_charts(session, raise_classes=None):
    common = dict(
        source="custom", game_format="cash", players=6, stack_bb=100.0, ante_bb=0.0,
        note="", rake=None, open_size_bb=2.5,
    )  # fmt: skip
    session.add(
        PreflopChart(
            name="btn rfi", position="BTN", vs_position=None, situation="rfi",
            actions={"raise": grid(raise_classes or {"AA": 1, "KK": 1, "AKs": 1})}, **common,
        )
    )  # fmt: skip
    session.add(
        PreflopChart(
            name="bb vs btn", position="BB", vs_position="BTN", situation="vs_open",
            actions={"call": grid({"QQ": 1, "JJ": 1, "AQs": 1})}, **common,
        )
    )  # fmt: skip
    session.commit()


@pytest.fixture
def cash():
    fam = next(f for f in load_library() if f.id == "cash")
    return fam, next(line for line in fam.lines if line.id == "btn_bb")


def test_library_definition_loads():
    fams = load_library()
    assert {f.id for f in fams} == {"mtt", "cash"}
    assert sum(len(f.lines) for f in fams) == 11


def test_build_line_spots_pot_and_stack(db_session, cash):
    add_cash_btn_bb_charts(db_session)
    fam, line = cash
    built = build_line_spots(db_session, fam, line, ["AhKd2c"])
    spot = built.spots["AhKd2c"]
    assert spot.pot_bb == 5.5  # 2.5 + 2.5 + SB 0.5
    assert spot.stack_bb == 97.5
    assert spot.range_ip.startswith("AA")  # BTN (aggressor) is IP vs BB
    assert spot.range_oop.startswith("QQ") or "AQs" in spot.range_oop
    assert built.missing == []


def test_missing_chart_is_reported_and_not_enqueued(db_session, cash):
    fam, line = cash
    built = build_line_spots(db_session, fam, line, ["AhKd2c"])
    assert built.spots == {}
    assert built.missing == [
        "falta tabla: BTN RFI (cash, 100bb)",
        "falta tabla: BB vs open de BTN (cash, 100bb)",
    ]
    assert enqueue_line(db_session, fam, line) == 0


def test_enqueue_line_and_status(db_session, cash):
    add_cash_btn_bb_charts(db_session)
    fam, line = cash
    assert enqueue_line(db_session, fam, line, [FLOP, "7s7h2d"]) == 2
    assert db_session.query(SolverJob).count() == 2
    status = library_status(db_session, [fam])
    entries = {e["flop"]: e["status"] for e in status[0]["lines"][0]["entries"]}
    assert entries[FLOP] == "queued"


def test_outdated_when_chart_changes(db_session, cash):
    from app.solver.cache import store_result
    from app.solver.library import library_key
    from app.solver.output_parser import SolverAction, StrategyNode
    from app.solver.runner import Progress

    add_cash_btn_bb_charts(db_session)
    fam, line = cash
    spot = build_line_spots(db_session, fam, line, [FLOP]).spots[FLOP]
    tree = StrategyNode("oop", [SolverAction("check")], {"AsAd": [1.0]})
    store_result(db_session, spot, tree, Progress(), 1.0, library_key(fam.id, line.id, FLOP))
    chart = db_session.query(PreflopChart).filter_by(position="BTN").one()
    chart.actions = {"raise": grid({"AA": 1})}
    db_session.commit()
    status = library_status(db_session, [fam])
    line_status = next(lst for lst in status[0]["lines"] if lst["id"] == "btn_bb")
    entry = next(e for e in line_status["entries"] if e["flop"] == FLOP)
    assert entry["status"] == "outdated"
