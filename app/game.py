from __future__ import annotations

import random
from uuid import uuid4

from app.models import (
    Card,
    Meld,
    MeldType,
    PlayedCard,
    Player,
    Rank,
    Suit,
    TurnPhase,
)
from app.rules import get_meld_type, is_valid_meld


class GameError(Exception):
    pass


class Game:
    CARDS_PER_PLAYER = 5

    def __init__(
        self,
        players: list[Player],
        target_score: int | None = None,
        max_rounds: int | None = None,
        rng: random.Random | None = None,
    ):
        if len(players) < 2:
            raise ValueError("At least 2 players are required")

        if len(players) > 7:
            raise ValueError("At most 7 players are supported")

        if target_score is None and max_rounds is None:
            raise ValueError(
                "target_score or max_rounds must be specified"
            )

        self.players = players
        self.target_score = target_score
        self.max_rounds = max_rounds

        self.rng = rng or random.Random()

        self.deck: list[Card] = []
        self.discard: list[Card] = []
        self.melds: list[Meld] = []

        self.current_player_index = 0
        self.phase = TurnPhase.ROUND_OVER

        self.round_number = 0
        self.previous_winner_id: str | None = None
        self.round_winner_id: str | None = None

        self.last_round_scores: dict[str, int] = {}
        self.match_over = False

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    def create_deck(self) -> list[Card]:
        return [
            Card(suit, rank)
            for suit in Suit
            for rank in Rank
        ]

    def start_round(self) -> None:
        if self.match_over:
            raise GameError("Match is already over")

        self.round_number += 1

        self.deck = self.create_deck()
        self.rng.shuffle(self.deck)

        self.discard = []
        self.melds = []
        self.round_winner_id = None
        self.last_round_scores = {}

        for player in self.players:
            player.hand.clear()

        # Deal 5 cards to every player, one card at a time.
        for _ in range(self.CARDS_PER_PLAYER):
            for player in self.players:
                player.hand.append(self.deck.pop())

        # First open discard card.
        self.discard.append(self.deck.pop())

        # First round: random starting player.
        if self.previous_winner_id is None:
            self.current_player_index = self.rng.randrange(
                len(self.players)
            )

        # Later rounds: previous winner starts.
        else:
            self.current_player_index = self._player_index(
                self.previous_winner_id
            )

        self.phase = TurnPhase.DRAW

    def draw_from_deck(
        self,
        player_id: str,
    ) -> Card | None:

        self._require_turn(player_id)
        self._require_phase(TurnPhase.DRAW)

        if not self.deck:
            self._finish_round()
            return None

        card = self.deck.pop()

        self.current_player.hand.append(card)

        self.phase = TurnPhase.PLAY

        return card

    def draw_from_discard(
        self,
        player_id: str,
        discard_index: int,
        hand_cards_for_meld: list[Card],
        discard_cards_for_meld: list[Card],
    ) -> Meld:

        self._require_turn(player_id)
        self._require_phase(TurnPhase.DRAW)

        if not 0 <= discard_index < len(self.discard):
            raise GameError("Invalid discard index")

        selected_card = self.discard[discard_index]

        # Все карты начиная с выбранной игрок забирает.
        taken_cards = self.discard[discard_index:]

        # Главная выбранная карта ОБЯЗАНА участвовать
        # в новой комбинации.
        if selected_card not in discard_cards_for_meld:
            raise GameError(
                "Selected discard card must be used in the meld"
            )

        # Нельзя использовать карты из сброса,
        # которые лежат раньше выбранной.
        taken_copy = taken_cards.copy()

        for card in discard_cards_for_meld:
            if card not in taken_copy:
                raise GameError(
                    "Invalid discard card used in meld"
                )

            taken_copy.remove(card)

        # Проверяем карты руки.
        self._require_cards_in_hand(
            self.current_player,
            hand_cards_for_meld,
        )

        meld_cards = (
            hand_cards_for_meld
            + discard_cards_for_meld
        )

        meld_type = get_meld_type(
            meld_cards
        )

        if meld_type is None:
            raise GameError(
                "Cards do not form a valid new meld"
            )

        # Удаляем карты руки, пошедшие в meld.
        self._remove_cards_from_hand(
            self.current_player,
            hand_cards_for_meld,
        )

        # Весь хвост сброса исчезает со стола.
        self.discard = self.discard[:discard_index]

        # Из взятых карт только те, которые НЕ пошли
        # в комбинацию, попадают на руку.
        remaining_taken_cards = taken_cards.copy()

        for card in discard_cards_for_meld:
            remaining_taken_cards.remove(card)

        self.current_player.hand.extend(
            remaining_taken_cards
        )

        played_cards = [
            PlayedCard(
                card=card,
                owner_id=player_id,
            )
            for card in meld_cards
        ]

        meld = Meld(
            id=str(uuid4()),
            type=meld_type,
            cards=self._sort_meld_cards(
                played_cards,
                meld_type,
            ),
        )

        self.melds.append(meld)

        self.phase = TurnPhase.PLAY

        self._check_round_end()

        return meld

    def create_meld(
        self,
        player_id: str,
        cards: list[Card],
    ) -> Meld:
        self._require_turn(player_id)
        self._require_phase(TurnPhase.PLAY)

        self._require_cards_in_hand(
            self.current_player,
            cards,
        )

        meld_type = get_meld_type(cards)

        if meld_type is None:
            raise GameError("Invalid meld")

        self._remove_cards_from_hand(
            self.current_player,
            cards,
        )

        played_cards = [
            PlayedCard(card, player_id)
            for card in cards
        ]

        meld = Meld(
            id=str(uuid4()),
            type=meld_type,
            cards=self._sort_meld_cards(
                played_cards,
                meld_type,
            ),
        )

        self.melds.append(meld)

        self._check_round_end()

        return meld

    def extend_meld(
        self,
        player_id: str,
        meld_id: str,
        card: Card,
    ) -> None:
        self._require_turn(player_id)
        self._require_phase(TurnPhase.PLAY)

        self._require_cards_in_hand(
            self.current_player,
            [card],
        )

        meld = self._get_meld(meld_id)

        existing_cards = [
            played.card
            for played in meld.cards
        ]

        candidate = existing_cards + [card]

        if not is_valid_meld(candidate):
            raise GameError("Card cannot extend this meld")

        self._remove_cards_from_hand(
            self.current_player,
            [card],
        )

        meld.cards.append(
            PlayedCard(
                card=card,
                owner_id=player_id,
            )
        )

        meld.cards = self._sort_meld_cards(
            meld.cards,
            meld.type,
        )

        self._check_round_end()

    def discard_card(
        self,
        player_id: str,
        card: Card,
    ) -> None:
        self._require_turn(player_id)
        self._require_phase(TurnPhase.PLAY)

        self._require_cards_in_hand(
            self.current_player,
            [card],
        )

        self._remove_cards_from_hand(
            self.current_player,
            [card],
        )

        self.discard.append(card)

        if self._check_round_end():
            return

        self.current_player_index = (
            self.current_player_index + 1
        ) % len(self.players)

        self.phase = TurnPhase.DRAW

    def calculate_round_scores(self) -> dict[str, int]:
        scores = {
            player.id: 0
            for player in self.players
        }

        # Cards laid on the table are positive.
        for meld in self.melds:
            for played_card in meld.cards:
                scores[played_card.owner_id] += (
                    played_card.card.points
                )

        # Cards left in hand are negative.
        for player in self.players:
            scores[player.id] -= sum(
                card.points
                for card in player.hand
            )

        return scores

    def _check_round_end(self) -> bool:
        if self.current_player.hand:
            return False

        self._finish_round(
            winner_id=self.current_player.id,
        )

        return True

    def _finish_round(
        self,
        winner_id: str | None = None,
    ) -> None:

        round_scores = (
            self.calculate_round_scores()
        )

        self.last_round_scores = round_scores

        # Обычный случай:
        # игрок закончил все карты.
        if winner_id is None:
            winner_id = max(
                self.players,
                key=lambda player:
                    round_scores[player.id],
            ).id

        self.round_winner_id = winner_id
        self.previous_winner_id = winner_id

        self.phase = TurnPhase.ROUND_OVER

        for player in self.players:
            player.score += (
                round_scores[player.id]
            )

        self._check_match_end()

    def start_next_round(
        self,
    ) -> None:

        if self.phase != TurnPhase.ROUND_OVER:
            raise GameError(
                "Current round is not over"
            )

        if self.match_over:
            raise GameError(
                "Match is already over"
            )

        self.start_round()

    def _check_match_end(self) -> None:
        score_limit_reached = (
            self.target_score is not None
            and any(
                player.score >= self.target_score
                for player in self.players
            )
        )

        round_limit_reached = (
            self.max_rounds is not None
            and self.round_number >= self.max_rounds
        )

        self.match_over = (
            score_limit_reached
            or round_limit_reached
        )

    def get_match_winner(self) -> Player | None:
        if not self.match_over:
            return None

        return max(
            self.players,
            key=lambda player: player.score,
        )

    def _require_turn(self, player_id: str) -> None:
        if self.current_player.id != player_id:
            raise GameError("It is not this player's turn")

    def _require_phase(self, phase: TurnPhase) -> None:
        if self.phase != phase:
            raise GameError(
                f"Expected phase {phase}, current phase is {self.phase}"
            )

    def _player_index(self, player_id: str) -> int:
        for i, player in enumerate(self.players):
            if player.id == player_id:
                return i

        raise GameError("Player not found")

    def _get_meld(self, meld_id: str) -> Meld:
        for meld in self.melds:
            if meld.id == meld_id:
                return meld

        raise GameError("Meld not found")

    @staticmethod
    def _require_cards_in_hand(
        player: Player,
        cards: list[Card],
    ) -> None:
        hand_copy = player.hand.copy()

        for card in cards:
            if card not in hand_copy:
                raise GameError("Player does not have this card")

            hand_copy.remove(card)

    @staticmethod
    def _remove_cards_from_hand(
        player: Player,
        cards: list[Card],
    ) -> None:
        for card in cards:
            player.hand.remove(card)

    @staticmethod
    def _sort_meld_cards(
        cards: list[PlayedCard],
        meld_type: MeldType,
    ) -> list[PlayedCard]:

        if meld_type == MeldType.RUN:
            return sorted(
                cards,
                key=lambda played: played.card.rank,
            )

        return cards