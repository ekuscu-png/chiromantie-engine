import json
import unittest
from pathlib import Path

from chiro_engine.tarot_engine import all_cards, draw_cards, draw_spread

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "tarot_knowledge_base.json"


class RealTarotKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_full_deck_has_78_cards(self):
        cards = all_cards(self.kb)
        self.assertEqual(len(cards), 78)
        self.assertEqual(len({c["id"] for c in cards}), 78)

    def test_draw_cards_returns_distinct_cards(self):
        cards = draw_cards(self.kb, 10)
        self.assertEqual(len(cards), 10)
        self.assertEqual(len({c["id"] for c in cards}), 10)
        for c in cards:
            self.assertIn("reversed", c)
            self.assertIn("meaning_upright", c)

    def test_daily_card_spread(self):
        result = draw_spread("daily_card", self.kb)
        self.assertEqual(len(result["cards"]), 1)
        self.assertEqual(result["cards"][0]["position"], "Thema des Tages")

    def test_three_card_spread_has_labeled_positions(self):
        result = draw_spread("three_card", self.kb)
        positions = [c["position"] for c in result["cards"]]
        self.assertEqual(positions, ["Vergangenheit", "Gegenwart", "Zukunft"])

    def test_yes_no_spread_has_answer(self):
        result = draw_spread("yes_no", self.kb)
        self.assertEqual(len(result["cards"]), 3)
        self.assertIn(result["answer"], ("Ja", "Nein"))

    def test_unknown_spread_returns_none(self):
        self.assertIsNone(draw_spread("does_not_exist", self.kb))


if __name__ == "__main__":
    unittest.main()
