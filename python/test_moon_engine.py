import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from chiro_engine.moon_engine import build_moon_report, moon_phase_for_date

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "moon_calendar_knowledge_base.json"


class MoonPhaseForDateTests(unittest.TestCase):
    def test_known_new_moon(self):
        # Astronomical new moon: 2024-01-11 ~11:57 UTC
        self.assertEqual(moon_phase_for_date(date(2024, 1, 11)), "new_moon")

    def test_known_full_moon(self):
        # Astronomical full moon: 2024-01-25 ~17:54 UTC
        self.assertEqual(moon_phase_for_date(date(2024, 1, 25)), "full_moon")

    def test_cycle_returns_to_new_moon_after_one_synodic_month(self):
        start = date(2024, 1, 11)
        later = start + timedelta(days=29)
        self.assertEqual(moon_phase_for_date(later), "new_moon")

    def test_every_phase_is_reachable_across_a_month(self):
        d = date(2024, 1, 1)
        seen = set()
        for _ in range(30):
            seen.add(moon_phase_for_date(d))
            d += timedelta(days=1)
        self.assertEqual(len(seen), 8)


class BuildMoonReportTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_report_includes_phase_data_from_kb(self):
        report = build_moon_report(date(2024, 1, 11), self.kb)
        self.assertEqual(report["phase"], "new_moon")
        self.assertEqual(report["phase_data"]["name_de"], "Neumond")
        self.assertIn("practical_tips", report["phase_data"])


if __name__ == "__main__":
    unittest.main()
