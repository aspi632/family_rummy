from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class Suit(str, Enum):
    CLUBS = "clubs"
    DIAMONDS = "diamonds"
    HEARTS = "hearts"
    SPADES = "spades"


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14


class MeldType(str, Enum):
    RUN = "run"
    SET = "set"


class TurnPhase(str, Enum):
    DRAW = "draw"
    PLAY = "play"
    ROUND_OVER = "round_over"


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank

    @property
    def points(self) -> int:
        if self.rank == Rank.ACE:
            return 15
        if self.rank >= Rank.TEN:
            return 10
        return 5


@dataclass
class Player:
    id: str
    name: str
    hand: list[Card] = field(default_factory=list)
    score: int = 0


@dataclass(frozen=True)
class PlayedCard:
    card: Card
    owner_id: str


@dataclass
class Meld:
    id: str
    type: MeldType
    cards: list[PlayedCard] = field(default_factory=list)