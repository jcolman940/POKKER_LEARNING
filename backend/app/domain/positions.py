"""Table positions, computed relative to the button for 2 to 10 occupied seats.

6-max and 9-max share the same logic: seats are named backwards from the button
(BTN, CO, HJ, LJ, then UTG+2, UTG+1, UTG), so a 6-handed table starts at LJ.
Ten-handed tables add UTG+3, which the spec's name list does not cover.
"""

from __future__ import annotations

MIN_PLAYERS = 2
MAX_PLAYERS = 10

# Preflop action order for each table size (first to act ... BB).
_PREFLOP_ORDER: dict[int, tuple[str, ...]] = {
    2: ("BTN", "BB"),  # heads-up: the button posts the small blind
    3: ("BTN", "SB", "BB"),
    4: ("CO", "BTN", "SB", "BB"),
    5: ("HJ", "CO", "BTN", "SB", "BB"),
    6: ("LJ", "HJ", "CO", "BTN", "SB", "BB"),
    7: ("UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"),
    8: ("UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"),
    9: ("UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"),
    10: ("UTG", "UTG+1", "UTG+2", "UTG+3", "LJ", "HJ", "CO", "BTN", "SB", "BB"),
}


def _check_players(num_players: int) -> None:
    if not MIN_PLAYERS <= num_players <= MAX_PLAYERS:
        raise ValueError(f"La mesa debe tener entre {MIN_PLAYERS} y {MAX_PLAYERS} jugadores")


def preflop_order(num_players: int) -> list[str]:
    """Positions in preflop action order (first to act first, BB last)."""
    _check_players(num_players)
    return list(_PREFLOP_ORDER[num_players])


def postflop_order(num_players: int) -> list[str]:
    """Positions in postflop action order (out of position first, button last)."""
    order = preflop_order(num_players)
    if num_players == 2:
        return ["BB", "BTN"]
    blinds, rest = order[-2:], order[:-2]
    return blinds + rest


def position_names(num_players: int) -> list[str]:
    return preflop_order(num_players)


def position_of_seat(seat: int, button_seat: int, occupied_seats: list[int]) -> str:
    """Position of `seat` given the button seat and the occupied seat numbers.

    Seats are numbered clockwise; only occupied seats count.
    """
    seats = sorted(set(occupied_seats))
    if seat not in seats or button_seat not in seats:
        raise ValueError("El asiento y el botón deben estar ocupados")
    n = len(seats)
    _check_players(n)
    offset = (seats.index(seat) - seats.index(button_seat)) % n
    # Offset 0 is the button, then the blinds, then preflop order from UTG.
    order = _PREFLOP_ORDER[n]
    clockwise_from_button = (order[-3],) + order[-2:] + order[:-3] if n > 2 else order
    return clockwise_from_button[offset]
