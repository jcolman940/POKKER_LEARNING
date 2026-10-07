from app.domain.preflop import preflop_situation
from app.domain.scenario import Situation
from tests.hands import act

POS = {"U": "LJ", "H": "HJ", "C": "CO", "B": "BTN", "S": "SB", "Hero": "BB"}


def test_rfi_when_folded_to_hero():
    assert preflop_situation(POS, "B", [act("p", "U", "fold")], {"U"}) == Situation.RFI


def test_vs_open():
    assert preflop_situation(POS, "B", [act("p", "C", "raise", 2.5)], set()) == Situation.VS_OPEN


def test_squeeze_when_open_was_called():
    before = [act("p", "C", "raise", 2.5), act("p", "B", "call", 2.5)]
    assert preflop_situation(POS, "Hero", before, set()) == Situation.SQUEEZE


def test_bvb_unopened_and_sb_open():
    folded = {"U", "H", "C", "B"}
    assert preflop_situation(POS, "S", [], folded) == Situation.BVB
    assert preflop_situation(POS, "Hero", [act("p", "S", "raise", 3)], folded) == Situation.BVB


def test_vs_3bet_and_vs_4bet():
    before = [act("p", "B", "raise", 2.5), act("p", "Hero", "raise", 11)]
    assert preflop_situation(POS, "B", before, set()) == Situation.VS_3BET
    before4 = before + [act("p", "B", "raise", 25)]
    assert preflop_situation(POS, "Hero", before4, set()) == Situation.VS_4BET


def test_vs_allin():
    before = [act("p", "C", "raise", 12, all_in=True)]
    assert preflop_situation(POS, "B", before, set()) == Situation.VS_ALLIN
