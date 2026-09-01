import json
import unittest
from pathlib import Path

from chiro_engine.iching_engine import build_reading, cast_lines

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "iching_knowledge_base.json"


def _line(value, yang, changing=False):
    return {"value": value, "yang": yang, "changing": changing}


STUB_KB = {
    "bagua_8_trigrams": {
        "1_qian": {"name_de": "Himmel", "binary": "111"},
        "2_kun": {"name_de": "Erde", "binary": "000"},
        "3_zhen": {"name_de": "Donner", "binary": "001"},
        "4_xun": {"name_de": "Wind", "binary": "110"},
        "5_kan": {"name_de": "Wasser", "binary": "010"},
        "6_li": {"name_de": "Feuer", "binary": "101"},
        "7_gen": {"name_de": "Berg", "binary": "100"},
        "8_dui": {"name_de": "See", "binary": "011"},
    },
    "hexagrams_64": {
        "1": {
            "number": 1, "upper_trigram": "Himmel", "lower_trigram": "Himmel",
            "changing_lines": {"1": "Zeile 1", "2": "Zeile 2", "3": "Zeile 3", "4": "Zeile 4", "5": "Zeile 5", "6": "Zeile 6"},
        },
        "2": {"number": 2, "upper_trigram": "Erde", "lower_trigram": "Erde", "changing_lines": {}},
        "11": {"number": 11, "upper_trigram": "Erde", "lower_trigram": "Himmel", "changing_lines": {}},
        "46": {"number": 46, "upper_trigram": "Erde", "lower_trigram": "Wind", "changing_lines": {}},
    },
}


class HexagramLookupTests(unittest.TestCase):
    def test_all_yang_stable_is_hexagram_1(self):
        lines = [_line(7, True)] * 6
        reading = build_reading(STUB_KB, lines=lines)
        self.assertEqual(reading["hexagram_number"], 1)
        self.assertEqual(reading["changing_lines"], [])
        self.assertIsNone(reading["resulting_hexagram_number"])

    def test_all_yin_stable_is_hexagram_2(self):
        lines = [_line(8, False)] * 6
        reading = build_reading(STUB_KB, lines=lines)
        self.assertEqual(reading["hexagram_number"], 2)

    def test_lower_heaven_upper_earth_is_hexagram_11(self):
        lines = [_line(7, True)] * 3 + [_line(8, False)] * 3
        reading = build_reading(STUB_KB, lines=lines)
        self.assertEqual(reading["hexagram_number"], 11)

    def test_changing_line_produces_resulting_hexagram(self):
        lines = [_line(9, True, changing=True), _line(7, True), _line(7, True)] + [_line(8, False)] * 3
        reading = build_reading(STUB_KB, lines=lines)
        self.assertEqual(reading["hexagram_number"], 11)
        # Hexagramm 11 im Stub hat keine changing_lines-Texte hinterlegt, daher leer.
        self.assertEqual(reading["changing_lines"], [])
        self.assertEqual(reading["resulting_hexagram_number"], 46)

    def test_changing_line_text_is_looked_up_from_primary_hexagram(self):
        lines = [_line(9, True, changing=True)] + [_line(7, True)] * 5
        reading = build_reading(STUB_KB, lines=lines)
        self.assertEqual(reading["hexagram_number"], 1)
        self.assertEqual(reading["changing_lines"], [{"position": 1, "text": "Zeile 1"}])

    def test_question_is_echoed(self):
        reading = build_reading(STUB_KB, question="Soll ich den Job wechseln?", lines=[_line(7, True)] * 6)
        self.assertEqual(reading["question"], "Soll ich den Job wechseln?")

    def test_question_defaults_to_none(self):
        reading = build_reading(STUB_KB, lines=[_line(7, True)] * 6)
        self.assertIsNone(reading["question"])


class CastLinesTests(unittest.TestCase):
    def test_returns_six_lines_with_valid_values(self):
        lines = cast_lines()
        self.assertEqual(len(lines), 6)
        for line in lines:
            self.assertIn(line["value"], (6, 7, 8, 9))
            self.assertEqual(line["changing"], line["value"] in (6, 9))
            self.assertEqual(line["yang"], line["value"] in (7, 9))


class RealIChingKnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        with open(KB_PATH, encoding="utf-8") as f:
            self.kb = json.load(f)

    def test_hexagram_1_lookup_matches_real_kb(self):
        reading = build_reading(self.kb, lines=[_line(7, True)] * 6)
        self.assertEqual(reading["hexagram_number"], 1)
        self.assertEqual(reading["hexagram"]["name_de"], "Das Schöpferische")

    def test_hexagram_11_lookup_matches_real_kb(self):
        lines = [_line(7, True)] * 3 + [_line(8, False)] * 3
        reading = build_reading(self.kb, lines=lines)
        self.assertEqual(reading["hexagram_number"], 11)
        self.assertEqual(self.kb["hexagrams_64"]["11"]["name_de"], reading["hexagram"]["name_de"])

    def test_repeated_random_readings_always_resolve(self):
        for _ in range(30):
            reading = build_reading(self.kb)
            self.assertIsNotNone(reading["hexagram_number"])
            self.assertTrue(1 <= reading["hexagram_number"] <= 64)
            if reading["changing_lines"]:
                self.assertIsNotNone(reading["resulting_hexagram_number"])
                self.assertTrue(1 <= reading["resulting_hexagram_number"] <= 64)

    def test_all_64_hexagram_trigram_pairs_are_unique(self):
        pairs = {(data["upper_trigram"], data["lower_trigram"]) for data in self.kb["hexagrams_64"].values()}
        self.assertEqual(len(pairs), 64)


if __name__ == "__main__":
    unittest.main()
