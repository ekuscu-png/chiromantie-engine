import base64
import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import anthropic

from chiro_engine import RuleEngine
from chiro_engine.rule_engine import RuleDefinition

BASE_DIR = Path(__file__).resolve().parent
KB_PATH = BASE_DIR / "data" / "knowledge_base.json"
KB = json.loads(KB_PATH.read_text(encoding="utf-8"))
RULES = [RuleDefinition.from_dict(r) for r in KB["example_rules"]]
WEIGHTINGS = KB["meta"]["weightings"]
ENGINE = RuleEngine(RULES, WEIGHTINGS)

DOMAIN_LABELS = {
    "personality": "Persönlichkeit",
    "career": "Karriere",
    "relationships": "Beziehungen",
    "creativity": "Kreativität",
    "life_events": "Lebensereignisse",
    "protection": "Schutz",
}

MODEL = "claude-opus-5"

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "hand_shape": {
            "type": "string",
            "enum": ["earth", "air", "water", "fire", "unknown"],
            "description": "Erdhand: quadratische Handflaeche, Finger nicht laenger als Handflaeche. Lufthand: quadratisch, Finger laenger als Handflaeche. Wasserhand: laengliche Handflaeche, lange Finger. Feuerhand: laengliche Handflaeche, kurze Finger.",
        },
        "finger_tip": {
            "type": "string",
            "enum": ["conical", "square", "pointed", "spatulate", "mixed", "unknown"],
        },
        "jupiter_mount_developed": {
            "type": "string",
            "enum": ["strong", "normal", "weak", "unknown"],
            "description": "Woelbung der Handflaeche direkt unter dem Zeigefinger. Bei flachem Frontallicht meist nicht sicher beurteilbar -> unknown.",
        },
        "venus_mount_developed": {
            "type": "string",
            "enum": ["strong", "normal", "weak", "unknown"],
            "description": "Fleischiger Ballen um den Daumen, innerhalb der Lebenslinien-Kurve.",
        },
        "heart_line_end": {
            "type": "string",
            "enum": ["under_jupiter", "between_jupiter_saturn", "under_saturn", "unknown"],
            "description": "Wo die oberste horizontale Linie (Herzlinie) unter den Fingern endet.",
        },
        "fate_line_end": {
            "type": "string",
            "enum": ["to_saturn", "to_jupiter", "to_apollo", "to_mercury", "ends_at_heart", "ends_at_head", "unknown"],
        },
        "fate_line_start": {
            "type": "string",
            "enum": ["from_wrist", "from_moon", "from_life_line", "from_venus", "unknown"],
        },
        "sun_line_exists": {"type": "boolean"},
        "life_line_has_break": {"type": "boolean"},
        "life_line_marks": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["break", "island", "chain", "cross", "star", "square", "branch_up", "branch_down"],
            },
        },
        "confidence_notes": {
            "type": "string",
            "description": "Kurze ehrliche Einschaetzung (2-3 Saetze), welche Merkmale sicher und welche unsicher/geraten sind.",
        },
    },
    "required": [
        "hand_shape",
        "finger_tip",
        "jupiter_mount_developed",
        "venus_mount_developed",
        "heart_line_end",
        "fate_line_end",
        "fate_line_start",
        "sun_line_exists",
        "life_line_has_break",
        "life_line_marks",
        "confidence_notes",
    ],
    "additionalProperties": False,
}

EXTRACTION_PROMPT = """Du analysierst ein Foto einer menschlichen Handflaeche im Rahmen einer traditionellen \
Chiromantie-App (Unterhaltung/Selbstreflexion, keine Wissenschaft). Bestimme die folgenden Merkmale so genau wie \
moeglich aus dem Bild. Sei ehrlich: Wenn ein Merkmal aus einem flachen Foto ohne Schraeglicht oder Ertasten nicht \
zuverlaessig bestimmbar ist (typischerweise Bergentwicklung und exakte Linien-Endpunkte), setze den Wert auf \
"unknown" statt zu raten. Antworte ausschliesslich ueber das bereitgestellte JSON-Schema."""


def build_features(extracted: dict) -> dict:
    def val(key):
        v = extracted.get(key)
        return None if v == "unknown" else v

    return {
        "hand_shape": val("hand_shape"),
        "finger_tip": val("finger_tip"),
        "mounts": {"jupiter": {"developed": val("jupiter_mount_developed")}},
        "venus_mount": {"developed": val("venus_mount_developed")},
        "heart_line": {"end": val("heart_line_end")},
        "fate_line": {"end": val("fate_line_end"), "start": val("fate_line_start")},
        "sun_line": {"exists": extracted.get("sun_line_exists", False)},
        "life_line": {
            "has_break": extracted.get("life_line_has_break", False),
            "marks": extracted.get("life_line_marks", []),
        },
    }


def analyze_hand_image(client: anthropic.Anthropic, image_bytes: bytes, media_type: str) -> dict:
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    api_key = request.form.get("api_key", "").strip()
    if not api_key:
        return jsonify({"error": "Kein API-Key angegeben."}), 400

    left_file = request.files.get("left_image")
    right_file = request.files.get("right_image")
    if not left_file and not right_file:
        return jsonify({"error": "Mindestens ein Foto (linke oder rechte Hand) hochladen."}), 400

    client = anthropic.Anthropic(api_key=api_key)
    result = {}

    try:
        for side, file in (("left", left_file), ("right", right_file)):
            if not file or not file.filename:
                continue
            image_bytes = file.read()
            media_type = file.content_type or "image/jpeg"
            extracted = analyze_hand_image(client, image_bytes, media_type)
            features = build_features(extracted)
            matches = ENGINE.evaluate(features)
            grouped = {}
            for m in matches:
                grouped.setdefault(m.domain, []).append(
                    {"id": m.id, "text": m.text, "weight": m.weight, "domain_label": DOMAIN_LABELS.get(m.domain, m.domain)}
                )
            result[side] = {
                "extracted": extracted,
                "features": features,
                "matches": [
                    {"id": m.id, "domain": m.domain, "domain_label": DOMAIN_LABELS.get(m.domain, m.domain), "text": m.text, "weight": m.weight}
                    for m in matches
                ],
                "grouped": grouped,
                "rule_count": len(RULES),
            }
    except anthropic.AuthenticationError:
        return jsonify({"error": "API-Key ungueltig oder abgelehnt."}), 401
    except anthropic.RateLimitError:
        return jsonify({"error": "Rate-Limit erreicht. Bitte spaeter erneut versuchen."}), 429
    except anthropic.APIStatusError as e:
        return jsonify({"error": f"API-Fehler: {e.message}"}), 502
    except anthropic.APIConnectionError:
        return jsonify({"error": "Keine Verbindung zur Anthropic-API. Internetverbindung pruefen."}), 502

    if "left" in result and "right" in result:
        left_ids = {m["id"] for m in result["left"]["matches"]}
        right_ids = {m["id"] for m in result["right"]["matches"]}
        if left_ids == right_ids:
            comparison = "Beide Hände sehr ähnlich — stabile, geradlinige Entwicklung entsprechend der Grundanlagen."
        elif right_ids - left_ids:
            comparison = "Aktive Hand zeigt mehr Merkmale als die passive Hand — Person hat aus wenig viel gemacht."
        elif left_ids - right_ids:
            comparison = "Passive Hand zeigt mehr Merkmale als die aktive Hand — ungenutztes Potenzial."
        else:
            comparison = "Unterschiedliches Profil zwischen beiden Händen."
        result["comparison"] = comparison

    return jsonify(result)
