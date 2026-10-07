"""Hand history parsers: one plugin per poker room, detected by file content.

Room parsers (GGPoker, PokerStars) are written against real sample files and
registered here with `register()`. Until then no room is supported and imports
report every file as unrecognized.
"""

from app.parsers.base import HandHistoryParser, ParseError, RawHand
from app.parsers.registry import detect_parser, register, registered_parsers, unregister

__all__ = [
    "HandHistoryParser",
    "ParseError",
    "RawHand",
    "detect_parser",
    "register",
    "registered_parsers",
    "unregister",
]
