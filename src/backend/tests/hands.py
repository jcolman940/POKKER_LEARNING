"""Builder for HandRecords in tests. It is not a room format: it builds the
normalized model directly."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.hand import Action, ActionType, HandRecord, Seat
from app.domain.positions import position_of_seat
from app.domain.scenario import GameFormat, Street

STREETS = {"p": Street.PREFLOP, "f": Street.FLOP, "t": Street.TURN, "r": Street.RIVER}


def act(street: str, player: str, kind: str, amount: float = 0.0, all_in: bool = False) -> Action:
    return Action(
        street=STREETS[street], player=player, type=ActionType(kind), amount=amount, all_in=all_in
    )


def make_hand(
    stacks: dict[str, float],
    actions: list[Action],
    *,
    button: str,
    hero: str | None = "Hero",
    hero_cards: str | None = "AhKh",
    board: str = "",
    shown: dict[str, str] | None = None,
    collected: dict[str, float] | None = None,
    sb: float = 0.5,
    bb: float = 1.0,
    ante: float = 0.0,
    hand_id: str = "1",
    site: str = "test",
    game_type: GameFormat = GameFormat.CASH,
    played_at: datetime | None = None,
    sitting_out: tuple[str, ...] = (),
    rake: float = 0.0,
) -> HandRecord:
    """Seats follow the dict order (seat 1, 2, ...). Antes and blinds are posted
    automatically from the positions; `actions` start after the posts."""
    seats = [
        Seat(seat=i, name=name, stack=stack, sitting_out=name in sitting_out)
        for i, (name, stack) in enumerate(stacks.items(), start=1)
    ]
    occupied = [s.seat for s in seats if not s.sitting_out]
    button_seat = next(s.seat for s in seats if s.name == button)
    positions = {
        s.name: position_of_seat(s.seat, button_seat, occupied) for s in seats if not s.sitting_out
    }
    posts: list[Action] = []
    if ante:
        posts += [act("p", p, "post_ante", ante) for p in positions]
    sb_player = next(
        p for p, pos in positions.items() if pos == ("BTN" if len(positions) == 2 else "SB")
    )
    bb_player = next(p for p, pos in positions.items() if pos == "BB")
    posts += [act("p", sb_player, "post_sb", sb), act("p", bb_player, "post_bb", bb)]
    return HandRecord(
        site=site,
        hand_id=hand_id,
        played_at=played_at or datetime(2026, 1, 1, tzinfo=UTC),
        game_type=game_type,
        max_seats=max(len(seats), 2),
        sb=sb,
        bb=bb,
        ante=ante,
        button_seat=button_seat,
        seats=seats,
        hero=hero,
        hero_cards=hero_cards,
        actions=posts + actions,
        board=board,
        shown=shown or {},
        collected=collected or {},
        rake=rake,
    )
