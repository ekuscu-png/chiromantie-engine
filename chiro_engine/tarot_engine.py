"""
Tarot-Legungen von tarot_master.json.

Anders als die anderen Domains basiert eine Tarot-Ziehung bewusst auf echtem
Zufall statt auf Foto- oder Datums-Ableitung - das ist der Kern der Tradition.
"""

from __future__ import annotations

import random

_SPREADS = {
    "daily_card": ["Thema des Tages"],
    "three_card": ["Vergangenheit", "Gegenwart", "Zukunft"],
    "yes_no": [None, None, None],
}


def all_cards(kb: dict) -> list[dict]:
    cards: list[dict] = []
    for key, data in kb["major_arcana"].items():
        cards.append({"id": key, "arcana": "major", **data})
    for suit_key, suit in kb["minor_arcana"].items():
        for rank, data in suit["cards"].items():
            cards.append({"id": f"{suit_key}_{rank}", "arcana": "minor", "suit": suit_key, **data})
    return cards


def draw_cards(kb: dict, count: int) -> list[dict]:
    pool = all_cards(kb)
    chosen = random.sample(pool, count)
    return [{**card, "reversed": random.random() < 0.5} for card in chosen]


def draw_spread(spread: str, kb: dict) -> dict | None:
    positions = _SPREADS.get(spread)
    if positions is None:
        return None
    cards = draw_cards(kb, len(positions))
    result_cards = [{**card, "position": position} for card, position in zip(cards, positions)]
    result = {"spread": spread, "cards": result_cards}
    if spread == "yes_no":
        upright_count = sum(1 for c in cards if not c["reversed"])
        result["answer"] = "Ja" if upright_count >= 2 else "Nein"
    return result
