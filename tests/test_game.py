import random

import pytest

from app.game import Game, GameError
from app.models import (
    Card,
    Player,
    Rank,
    Suit,
    TurnPhase,
)


def C(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(suit, rank)


def make_game() -> Game:
    return Game(
        players=[
            Player("alice", "Alice"),
            Player("bob", "Bob"),
        ],
        target_score=100,
        rng=random.Random(42),
    )


def prepare_alice_turn(game: Game) -> None:
    game.current_player_index = 0
    game.phase = TurnPhase.DRAW


def test_deck_has_52_unique_cards():
    game = make_game()

    deck = game.create_deck()

    assert len(deck) == 52
    assert len(set(deck)) == 52


def test_start_round_deals_five_cards():
    game = make_game()

    game.start_round()

    assert len(game.players[0].hand) == 5
    assert len(game.players[1].hand) == 5


def test_start_round_creates_first_discard():
    game = make_game()

    game.start_round()

    assert len(game.discard) == 1

    # 52 - 10 dealt - 1 initial discard
    assert len(game.deck) == 41


def test_draw_from_deck():
    game = make_game()
    game.start_round()

    player = game.current_player
    old_hand_size = len(player.hand)
    old_deck_size = len(game.deck)

    game.draw_from_deck(player.id)

    assert len(player.hand) == old_hand_size + 1
    assert len(game.deck) == old_deck_size - 1
    assert game.phase == TurnPhase.PLAY


def test_wrong_player_cannot_draw():
    game = make_game()
    game.start_round()

    wrong_player = next(
        player
        for player in game.players
        if player.id != game.current_player.id
    )

    with pytest.raises(GameError):
        game.draw_from_deck(wrong_player.id)


def test_draw_from_discard_immediately_creates_meld():
    game = make_game()
    alice = game.players[0]

    alice.hand = [
        C(Rank.SIX),
        C(Rank.SEVEN),
        C(Rank.KING, Suit.HEARTS),
    ]

    game.discard = [
        C(Rank.TWO, Suit.SPADES),
        C(Rank.EIGHT),
    ]

    prepare_alice_turn(game)

    meld = game.draw_from_discard(
        "alice",
        discard_index=1,
        hand_cards_for_meld=[
            C(Rank.SIX),
            C(Rank.SEVEN),
        ],
        discard_cards_for_meld=[
            C(Rank.EIGHT),
        ],
    )


def test_draw_from_middle_takes_all_following_cards():
    game = make_game()

    alice = game.players[0]

    alice.hand = [
        C(Rank.SIX),
        C(Rank.SEVEN),
        C(Rank.ACE, Suit.HEARTS),
    ]

    game.discard = [
        C(Rank.TWO, Suit.SPADES),
        C(Rank.EIGHT),
        C(Rank.KING, Suit.HEARTS),
        C(Rank.FOUR, Suit.DIAMONDS),
    ]

    prepare_alice_turn(game)

    game.draw_from_discard(
        "alice",
        discard_index=1,
        hand_cards_for_meld=[
            C(Rank.SIX),
            C(Rank.SEVEN),
        ],
        discard_cards_for_meld=[
            C(Rank.EIGHT),
        ],
    )

    assert game.discard == [
        C(Rank.TWO, Suit.SPADES),
    ]

    assert C(Rank.KING, Suit.HEARTS) in alice.hand
    assert C(Rank.FOUR, Suit.DIAMONDS) in alice.hand


def test_invalid_discard_draw_is_rejected():
    game = make_game()

    alice = game.players[0]

    alice.hand = [
        C(Rank.TWO, Suit.HEARTS),
        C(Rank.KING, Suit.DIAMONDS),
    ]

    game.discard = [
        C(Rank.EIGHT),
    ]

    prepare_alice_turn(game)

    with pytest.raises(GameError):
        game.draw_from_discard(
            "alice",
            discard_index=0,
            hand_cards_for_meld=[
                C(Rank.TWO, Suit.HEARTS),
                C(Rank.KING, Suit.DIAMONDS),
            ],
            discard_cards_for_meld=[
                C(Rank.EIGHT),
            ],
        )


def test_create_meld():
    game = make_game()

    alice = game.players[0]

    alice.hand = [
        C(Rank.SIX),
        C(Rank.SEVEN),
        C(Rank.EIGHT),
        C(Rank.KING, Suit.HEARTS),
    ]

    game.current_player_index = 0
    game.phase = TurnPhase.PLAY

    game.create_meld(
        "alice",
        [
            C(Rank.SIX),
            C(Rank.SEVEN),
            C(Rank.EIGHT),
        ],
    )

    assert len(game.melds) == 1

    assert alice.hand == [
        C(Rank.KING, Suit.HEARTS)
    ]


def test_player_can_extend_another_players_meld():
    game = make_game()

    alice = game.players[0]
    bob = game.players[1]

    alice.hand = [
        C(Rank.SIX),
        C(Rank.SEVEN),
        C(Rank.EIGHT),
        C(Rank.KING, Suit.HEARTS),
    ]

    game.current_player_index = 0
    game.phase = TurnPhase.PLAY

    meld = game.create_meld(
        "alice",
        [
            C(Rank.SIX),
            C(Rank.SEVEN),
            C(Rank.EIGHT),
        ],
    )

    # Now Bob's turn.
    game.current_player_index = 1
    game.phase = TurnPhase.PLAY

    bob.hand = [
        C(Rank.NINE),
        C(Rank.TWO, Suit.HEARTS),
    ]

    game.extend_meld(
        "bob",
        meld.id,
        C(Rank.NINE),
    )

    assert meld.cards[-1].card == C(Rank.NINE)
    assert meld.cards[-1].owner_id == "bob"


def test_last_card_can_be_played_without_discarding():
    game = make_game()

    alice = game.players[0]

    alice.hand = [
        C(Rank.SIX),
        C(Rank.SEVEN),
        C(Rank.EIGHT),
    ]

    game.current_player_index = 0
    game.phase = TurnPhase.PLAY

    game.create_meld(
        "alice",
        alice.hand.copy(),
    )

    assert alice.hand == []
    assert game.round_winner_id == "alice"
    assert game.phase == TurnPhase.ROUND_OVER


def test_last_card_can_be_discarded_to_win():
    game = make_game()

    alice = game.players[0]
    alice.hand = [
        C(Rank.KING, Suit.HEARTS)
    ]

    game.current_player_index = 0
    game.phase = TurnPhase.PLAY

    game.discard_card(
        "alice",
        C(Rank.KING, Suit.HEARTS),
    )

    assert alice.hand == []
    assert game.round_winner_id == "alice"


def test_turn_passes_after_discard():
    game = make_game()

    alice = game.players[0]

    alice.hand = [
        C(Rank.TWO),
        C(Rank.THREE),
    ]

    game.current_player_index = 0
    game.phase = TurnPhase.PLAY

    game.discard_card(
        "alice",
        C(Rank.TWO),
    )

    assert game.current_player.id == "bob"
    assert game.phase == TurnPhase.DRAW


def test_score_cards_on_table_positive_and_hand_negative():
    game = make_game()

    alice = game.players[0]
    bob = game.players[1]

    alice.hand = [
        C(Rank.SIX),
        C(Rank.SEVEN),
        C(Rank.EIGHT),
    ]

    bob.hand = [
        C(Rank.ACE, Suit.HEARTS),
    ]

    game.current_player_index = 0
    game.phase = TurnPhase.PLAY

    game.create_meld(
        "alice",
        alice.hand.copy(),
    )

    # Alice:
    # 6,7,8 = 5 + 5 + 5 = +15
    assert alice.score == 15

    # Bob:
    # Ace remains in hand = -15
    assert bob.score == -15


def test_previous_round_winner_starts_next_round():
    game = make_game()

    game.previous_winner_id = "bob"

    game.start_round()

    assert game.current_player.id == "bob"


def test_draw_from_discard_can_use_later_discard_cards_in_meld():
    game = make_game()

    alice = game.players[0]

    # У Alice на руках только 5♣ из будущей комбинации.
    alice.hand = [
        C(Rank.FIVE),
        C(Rank.ACE, Suit.HEARTS),
    ]

    # Горизонтальный сброс:
    #
    # [2♠] [4♣] [6♣] [K♥]
    #       ↑
    # Alice выбирает 4♣.
    #
    # При этом она автоматически забирает:
    # 4♣, 6♣, K♥
    #
    # И сразу выкладывает:
    # 4♣ + 5♣ + 6♣
    game.discard = [
        C(Rank.TWO, Suit.SPADES),
        C(Rank.FOUR),
        C(Rank.SIX),
        C(Rank.KING, Suit.HEARTS),
    ]

    prepare_alice_turn(game)

    meld = game.draw_from_discard(
        player_id="alice",

        # Берём сброс начиная с 4♣.
        discard_index=1,

        # Из руки в комбинацию идёт 5♣.
        hand_cards_for_meld=[
            C(Rank.FIVE),
        ],

        # Из забранного сброса в комбинацию
        # идут 4♣ и 6♣.
        discard_cards_for_meld=[
            C(Rank.FOUR),
            C(Rank.SIX),
        ],
    )

    # Получилась комбинация 4♣ 5♣ 6♣.
    assert {
        played.card
        for played in meld.cards
    } == {
        C(Rank.FOUR),
        C(Rank.FIVE),
        C(Rank.SIX),
    }

    # K♥ игрок тоже обязан был забрать,
    # но она не участвовала в комбинации,
    # поэтому оказывается на руке.
    assert C(
        Rank.KING,
        Suit.HEARTS,
    ) in alice.hand

    # Исходный A♥ тоже остался на руке.
    assert C(
        Rank.ACE,
        Suit.HEARTS,
    ) in alice.hand

    # 5♣ ушла из руки в комбинацию.
    assert C(Rank.FIVE) not in alice.hand

    # Из сброса исчез весь хвост начиная с 4♣.
    # Осталась только 2♠.
    assert game.discard == [
        C(Rank.TWO, Suit.SPADES),
    ]


def test_selected_discard_card_must_be_used_in_meld():
    game = make_game()

    alice = game.players[0]

    alice.hand = [
        C(Rank.FIVE),
    ]

    game.discard = [
        C(Rank.FOUR),
        C(Rank.SIX),
        C(Rank.SEVEN),
    ]

    prepare_alice_turn(game)

    with pytest.raises(GameError):
        game.draw_from_discard(
            player_id="alice",

            # Заявляем, что забираем начиная с 4♣.
            discard_index=0,

            hand_cards_for_meld=[
                C(Rank.FIVE),
            ],

            # Но пытаемся сделать 5♣ 6♣ 7♣,
            # не используя выбранную 4♣.
            discard_cards_for_meld=[
                C(Rank.SIX),
                C(Rank.SEVEN),
            ],
        )