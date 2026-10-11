"""GGPoker hand histories (tournaments), written against real exports.

Format notes (from the samples in tests/fixtures/hand_histories/ggpoker):
- Files list hands newest first; hands are separated by blank lines and start
  with "Poker Hand #TM...: Tournament #...".
- GG anonymizes opponents (hex ids) and names the user "Hero".
- "raises X to Y": Y is the player's total bet on the street; X is the raise
  increment, so the chips moved are Y minus what the player already had in.
- Antes are dead money and do not count towards the street bet.
- A short stack can post a partial blind with no "all-in" text; all-ins are
  derived from the remaining stack instead of the text.
- "*** SHOWDOWN ***" appears in every hand; side pots give one "collected" line
  per pot, so a player can collect several times.
- Times are the player's local time.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.domain.hand import Action, ActionType, HandRecord, Seat, TournamentInfo
from app.domain.scenario import GameFormat, Street
from app.parsers.base import HandHistoryParser, ParseError, RawHand, split_on

HAND_START = re.compile(r"^Poker Hand #\S+: ")
HEADER = re.compile(
    r"^Poker Hand #(?P<id>TM\d+): Tournament #(?P<tid>\d+), (?P<name>.+?) Hold'em No Limit"
    r" - Level(?P<level>\d+)\((?P<sb>[\d,.]+)/(?P<bb>[\d,.]+)(?:\((?P<ante>[\d,.]+)\))?\)"
    r" - (?P<date>\d{4}/\d{2}/\d{2} \d{1,2}:\d{2}:\d{2})$"
)
TABLE = re.compile(
    r"^Table '(?P<name>[^']*)' (?P<max>\d+)-max Seat #(?P<button>\d+) is the button$"
)
SEAT = re.compile(r"^Seat (?P<seat>\d+): (?P<name>.+) \((?P<stack>[\d,.]+) in chips\)$")
DEALT = re.compile(r"^Dealt to (?P<name>.+?) ?(?:\[(?P<cards>[^\]]+)\])?$")
ACTION = re.compile(
    r"^(?P<name>.+?): (?:"
    r"(?P<post>posts (?:the ante|small blind|big blind)) (?P<post_amount>[\d,.]+)"
    r"|(?P<fold>folds)|(?P<check>checks)"
    r"|calls (?P<call>[\d,.]+)"
    r"|bets (?P<bet>[\d,.]+)"
    r"|raises [\d,.]+ to (?P<raise_to>[\d,.]+)"
    r"|shows \[(?P<shows>[^\]]+)\](?: \(.*\))?"
    r")(?P<all_in> and is all-in)?$"
)
UNCALLED = re.compile(r"^Uncalled bet \((?P<amount>[\d,.]+)\) returned to (?P<name>.+)$")
COLLECTED = re.compile(r"^(?P<name>.+?) collected (?P<amount>[\d,.]+) from pot$")
STREET = re.compile(r"^\*\*\* (?P<street>FLOP|TURN|RIVER) \*\*\* (?P<cards>.*)$")
TOTAL = re.compile(r"^Total pot [\d,.]+ \| Rake (?P<rake>[\d,.]+)")
BOARD = re.compile(r"^Board \[(?P<cards>[^\]]*)\]$")
SUMMARY_SHOWED = re.compile(r"^Seat \d+: (?P<name>.+?)(?: \([^)]*\))? showed \[(?P<cards>[^\]]+)\]")
BUY_IN = re.compile(r"\$(?P<amount>[\d,.]+)")

POSTS = {
    "posts the ante": ActionType.POST_ANTE,
    "posts small blind": ActionType.POST_SB,
    "posts big blind": ActionType.POST_BB,
}
STREETS = {"FLOP": Street.FLOP, "TURN": Street.TURN, "RIVER": Street.RIVER}
# Lines that carry no information the HandRecord keeps.
IGNORED = re.compile(r"^(\*\*\* (HOLE CARDS|SHOWDOWN) \*\*\*|Seat \d+: .+)$")


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def _cards(text: str) -> str:
    return text.replace(" ", "")


def _format(name: str) -> GameFormat:
    lowered = name.lower()
    if "spin" in lowered:
        return GameFormat.SPIN
    if "sit & go" in lowered or "sng" in lowered:
        return GameFormat.SNG
    return GameFormat.MTT


class GGPokerParser(HandHistoryParser):
    site = "ggpoker"
    label = "GGPoker"

    def detect(self, text: str) -> bool:
        # The importer already decoded the file and dropped any BOM.
        return bool(HAND_START.match(text.lstrip()))

    def split(self, text: str) -> list[RawHand]:
        return split_on(HAND_START, text)

    def parse(self, raw: RawHand) -> HandRecord:
        lines = raw.text.splitlines()
        header = HEADER.match(lines[0]) if lines else None
        if header is None:
            raise ParseError("Encabezado de mano de GGPoker no reconocido", line=1)
        table = TABLE.match(lines[1]) if len(lines) > 1 else None
        if table is None:
            raise ParseError("Línea de mesa no reconocida", line=2)

        seats: list[Seat] = []
        stacks: dict[str, float] = {}
        actions: list[Action] = []
        street = Street.PREFLOP
        street_bets: dict[str, float] = {}
        hero = hero_cards = None
        board = ""
        shown: dict[str, str] = {}
        collected: dict[str, float] = {}
        rake = 0.0
        in_summary = False

        def add(name: str, kind: ActionType, amount: float = 0.0, to: float | None = None) -> None:
            if name not in stacks:
                raise ValueError(f"Jugador desconocido: {name!r}")
            stacks[name] -= amount
            if kind != ActionType.POST_ANTE:
                street_bets[name] = street_bets.get(name, 0.0) + amount
            all_in = amount > 0 and stacks[name] <= 1e-9
            actions.append(
                Action(
                    street=street,
                    player=name,
                    type=kind,
                    amount=amount,
                    to_amount=to,
                    all_in=all_in,
                )
            )

        for number, line in enumerate(lines[2:], start=3):
            line = line.strip()
            if not line:
                continue
            try:
                if line == "*** SUMMARY ***":
                    in_summary = True
                    continue
                if in_summary:
                    if m := TOTAL.match(line):
                        rake = _num(m["rake"])
                    elif m := BOARD.match(line):
                        board = _cards(m["cards"])
                    elif m := SUMMARY_SHOWED.match(line):
                        shown.setdefault(m["name"], _cards(m["cards"]))
                    continue
                if not actions and (m := SEAT.match(line)):
                    name, stack = m["name"], _num(m["stack"])
                    seats.append(Seat(seat=int(m["seat"]), name=name, stack=stack))
                    stacks[name] = stack
                    continue
                if m := DEALT.match(line):
                    if m["cards"]:
                        hero, hero_cards = m["name"], _cards(m["cards"])
                    continue
                if m := STREET.match(line):
                    street = STREETS[m["street"]]
                    street_bets = {}
                    board = "".join(
                        _cards(part) for part in re.findall(r"\[([^\]]+)\]", m["cards"])
                    )
                    continue
                if m := UNCALLED.match(line):
                    name, amount = m["name"], _num(m["amount"])
                    if name not in stacks:
                        raise ValueError(f"Jugador desconocido: {name!r}")
                    stacks[name] += amount
                    street_bets[name] = street_bets.get(name, 0.0) - amount
                    actions.append(
                        Action(street=street, player=name, type=ActionType.RETURN, amount=amount)
                    )
                    continue
                if m := COLLECTED.match(line):
                    collected[m["name"]] = collected.get(m["name"], 0.0) + _num(m["amount"])
                    continue
                if m := ACTION.match(line):
                    name = m["name"]
                    if m["post"]:
                        add(name, POSTS[m["post"]], _num(m["post_amount"]))
                    elif m["fold"]:
                        add(name, ActionType.FOLD)
                    elif m["check"]:
                        add(name, ActionType.CHECK)
                    elif m["call"]:
                        add(name, ActionType.CALL, _num(m["call"]))
                    elif m["bet"]:
                        add(name, ActionType.BET, _num(m["bet"]))
                    elif m["raise_to"]:
                        to = _num(m["raise_to"])
                        add(name, ActionType.RAISE, to - street_bets.get(name, 0.0), to)
                    elif m["shows"]:
                        shown[name] = _cards(m["shows"])
                    continue
                if IGNORED.match(line):
                    continue
            except ValueError as e:
                raise ParseError(str(e), line=number) from e
            raise ParseError(f"Línea no reconocida: {line[:120]}", line=number)

        name = header["name"]
        buy_in = BUY_IN.search(name)
        played_at = datetime.strptime(header["date"], "%Y/%m/%d %H:%M:%S").astimezone()
        return HandRecord(
            site=self.site,
            hand_id=header["id"],
            played_at=played_at.astimezone(UTC),
            game_type=_format(name),
            table_name=table["name"],
            max_seats=int(table["max"]),
            currency="USD" if buy_in else None,
            sb=_num(header["sb"]),
            bb=_num(header["bb"]),
            ante=_num(header["ante"]) if header["ante"] else 0.0,
            tournament=TournamentInfo(
                tournament_id=header["tid"],
                currency="USD" if buy_in else None,
                level=header["level"],
            ),
            button_seat=int(table["button"]),
            seats=seats,
            hero=hero,
            hero_cards=hero_cards,
            actions=actions,
            board=board,
            shown=shown,
            collected=collected,
            rake=rake,
        )
