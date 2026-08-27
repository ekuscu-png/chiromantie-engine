import unittest

from chiro_engine.condition_parser import evaluate_condition, parse_condition
from chiro_engine.rule_engine import RuleDefinition, RuleEngine, RuleOutput


class ConditionParserTests(unittest.TestCase):
    def test_simple_equality_match(self):
        ast = parse_condition("hand_shape == 'earth'")
        self.assertTrue(evaluate_condition(ast, {"hand_shape": "earth"}))

    def test_simple_equality_mismatch(self):
        ast = parse_condition("hand_shape == 'earth'")
        self.assertFalse(evaluate_condition(ast, {"hand_shape": "air"}))

    def test_not_equal(self):
        ast = parse_condition("hand_shape != 'earth'")
        self.assertTrue(evaluate_condition(ast, {"hand_shape": "air"}))

    def test_and_both_true(self):
        ast = parse_condition("mounts.jupiter.developed == 'strong' AND fate_line.end == 'to_jupiter'")
        features = {"mounts": {"jupiter": {"developed": "strong"}}, "fate_line": {"end": "to_jupiter"}}
        self.assertTrue(evaluate_condition(ast, features))

    def test_and_one_false(self):
        ast = parse_condition("mounts.jupiter.developed == 'strong' AND fate_line.end == 'to_jupiter'")
        features = {"mounts": {"jupiter": {"developed": "weak"}}, "fate_line": {"end": "to_jupiter"}}
        self.assertFalse(evaluate_condition(ast, features))

    def test_contains_match(self):
        ast = parse_condition("life_line.marks contains 'square'")
        self.assertTrue(evaluate_condition(ast, {"life_line": {"marks": ["square", "island"]}}))

    def test_contains_no_match(self):
        ast = parse_condition("life_line.marks contains 'square'")
        self.assertFalse(evaluate_condition(ast, {"life_line": {"marks": ["island"]}}))

    def test_boolean_literal(self):
        ast = parse_condition("life_line.has_break == true")
        self.assertTrue(evaluate_condition(ast, {"life_line": {"has_break": True}}))

    def test_or(self):
        ast = parse_condition("a == 'x' OR b == 'y'")
        self.assertTrue(evaluate_condition(ast, {"a": "nope", "b": "y"}))

    def test_parens_with_and_or(self):
        ast = parse_condition("(a == 'x' OR b == 'y') AND c != 'z'")
        self.assertTrue(evaluate_condition(ast, {"a": "x", "b": "nope", "c": "ok"}))

    def test_missing_nested_path_is_falsy_not_error(self):
        ast = parse_condition("missing.deeply.nested == 'x'")
        self.assertFalse(evaluate_condition(ast, {}))

    def test_empty_condition_raises(self):
        with self.assertRaises(ValueError):
            parse_condition("")

    def test_incomplete_condition_raises(self):
        with self.assertRaises(ValueError):
            parse_condition("hand_shape ==")


class RuleEngineTests(unittest.TestCase):
    def setUp(self):
        self.rules = [
            RuleDefinition("r1", "hand_shape == 'earth'", RuleOutput("personality", "Erdhand-Text"), "hand_shape"),
            RuleDefinition("r2", "hand_shape == 'air'", RuleOutput("personality", "Lufthand-Text"), "hand_shape"),
            RuleDefinition(
                "r3", "life_line.marks contains 'square'", RuleOutput("protection", "Schutz-Text"), "main_lines"
            ),
        ]
        self.weightings = {"hand_shape": 2.5, "main_lines": 3.0}
        self.engine = RuleEngine(self.rules, self.weightings)

    def test_only_matching_rules_returned(self):
        matches = self.engine.evaluate({"hand_shape": "earth", "life_line": {"marks": ["square"]}})
        self.assertEqual(len(matches), 2)

    def test_sorted_by_weight_descending(self):
        matches = self.engine.evaluate({"hand_shape": "earth", "life_line": {"marks": ["square"]}})
        self.assertEqual(matches[0].id, "r3")  # main_lines: 3.0
        self.assertEqual(matches[1].id, "r1")  # hand_shape: 2.5

    def test_evaluate_by_domain(self):
        grouped = self.engine.evaluate_by_domain({"hand_shape": "earth", "life_line": {"marks": ["square"]}})
        self.assertEqual(len(grouped["personality"]), 1)
        self.assertEqual(len(grouped["protection"]), 1)

    def test_no_match(self):
        matches = self.engine.evaluate({"hand_shape": "water"})
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
