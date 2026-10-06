import pytest

from app.domain.cards import CardError, draw, ensure_disjoint, parse_cards
from app.domain.metrics import pot_metrics
from app.domain.positions import position_of_seat, postflop_order, preflop_order


def test_parse_cards_normalizes_and_validates():
    assert parse_cards("ahKD 2c") == ["Ah", "Kd", "2c"]
    assert parse_cards("") == []
    with pytest.raises(CardError):
        parse_cards("AhAh")
    with pytest.raises(CardError):
        parse_cards("Ax")
    with pytest.raises(CardError):
        parse_cards("AhK")


def test_ensure_disjoint_and_draw():
    with pytest.raises(CardError, match="Ah"):
        ensure_disjoint({"hero": ["Ah", "Kd"], "board": ["Ah"]})
    import random

    cards = draw(5, ["Ah", "Kd"], random.Random(1))
    assert len(set(cards)) == 5 and not {"Ah", "Kd"} & set(cards)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (2, ["BTN", "BB"]),
        (3, ["BTN", "SB", "BB"]),
        (6, ["LJ", "HJ", "CO", "BTN", "SB", "BB"]),
        (9, ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]),
    ],
)
def test_preflop_order(n, expected):
    assert preflop_order(n) == expected


def test_postflop_order():
    assert postflop_order(2) == ["BB", "BTN"]
    assert postflop_order(6) == ["SB", "BB", "LJ", "HJ", "CO", "BTN"]
    with pytest.raises(ValueError):
        preflop_order(11)


def test_position_of_seat_relative_to_button():
    seats = [1, 2, 4, 5, 7, 9]  # 6 occupied seats out of 9
    assert position_of_seat(4, button_seat=4, occupied_seats=seats) == "BTN"
    assert position_of_seat(5, button_seat=4, occupied_seats=seats) == "SB"
    assert position_of_seat(7, button_seat=4, occupied_seats=seats) == "BB"
    assert position_of_seat(9, button_seat=4, occupied_seats=seats) == "LJ"
    assert position_of_seat(2, button_seat=4, occupied_seats=seats) == "CO"
    assert position_of_seat(3, button_seat=3, occupied_seats=[3, 8]) == "BTN"
    assert position_of_seat(8, button_seat=3, occupied_seats=[3, 8]) == "BB"


def test_pot_metrics():
    # Villain bets 5 into 5: pot is 10, hero calls 5.
    m = pot_metrics(pot=10, to_call=5, effective_stack=95)
    assert m.pot_odds == pytest.approx(2.0)
    assert m.required_equity == pytest.approx(1 / 3)
    assert m.mdf == pytest.approx(0.5)
    assert m.spr == pytest.approx(9.5)

    no_bet = pot_metrics(pot=6, to_call=0, effective_stack=60)
    assert no_bet.required_equity is None and no_bet.mdf is None
    assert no_bet.spr == pytest.approx(10)
    assert pot_metrics(0, 0, 100).spr is None
