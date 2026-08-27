import json
import unittest
from pathlib import Path

from chiro_engine.condition_parser import evaluate_condition, parse_condition
from chiro_engine.rule_engine import RuleDefinition, RuleEngine, RuleOutput
from chiro_engine.physiognomy_engine import (
    age_phase_interpretation,
    build_compound_features,
    direct_interpretations,
    load_compound_rules,
)

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "physiognomy_knowledge_base.json"


class SingleEqualsOperatorTests(unittest.TestCase):
    def test_single_equals_matches_like_double_equals(self):
        ast = parse_condition("face_shape='oval'")
        self.assertTrue(evaluate_condition(ast, {"face_shape": "oval"}))

    def test_single_equals_and_chain(self):
        ast = parse_condition("eyes='almond' AND lips='full'")
        self.assertTrue(evaluate_condition(ast, {"eyes": "almond", "lips": "full"}))
        self.assertFalse(evaluate_condition(ast, {"eyes": "almond", "lips": "thin"}))


class RuleEngineSkipsMalformedRulesTests(unittest.TestCase):
    def test_malformed_condition_is_skipped_not_raised(self):
        rules = [
            RuleDefinition("good", "face_shape == 'oval'", RuleOutput("personality", "ok"), "personality"),
            RuleDefinition("bad", "user.age BETWEEN 15 AND 30", RuleOutput("personality", "bad"), "personality"),
        ]
        engine = RuleEngine(rules)
        self.assertEqual(engine.skipped_rule_ids, ["bad"])
        matches = engine.evaluate({"face_shape": "oval"})
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, "good")


class LoadCompoundRulesTests(unittest.TestCase):
    def setUp(self):
        self.kb = {
            "meta": {"weightings": {}},
            "compound_rules_200plus": {
                "personality_rules": [{"id": "p1", "condition": "face_shape='oval'", "output": "harmonisch"}],
                "career_rules": [{"id": "c1", "condition": "forehead='wide'", "output": "fuehrung"}],
                "wealth_rules": [],
                "relationship_rules": [],
                "health_rules": [],
                "life_phase_rules_age_based": [],
                "compound_lucky_signs": [],
            },
            "face_shapes_extended": {"oval": {"element": "metal"}},
        }

    def test_translates_groups_into_domains(self):
        rules = load_compound_rules(self.kb)
        by_id = {r.id: r for r in rules}
        self.assertEqual(by_id["p1"].output.domain, "personality")
        self.assertEqual(by_id["c1"].output.domain, "career")
        self.assertEqual(by_id["p1"].output.text, "harmonisch")

    def test_rules_are_evaluable_by_rule_engine(self):
        engine = RuleEngine(load_compound_rules(self.kb))
        matches = engine.evaluate(build_compound_features({"face_shape": "oval"}, self.kb))
        self.assertEqual([m.id for m in matches], ["p1"])


class DirectInterpretationsTests(unittest.TestCase):
    def setUp(self):
        self.kb = {
            "face_shapes_extended": {
                "oval": {"personality_long": "Harmonisch.", "wealth_pattern": "Steter Zuwachs.", "element": "metal"}
            },
            "three_courts_san_ting": {"balance_analysis": {"all_three_equal": "Ausgewogen."}},
            "twelve_palaces_detailed": {
                "1_ming_gong_life_palace": {"interpretations": {"wide_bright": "Weite Perspektive."}}
            },
            "forehead_deep": {"height_detailed": {"high": {"personality": "Intelligent."}}},
            "moles_extended_positions": {"positions": {"chin_center": {"meaning": "Spaetes Glueck."}}},
        }

    def test_face_shape_and_san_ting_and_moles_are_looked_up(self):
        extracted = {
            "face_shape": "oval",
            "san_ting_balance": "all_three_equal",
            "glabella_area": "wide_bright",
            "forehead_height": "high",
            "moles": ["chin_center"],
        }
        results = direct_interpretations(extracted, self.kb)
        sections = {r["section"]: r["text"] for r in results}
        self.assertIn("Harmonisch.", sections["Gesichtsform"])
        self.assertEqual(sections["Drei Höfe (San Ting) – Balance"], "Ausgewogen.")
        self.assertEqual(sections["Palast des Lebens (Yin Tang)"], "Weite Perspektive.")
        self.assertEqual(sections["Stirn – Höhe"], "Intelligent.")
        self.assertEqual(sections["Muttermal: chin_center"], "Spaetes Glueck.")

    def test_unknown_values_are_skipped(self):
        results = direct_interpretations({"face_shape": "unknown", "moles": ["unknown"]}, self.kb)
        self.assertEqual(results, [])


class AgePhaseInterpretationTests(unittest.TestCase):
    def setUp(self):
        self.kb = {
            "compound_rules_200plus": {
                "life_phase_rules_age_based": [
                    {"id": "l001", "condition": "user.age BETWEEN 15 AND 30", "output": "Stirn-Phase."},
                    {"id": "l002", "condition": "user.age BETWEEN 31 AND 34", "output": "Augenbrauen-Phase."},
                    {"id": "l003", "condition": "user.age BETWEEN 35 AND 40", "output": "Augen-Phase."},
                    {"id": "l004", "condition": "user.age BETWEEN 41 AND 50", "output": "Nasen-Phase."},
                    {"id": "l005", "condition": "user.age BETWEEN 51 AND 55", "output": "Philtrum-Phase."},
                    {"id": "l006", "condition": "user.age BETWEEN 56 AND 65", "output": "Mund-Phase."},
                    {"id": "l007", "condition": "user.age BETWEEN 66 AND 75", "output": "Kinn-Phase."},
                    {"id": "l008", "condition": "user.age BETWEEN 76 AND 100", "output": "Rand-Zonen aktiv."},
                ]
            }
        }

    def test_age_in_second_range(self):
        result = age_phase_interpretation(32, self.kb)
        self.assertEqual(result["text"], "Augenbrauen-Phase.")

    def test_age_below_all_ranges_returns_none(self):
        self.assertIsNone(age_phase_interpretation(5, self.kb))


class RealKnowledgeBaseLoadsCleanlyTests(unittest.TestCase):
    """Smoke test against the actual shipped KB file, not a stub."""

    def test_kb_loads_and_engine_initializes(self):
        with open(KB_PATH, encoding="utf-8") as f:
            kb = json.load(f)
        rules = load_compound_rules(kb)
        self.assertGreater(len(rules), 0)
        engine = RuleEngine(rules, kb["meta"]["weightings"])
        # A handful of hand-authored rules use unsupported syntax (BETWEEN, >=)
        # and are expected to be skipped rather than crash the engine.
        self.assertLess(len(engine.skipped_rule_ids), len(rules))

    def test_direct_interpretations_handle_full_extraction(self):
        with open(KB_PATH, encoding="utf-8") as f:
            kb = json.load(f)
        extracted = {"face_shape": "square", "forehead_height": "medium", "moles": ["chin_center"]}
        results = direct_interpretations(extracted, kb)
        self.assertTrue(any(r["section"] == "Gesichtsform" for r in results))


if __name__ == "__main__":
    unittest.main()
