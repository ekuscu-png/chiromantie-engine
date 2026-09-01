import json
import unittest
from datetime import date
from pathlib import Path

from chiro_engine.impulse_engine import (
    birthday_message,
    build_impulse_feed,
    pick_message,
    seasonal_message,
)

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "push_notifications_knowledge_base.json"


class PickMessageTests(unittest.TestCase):
    def test_filters_out_messages_with_placeholders(self):
        messages = ["Statisch ohne Platzhalter", "Mit {platzhalter} drin"]
        for _ in range(20):
            self.assertEqual(pick_message(messages), "Statisch ohne Platzhalter")

    def test_returns_none_if_nothing_static(self):
        self.assertIsNone(pick_message(["Nur {a}", "Nur {b}"]))

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(pick_message([]))


class SeasonalMessageTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_new_year_message(self):
        msg = seasonal_message(date(2026, 1, 1), self.kb)
        self.assertEqual(msg, self.kb["notification_categories"]["seasonal_special"]["new_year"])

    def test_ordinary_day_has_no_seasonal_message(self):
        self.assertIsNone(seasonal_message(date(2026, 5, 15), self.kb))


class BirthdayMessageTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_exact_birthday(self):
        msg = birthday_message(date(1990, 8, 23), date(2026, 8, 23), self.kb)
        self.assertEqual(msg, self.kb["notification_categories"]["seasonal_special"]["birthday"])

    def test_birthday_month_but_not_day(self):
        msg = birthday_message(date(1990, 8, 23), date(2026, 8, 1), self.kb)
        self.assertEqual(msg, self.kb["notification_categories"]["seasonal_special"]["birthday_month"])

    def test_unrelated_month(self):
        self.assertIsNone(birthday_message(date(1990, 8, 23), date(2026, 3, 1), self.kb))


class BuildImpulseFeedTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_feed_without_birth_date(self):
        feed = build_impulse_feed(date(2026, 5, 15), self.kb, moon_phase="new_moon")
        self.assertEqual(feed["date"], "2026-05-15")
        self.assertIsNone(feed["zodiac_impulse"])
        self.assertIsNone(feed["birthday_impulse"])
        self.assertIsNotNone(feed["tarot_impulse"])
        self.assertIsNotNone(feed["iching_impulse"])

    def test_feed_with_birth_date_includes_zodiac_impulse(self):
        feed = build_impulse_feed(
            date(2026, 5, 15), self.kb, moon_phase="full_moon", zodiac_sign="leo", birth_date=date(1990, 8, 23)
        )
        self.assertIsNotNone(feed["zodiac_impulse"])

    def test_every_zodiac_sign_has_at_least_one_static_message(self):
        for sign, messages in self.kb["notification_categories"]["zodiac_specific"].items():
            self.assertIsNotNone(pick_message(messages), f"Kein statischer Impuls für {sign}")


if __name__ == "__main__":
    unittest.main()
