import json
import unittest
from datetime import date
from pathlib import Path

from chiro_engine.journal_engine import (
    auto_insights,
    build_analysis_prompt,
    days_until_birthday,
    detect_crisis,
)

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "journal_knowledge_base.json"


class DaysUntilBirthdayTests(unittest.TestCase):
    def test_birthday_later_this_year(self):
        self.assertEqual(days_until_birthday(date(1990, 8, 23), date(2026, 8, 1)), 22)

    def test_birthday_today_is_zero(self):
        self.assertEqual(days_until_birthday(date(1990, 8, 23), date(2026, 8, 23)), 0)

    def test_birthday_already_passed_rolls_to_next_year(self):
        self.assertEqual(days_until_birthday(date(1990, 1, 5), date(2026, 8, 1)), (date(2027, 1, 5) - date(2026, 8, 1)).days)

    def test_leap_day_birthday_in_non_leap_year_falls_back_to_march_1(self):
        # sollte nicht crashen, egal welches Zieljahr kein Schaltjahr ist
        result = days_until_birthday(date(2000, 2, 29), date(2026, 1, 1))
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)


class AutoInsightsTests(unittest.TestCase):
    def test_new_moon_insight(self):
        insights = auto_insights(moon_phase="new_moon", personal_year=None, days_to_birthday=None)
        self.assertTrue(any("Neumond" in i for i in insights))

    def test_full_moon_insight(self):
        insights = auto_insights(moon_phase="full_moon", personal_year=None, days_to_birthday=None)
        self.assertTrue(any("Vollmond" in i for i in insights))

    def test_no_insight_for_ordinary_phase(self):
        insights = auto_insights(moon_phase="waxing_gibbous", personal_year=None, days_to_birthday=None)
        self.assertEqual(insights, [])

    def test_personal_year_9_and_1(self):
        self.assertTrue(any("Vollendung" in i for i in auto_insights(moon_phase="first_quarter", personal_year=9, days_to_birthday=None)))
        self.assertTrue(any("Neuanfänge" in i for i in auto_insights(moon_phase="first_quarter", personal_year=1, days_to_birthday=None)))

    def test_birthday_approaching(self):
        insights = auto_insights(moon_phase="first_quarter", personal_year=None, days_to_birthday=10)
        self.assertTrue(any("Geburtstag" in i for i in insights))

    def test_birthday_far_away_no_insight(self):
        insights = auto_insights(moon_phase="first_quarter", personal_year=None, days_to_birthday=200)
        self.assertEqual(insights, [])


class CrisisDetectionTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_detects_known_keyword_case_insensitively(self):
        self.assertTrue(detect_crisis("Ich habe manchmal Suizidgedanken.", self.kb))
        self.assertTrue(detect_crisis("ICH WILL NICHT MEHR LEBEN.", self.kb))

    def test_normal_entry_not_flagged(self):
        self.assertFalse(detect_crisis("Heute war ein guter Tag, ich war spazieren.", self.kb))


class BuildAnalysisPromptTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_fills_known_placeholders_and_keeps_entry_text_verbatim(self):
        prompt = build_analysis_prompt(
            "Heute fühle ich mich {seltsam} und unsicher.",
            self.kb,
            sun_sign="leo",
            moon_phase="new_moon",
            life_path=5,
            personal_year=1,
        )
        self.assertIn("leo", prompt)
        self.assertIn("new_moon", prompt)
        self.assertIn("Heute fühle ich mich {seltsam} und unsicher.", prompt)
        self.assertNotIn("{sun_sign}", prompt)
        self.assertNotIn("{entry_text}", prompt)


if __name__ == "__main__":
    unittest.main()
