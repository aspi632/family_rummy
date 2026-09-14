from app.models import Card, Rank, Suit
from app.rules import (
    is_valid_meld,
    is_valid_run,
    is_valid_set,
    can_use_discard_card_for_new_meld,
)


def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(suit=suit, rank=rank)


def test_valid_run():
    cards = [
        card(Rank.SIX),
        card(Rank.SEVEN),
        card(Rank.EIGHT),
    ]

    assert is_valid_run(cards)


def test_run_does_not_need_to_be_pre_sorted():
    cards = [
        card(Rank.EIGHT),
        card(Rank.SIX),
        card(Rank.SEVEN),
    ]

    assert is_valid_run(cards)


def test_qka_is_valid():
    cards = [
        card(Rank.QUEEN),
        card(Rank.KING),
        card(Rank.ACE),
    ]

    assert is_valid_run(cards)


def test_234_is_valid():
    cards = [
        card(Rank.TWO),
        card(Rank.THREE),
        card(Rank.FOUR),
    ]

    assert is_valid_run(cards)


def test_a23_is_invalid():
    cards = [
        card(Rank.ACE),
        card(Rank.TWO),
        card(Rank.THREE),
    ]

    assert not is_valid_run(cards)


def test_run_must_have_same_suit():
    cards = [
        Card(Suit.CLUBS, Rank.SIX),
        Card(Suit.HEARTS, Rank.SEVEN),
        Card(Suit.CLUBS, Rank.EIGHT),
    ]

    assert not is_valid_run(cards)


def test_valid_three_card_set():
    cards = [
        Card(Suit.CLUBS, Rank.JACK),
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.SPADES, Rank.JACK),
    ]

    assert is_valid_set(cards)


def test_valid_four_card_set():
    cards = [
        Card(Suit.CLUBS, Rank.JACK),
        Card(Suit.HEARTS, Rank.JACK),
        Card(Suit.SPADES, Rank.JACK),
        Card(Suit.DIAMONDS, Rank.JACK),
    ]

    assert is_valid_set(cards)


def test_two_cards_are_not_meld():
    cards = [
        card(Rank.SIX),
        card(Rank.SEVEN),
    ]

    assert not is_valid_meld(cards)


def test_discard_can_form_new_run():
    hand = [
        card(Rank.SIX),
        card(Rank.SEVEN),
        Card(Suit.HEARTS, Rank.KING),
    ]

    discard_card = card(Rank.EIGHT)

    assert can_use_discard_card_for_new_meld(
        hand,
        discard_card,
    )


def test_discard_cannot_be_taken_without_new_meld():
    hand = [
        Card(Suit.HEARTS, Rank.KING),
        Card(Suit.DIAMONDS, Rank.TWO),
    ]

    discard_card = card(Rank.EIGHT)

    assert not can_use_discard_card_for_new_meld(
        hand,
        discard_card,
    )