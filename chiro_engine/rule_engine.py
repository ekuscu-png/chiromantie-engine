from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .condition_parser import ASTNode, evaluate_condition, parse_condition


@dataclass(frozen=True)
class RuleOutput:
    domain: str
    text: str


@dataclass(frozen=True)
class RuleDefinition:
    id: str
    condition: str
    output: RuleOutput
    # Optionaler Schluessel in meta.weightings (z.B. 'main_lines', 'hand_shape', 'mounts').
    # Fehlt er, wird Gewicht 1.0 verwendet.
    category: Optional[str] = None

    @staticmethod
    def from_dict(raw: dict) -> "RuleDefinition":
        output = raw["output"]
        return RuleDefinition(
            id=raw["id"],
            condition=raw["condition"],
            output=RuleOutput(domain=output["domain"], text=output["text"]),
            category=raw.get("category"),
        )


@dataclass(frozen=True)
class MatchedRule:
    id: str
    domain: str
    text: str
    weight: float


@dataclass(frozen=True)
class _CompiledRule:
    rule: RuleDefinition
    ast: ASTNode


class RuleEngine:
    def __init__(self, rules: list[RuleDefinition], weightings: Optional[dict[str, float]] = None):
        self._weightings = weightings or {}
        self._compiled: list[_CompiledRule] = []
        for rule in rules:
            try:
                ast = parse_condition(rule.condition)
            except ValueError as err:
                raise ValueError(f"Failed to parse condition for rule '{rule.id}': {err}") from err
            self._compiled.append(_CompiledRule(rule=rule, ast=ast))

    def evaluate(self, features: dict) -> list[MatchedRule]:
        """Gibt alle Regeln zurueck, deren Bedingung erfuellt ist, sortiert nach Gewicht (absteigend)."""
        matches: list[MatchedRule] = []
        for compiled in self._compiled:
            if evaluate_condition(compiled.ast, features):
                rule = compiled.rule
                weight = self._weightings.get(rule.category, 1.0) if rule.category else 1.0
                matches.append(
                    MatchedRule(id=rule.id, domain=rule.output.domain, text=rule.output.text, weight=weight)
                )
        matches.sort(key=lambda m: m.weight, reverse=True)
        return matches

    def evaluate_by_domain(self, features: dict) -> dict[str, list[MatchedRule]]:
        """Wie evaluate(), aber nach output.domain gruppiert (z.B. 'career', 'relationships')."""
        grouped: dict[str, list[MatchedRule]] = {}
        for match in self.evaluate(features):
            grouped.setdefault(match.domain, []).append(match)
        return grouped
