import random

SUITS = ["♠", "♥", "♦", "♣"]
VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

# Igual que suit_map en el script de Godot: ♠→P, ♥→C, ♦→D, ♣→T
SUIT_MAP = {"♠": "P", "♥": "C", "♦": "D", "♣": "T"}


def card_filename(card):
    """Nombre de archivo de imagen para una carta, ej: 'AP.png', '10C.png'."""
    if card is None:
        return "back.png"
    suit_letter = SUIT_MAP.get(card["suit"], "")
    return f'{card["value"]}{suit_letter}.png'


def create_deck():
    """Equivalente a _create_deck() + shuffle() en Godot."""
    deck = [{"value": v, "suit": s} for s in SUITS for v in VALUES]
    random.shuffle(deck)
    return deck


def draw_card(deck):
    """Equivalente a _draw_card()."""
    if not deck:
        print("El mazo está vacío, no se puede sacar más cartas.")
        return None
    return deck.pop()


def calculate_score(hand):
    """Equivalente a _calculate_score()."""
    score = 0
    aces = 0
    for card in hand:
        v = card["value"]
        if v in ("J", "Q", "K"):
            score += 10
        elif v == "A":
            score += 11
            aces += 1
        else:
            score += int(v)

    while score > 21 and aces > 0:
        score -= 10
        aces -= 1

    return score


def card_str(card):
    """Representación en texto de una carta, ej: '10♠', 'A♥'."""
    if card is None:
        return "??"
    return f'{card["value"]}{card["suit"]}'