import json
import unittest
from datetime import date
from pathlib import Path

from chiro_engine.zodiac_engine import (
    build_zodiac_report,
    chinese_animal_for_year,
    compatibility_report,
    western_sign_for_date,
)

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "zodiac_knowledge_base.json"


class WesternSignForDateTests(unittest.TestCase):
    def test_mid_range_dates(self):
        self.assertEqual(western_sign_for_date(3, 25), "aries")
        self.assertEqual(western_sign_for_date(7, 1), "cancer")
        self.assertEqual(western_sign_for_date(11, 30), "sagittarius")

    def test_boundary_dates(self):
        self.assertEqual(western_sign_for_date(3, 22), "aries")
        self.assertEqual(western_sign_for_date(4, 20), "aries")
        self.assertEqual(western_sign_for_date(4, 21), "taurus")

    def test_leo_virgo_cusp_matches_the_other_common_convention(self):
        self.assertEqual(western_sign_for_date(8, 23), "leo")
        self.assertEqual(western_sign_for_date(8, 24), "virgo")

    def test_capricorn_wraps_year_boundary(self):
        self.assertEqual(western_sign_for_date(12, 25), "capricorn")
        self.assertEqual(western_sign_for_date(1, 5), "capricorn")
        self.assertEqual(western_sign_for_date(1, 20), "capricorn")
        self.assertEqual(western_sign_for_date(1, 21), "aquarius")

    def test_every_day_of_year_maps_to_exactly_one_sign(self):
        d = date(2023, 1, 1)
        seen = set()
        while d.year == 2023:
            seen.add(western_sign_for_date(d.month, d.day))
            d = date.fromordinal(d.toordinal() + 1)
        self.assertEqual(len(seen), 12)


class ChineseAnimalForYearTests(unittest.TestCase):
    def setUp(self):
        self.kb = {
            "chinese_zodiac": {
                "animals": {
                    "rat": {"years": [1996, 2008, 2020]},
                    "ox": {"years": [1997, 2009, 2021]},
                }
            }
        }

    def test_known_year(self):
        self.assertEqual(chinese_animal_for_year(2020, self.kb), "rat")

    def test_extrapolates_beyond_listed_years(self):
        self.assertEqual(chinese_animal_for_year(2032, self.kb), "rat")
        self.assertEqual(chinese_animal_for_year(1984, self.kb), "rat")


class RealKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_all_144_compatibility_pairs_reachable(self):
        signs = list(self.kb["western_zodiac_signs"].keys())
        self.assertEqual(len(signs), 12)
        for s1 in signs:
            for s2 in signs:
                self.assertIsNotNone(compatibility_report(s1, s2, self.kb), f"missing pair {s1}_{s2}")

    def test_build_zodiac_report_for_real_date(self):
        report = build_zodiac_report(date(1990, 8, 15), self.kb)
        self.assertEqual(report["sign"], "leo")
        self.assertEqual(report["sign_data"]["name_de"], self.kb["western_zodiac_signs"]["leo"]["name_de"])
        self.assertIsNotNone(report["chinese_animal"])
        self.assertFalse(report["chinese_new_year_caveat"])

    def test_january_birth_flags_new_year_caveat(self):
        report = build_zodiac_report(date(1990, 1, 25), self.kb)
        self.assertTrue(report["chinese_new_year_caveat"])


if __name__ == "__main__":
    unittest.main()
