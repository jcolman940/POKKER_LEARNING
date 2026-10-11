"""Hand history parsers: one plugin per poker room, detected by file content.

Room parsers are written against real sample files and registered here with
`register()`. GGPoker tournaments are supported; PokerStars and GGPoker cash
still wait for real samples.
"""

from app.parsers.base import HandHistoryParser, ParseError, RawHand
from app.parsers.ggpoker import GGPokerParser
from app.parsers.registry import detect_parser, register, registered_parsers, unregister

register(GGPokerParser())

__all__ = [
    "HandHistoryParser",
    "ParseError",
    "RawHand",
    "detect_parser",
    "register",
    "registered_parsers",
    "unregister",
]
