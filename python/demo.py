import json
from pathlib import Path

from chiro_engine import RuleEngine
from chiro_engine.rule_engine import RuleDefinition

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"


def main() -> None:
    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))

    rules = [RuleDefinition.from_dict(r) for r in kb["example_rules"]]
    weightings = kb["meta"]["weightings"]

    engine = RuleEngine(rules, weightings)

    # Beispiel-Features, wie sie aus der Bildanalyse (Schritt 3 in app_workflow) kommen koennten.
    # Achtung: example_rules referenziert sowohl `mounts.jupiter.developed` als auch das
    # eigenstaendige Feld `venus_mount.developed` (statt `mounts.venus.developed`) - diese
    # Inkonsistenz stammt aus der Quelldatei und wird hier bewusst so gespiegelt.
    sample_features = {
        "hand_shape": "earth",
        "finger_tip": "conical",
        "mounts": {"jupiter": {"developed": "strong"}},
        "venus_mount": {"developed": "strong"},
        "fate_line": {"end": "to_jupiter"},
        "heart_line": {"end": "under_jupiter"},
        "sun_line": {"exists": True},
        "life_line": {"has_break": True, "marks": ["square"]},
    }

    matches = engine.evaluate(sample_features)

    print(f"{len(matches)} Regel(n) getroffen:\n")
    for m in matches:
        print(f"[{m.domain}] (weight {m.weight}) {m.id}")
        print(f"  -> {m.text}\n")


if __name__ == "__main__":
    main()
