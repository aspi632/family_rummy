from itertools import combinations

from app.models import Card, MeldType


def is_valid_set(cards: list[Card]) -> bool:
    if len(cards) not in (3, 4):
        return False

    ranks = {card.rank for card in cards}
    suits = {card.suit for card in cards}

    return len(ranks) == 1 and len(suits) == len(cards)


def is_valid_run(cards: list[Card]) -> bool:
    if len(cards) < 3:
        return False

    if len({card.suit for card in cards}) != 1:
        return False

    ranks = sorted(card.rank for card in cards)

    if len(set(ranks)) != len(ranks):
        return False

    return all(
        ranks[i] + 1 == ranks[i + 1]
        for i in range(len(ranks) - 1)
    )


def get_meld_type(cards: list[Card]):
    if is_valid_set(cards):
        return MeldType.SET

    if is_valid_run(cards):
        return MeldType.RUN

    return None


def is_valid_meld(cards: list[Card]) -> bool:
    return get_meld_type(cards) is not None


def can_extend_meld(
    existing_cards: list[Card],
    new_card: Card,
) -> bool:
    return is_valid_meld(existing_cards + [new_card])


def can_use_discard_card_for_new_meld(
    hand: list[Card],
    discard_card: Card,
) -> bool:
    """
    discard_card must immediately create a NEW meld.

    Existing melds on the table are deliberately not considered.
    """

    for size in range(2, len(hand) + 1):
        for hand_cards in combinations(hand, size):
            if is_valid_meld(list(hand_cards) + [discard_card]):
                return True

    return False