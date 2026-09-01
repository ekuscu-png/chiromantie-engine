import base64
import json
import os
from datetime import date
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from PIL import Image, ImageOps, UnidentifiedImageError

import anthropic

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

from chiro_engine import RuleEngine
from chiro_engine.rule_engine import RuleDefinition
from chiro_engine.physiognomy_engine import (
    age_phase_interpretation,
    build_compound_features,
    direct_interpretations,
    load_compound_rules,
)
from chiro_engine.zodiac_engine import build_zodiac_report, compatibility_report, western_sign_for_date
from chiro_engine.moon_engine import build_moon_report, moon_phase_for_date
from chiro_engine.tarot_engine import draw_spread
from chiro_engine.numerology_engine import (
    build_numerology_report,
    life_path_number,
    numerology_compatibility,
    personal_year_number,
)
from chiro_engine.iching_engine import build_reading
from chiro_engine.journal_engine import auto_insights, build_analysis_prompt, days_until_birthday, detect_crisis
from chiro_engine.impulse_engine import build_impulse_feed

BASE_DIR = Path(__file__).resolve().parent
KB_PATH = BASE_DIR / "data" / "knowledge_base.json"
KB = json.loads(KB_PATH.read_text(encoding="utf-8"))
RULES = [RuleDefinition.from_dict(r) for r in KB["example_rules"]]
WEIGHTINGS = KB["meta"]["weightings"]
ENGINE = RuleEngine(RULES, WEIGHTINGS)

PHYSIOGNOMY_KB_PATH = BASE_DIR / "data" / "physiognomy_knowledge_base.json"
PHYSIOGNOMY_KB = json.loads(PHYSIOGNOMY_KB_PATH.read_text(encoding="utf-8"))
PHYSIOGNOMY_RULES = load_compound_rules(PHYSIOGNOMY_KB)
PHYSIOGNOMY_ENGINE = RuleEngine(PHYSIOGNOMY_RULES, PHYSIOGNOMY_KB["meta"]["weightings"])

ZODIAC_KB_PATH = BASE_DIR / "data" / "zodiac_knowledge_base.json"
ZODIAC_KB = json.loads(ZODIAC_KB_PATH.read_text(encoding="utf-8"))

MOON_KB_PATH = BASE_DIR / "data" / "moon_calendar_knowledge_base.json"
MOON_KB = json.loads(MOON_KB_PATH.read_text(encoding="utf-8"))

TAROT_KB_PATH = BASE_DIR / "data" / "tarot_knowledge_base.json"
TAROT_KB = json.loads(TAROT_KB_PATH.read_text(encoding="utf-8"))

NUMEROLOGY_KB_PATH = BASE_DIR / "data" / "numerology_knowledge_base.json"
NUMEROLOGY_KB = json.loads(NUMEROLOGY_KB_PATH.read_text(encoding="utf-8"))

ICHING_KB_PATH = BASE_DIR / "data" / "iching_knowledge_base.json"
ICHING_KB = json.loads(ICHING_KB_PATH.read_text(encoding="utf-8"))

JOURNAL_KB_PATH = BASE_DIR / "data" / "journal_knowledge_base.json"
JOURNAL_KB = json.loads(JOURNAL_KB_PATH.read_text(encoding="utf-8"))

IMPULSE_KB_PATH = BASE_DIR / "data" / "push_notifications_knowledge_base.json"
IMPULSE_KB = json.loads(IMPULSE_KB_PATH.read_text(encoding="utf-8"))

DOMAIN_LABELS = {
    "personality": "Persönlichkeit",
    "career": "Karriere",
    "relationships": "Beziehungen",
    "creativity": "Kreativität",
    "life_events": "Lebensereignisse",
    "protection": "Schutz",
}

PHYSIOGNOMY_DOMAIN_LABELS = {
    "personality": "Persönlichkeit",
    "career": "Karriere",
    "wealth": "Vermögen",
    "relationships": "Beziehungen",
    "health": "Gesundheit",
    "life_phase": "Lebensphase",
    "lucky_signs": "Glückszeichen",
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


_MOLE_POSITIONS = [
    "forehead_center", "forehead_center_lower_between_brows",
    "eyebrow_head_left", "eyebrow_tail_left", "eyebrow_head_right", "eyebrow_tail_right",
    "eye_corner_outer_left_wife_palace", "eye_corner_outer_right",
    "nose_root_between_eyes", "nose_bridge_middle", "nose_tip_center", "nose_wing_left", "nose_wing_right",
    "cheek_upper_left", "cheek_upper_right", "cheek_lower_left", "cheek_lower_right",
    "philtrum_middle", "upper_lip_center", "lower_lip_center", "mouth_corner_left", "mouth_corner_right",
    "chin_center", "chin_left", "chin_right", "earlobe_left", "earlobe_right",
    "other_position", "none",
]

EXTRACTION_SCHEMA_FACE = {
    "type": "object",
    "properties": {
        "face_shape": {
            "type": "string",
            "enum": [
                "oval", "round", "square", "rectangular", "heart", "triangular_wide_jaw", "diamond",
                "trapezoid_wide_forehead", "long_narrow", "pear", "round_with_high_cheekbones",
                "square_with_prominent_forehead", "unknown",
            ],
        },
        "face_symmetry": {"type": "string", "enum": ["symmetric", "mild_asymmetric", "asymmetric", "unknown"]},
        "san_ting_balance": {
            "type": "string",
            "description": "Balance der drei Gesichts-Hoefe (Haaransatz-Brauen / Brauen-Nasenspitze / Nasenspitze-Kinn).",
            "enum": [
                "all_three_equal", "upper_dominant_only", "middle_dominant_only", "lower_dominant_only",
                "upper_and_middle_dominant", "middle_and_lower_dominant", "upper_and_lower_dominant", "unknown",
            ],
        },
        "glabella_area": {
            "type": "string",
            "description": "Bereich zwischen den Augenbrauen (Yin Tang / Palast des Lebens).",
            "enum": ["wide_bright", "narrow", "vertical_lines", "mole", "sunken", "unknown"],
        },
        "forehead_height": {"type": "string", "enum": ["very_high", "high", "medium", "low", "very_low", "unknown"]},
        "forehead_shape": {
            "type": "string",
            "enum": ["round_convex", "square_flat", "arched_protruding", "receding", "sloping", "flat_wide", "unknown"],
        },
        "forehead_width": {"type": "string", "enum": ["very_wide", "wide", "medium", "narrow", "very_narrow", "unknown"]},
        "eyebrows_length": {
            "type": "string",
            "enum": ["much_longer_than_eye", "longer_than_eye", "same_as_eye", "shorter_than_eye", "much_shorter", "unknown"],
        },
        "eyebrows_thickness": {
            "type": "string",
            "enum": ["very_thick", "thick", "medium", "thin", "very_thin", "sparse_gappy", "unknown"],
        },
        "eyebrows_shape": {
            "type": "string",
            "enum": [
                "straight_horizontal", "arched_moderate", "arched_high_dramatic", "downturned_ends",
                "upturned_ends", "wild_bushy", "one_arched_one_straight", "unknown",
            ],
        },
        "eyebrows_spacing": {
            "type": "string",
            "enum": ["very_wide_apart", "wide_apart", "medium", "close_together", "monobrow", "unknown"],
        },
        "eyes_size": {"type": "string", "enum": ["very_large", "large", "medium", "small", "very_small", "unknown"]},
        "eyes_shape": {
            "type": "string",
            "enum": [
                "almond", "round_open", "narrow_slit", "hooded_droopy_lid", "downturned_corners",
                "upturned_corners", "asymmetric_eyes", "unknown",
            ],
        },
        "eyes_distance": {
            "type": "string",
            "enum": ["very_wide_apart", "wide", "medium", "close_together", "very_close", "unknown"],
        },
        "eyes_expression": {
            "type": "string",
            "enum": [
                "bright_clear_lively", "dull_matte", "fiery_intense", "cold_hard", "watery_moist",
                "sunken_hollow", "bloodshot_red", "yellowish_whites", "unknown",
            ],
        },
        "dark_circles_under_eyes": {"type": "string", "enum": ["deep", "mild", "none", "unknown"]},
        "crows_feet": {"type": "string", "enum": ["deep_many", "some", "none", "unknown"]},
        "nose_length": {"type": "string", "enum": ["very_long", "long", "medium", "short", "very_short", "unknown"]},
        "nose_bridge": {
            "type": "string",
            "enum": [
                "very_high_straight", "high_straight", "medium_straight", "low_flat", "humped_aquiline",
                "dented_saddle", "very_visible_bone", "curved_left_or_right", "unknown",
            ],
        },
        "nose_tip": {
            "type": "string",
            "enum": [
                "round_fleshy_ideal", "round_bulbous_very_large", "pointed_sharp", "upturned_ski_slope",
                "downturned_hooked", "split_bifid", "square_flat", "unknown",
            ],
        },
        "nose_wings": {
            "type": "string",
            "enum": ["very_full_thick", "full_fleshy", "medium", "narrow", "very_narrow", "asymmetric", "unknown"],
        },
        "nose_nostrils": {
            "type": "string",
            "enum": ["very_small_hidden", "small_hidden", "medium_visible", "large_visible", "very_large_flaring", "unknown"],
        },
        "nose_root_shan_gen": {
            "type": "string",
            "enum": ["very_high_wide", "high_wide", "medium", "low_sunken", "with_horizontal_line", "with_mole", "unknown"],
        },
        "philtrum_length": {
            "type": "string",
            "enum": ["very_deep_long", "long_clear_deep", "medium", "short_flat", "very_flat_absent", "unknown"],
        },
        "mouth_size": {
            "type": "string",
            "enum": ["very_large", "large", "medium_symmetric", "small", "very_small", "unknown"],
        },
        "lips_thickness": {
            "type": "string",
            "enum": [
                "very_full_both", "full_both", "medium_both", "thin_both", "very_thin_both",
                "upper_much_fuller", "upper_fuller", "lower_much_fuller", "lower_fuller", "unknown",
            ],
        },
        "lips_shape": {
            "type": "string",
            "enum": [
                "cupids_bow_pronounced", "straight_upper_lip", "wide_flat_lips", "small_pointed_lips",
                "heart_shaped_lips", "unknown",
            ],
        },
        "lips_corners": {
            "type": "string",
            "enum": ["very_upturned", "upturned", "neutral", "downturned", "very_downturned", "unknown"],
        },
        "lips_color": {
            "type": "string",
            "enum": ["natural_healthy_pink", "pale_lips", "very_red", "bluish_lips", "purplish_lips", "dry_cracked_lips", "unknown"],
        },
        "chin_shape": {
            "type": "string",
            "enum": [
                "very_round_full", "round_full", "square_angular", "very_square", "pointed_sharp", "very_pointed",
                "double_chin_natural", "protruding_thrust_forward", "receding_weak", "very_receding",
                "cleft_dimple", "asymmetric_chin", "unknown",
            ],
        },
        "jaw_shape": {
            "type": "string",
            "enum": ["very_wide_strong", "wide_strong", "medium", "narrow", "very_narrow_delicate", "very_angular_defined", "unknown"],
        },
        "cheekbone_prominence": {"type": "string", "enum": ["high_prominent", "medium", "low_flat", "unknown"]},
        "cheeks_fullness": {"type": "string", "enum": ["full", "average", "hollow", "unknown"]},
        "ears_size": {
            "type": "string",
            "enum": ["very_large_prominent", "large", "medium", "small", "very_small", "unknown"],
        },
        "ears_position": {
            "type": "string",
            "enum": ["very_high_above_brow_level", "high_at_brow_level", "medium_at_eye_level", "low_below_eye_level", "very_low", "unknown"],
        },
        "ears_earlobe": {
            "type": "string",
            "enum": [
                "very_large_fleshy_pendulous", "large_fleshy", "medium_fleshy", "small_thin",
                "absent_no_lobe", "attached_lobe", "free_lobe", "unknown",
            ],
        },
        "ears_shape": {
            "type": "string",
            "enum": [
                "pointed_elf_ears", "rounded_soft", "very_thick_ears", "very_thin_ears",
                "flat_close_to_head", "protruding_sticking_out", "unknown",
            ],
        },
        "skin_color": {
            "type": "string",
            "enum": [
                "clear_luminous_glowing", "healthy_pink_smooth", "sallow_yellowish", "very_pale",
                "red_veined_ruddy", "gray_dull", "bluish_under_eyes", "greenish_tinge",
                "very_dark_under_skin", "unknown",
            ],
        },
        "skin_texture": {
            "type": "string",
            "enum": ["very_fine_smooth", "fine_smooth", "medium", "rough", "very_rough_thick", "very_dry", "very_oily", "combination", "unknown"],
        },
        "moles": {
            "type": "array",
            "description": "Sichtbare Muttermale, jeweils der naechstgelegenen Position zugeordnet. Leer/['none'] wenn keine sichtbar.",
            "items": {"type": "string", "enum": _MOLE_POSITIONS},
        },
        "confidence_notes": {
            "type": "string",
            "description": "Kurze ehrliche Einschaetzung (2-3 Saetze), welche Merkmale sicher und welche unsicher/geraten sind.",
        },
    },
    "required": [
        "face_shape", "face_symmetry", "san_ting_balance", "glabella_area",
        "forehead_height", "forehead_shape", "forehead_width",
        "eyebrows_length", "eyebrows_thickness", "eyebrows_shape", "eyebrows_spacing",
        "eyes_size", "eyes_shape", "eyes_distance", "eyes_expression", "dark_circles_under_eyes", "crows_feet",
        "nose_length", "nose_bridge", "nose_tip", "nose_wings", "nose_nostrils", "nose_root_shan_gen",
        "philtrum_length", "mouth_size", "lips_thickness", "lips_shape", "lips_corners", "lips_color",
        "chin_shape", "jaw_shape", "cheekbone_prominence", "cheeks_fullness",
        "ears_size", "ears_position", "ears_earlobe", "ears_shape",
        "skin_color", "skin_texture", "moles", "confidence_notes",
    ],
    "additionalProperties": False,
}

EXTRACTION_PROMPT_FACE = """Du analysierst ein Foto eines menschlichen Gesichts im Rahmen einer traditionellen \
Physiognomik-App (Mian Xiang / Samudrika Shastra / westliche Tradition; Unterhaltung/Selbstreflexion, keine \
Wissenschaft - Ausnahme sind rein beschreibende Merkmale wie Hautfarbe/-textur). Bestimme die Merkmale so genau wie \
moeglich aus dem Bild, idealerweise Frontalaufnahme mit neutralem Ausdruck und gutem Licht. Sei ehrlich: Wenn ein \
Merkmal (z.B. exakte Balance der drei Gesichts-Hoefe, feine Hautfarb-Nuancen) aus dem Foto nicht zuverlaessig \
bestimmbar ist, setze den Wert auf "unknown" statt zu raten. Erkenne nur tatsaechlich sichtbare Muttermale, \
erfinde keine. Antworte ausschliesslich ueber das bereitgestellte JSON-Schema."""


def build_physiognomy_output(extracted: dict, age: int | None) -> dict:
    direct = direct_interpretations(extracted, PHYSIOGNOMY_KB)
    if age is not None:
        phase = age_phase_interpretation(age, PHYSIOGNOMY_KB)
        if phase:
            direct.insert(0, phase)

    compound_features = build_compound_features(extracted, PHYSIOGNOMY_KB)
    matches = PHYSIOGNOMY_ENGINE.evaluate(compound_features)
    grouped = {}
    for m in matches:
        grouped.setdefault(m.domain, []).append(
            {"id": m.id, "text": m.text, "weight": m.weight, "domain_label": PHYSIOGNOMY_DOMAIN_LABELS.get(m.domain, m.domain)}
        )

    return {
        "extracted": extracted,
        "direct_interpretations": direct,
        "matches": [
            {
                "id": m.id, "domain": m.domain,
                "domain_label": PHYSIOGNOMY_DOMAIN_LABELS.get(m.domain, m.domain),
                "text": m.text, "weight": m.weight,
            }
            for m in matches
        ],
        "grouped": grouped,
        "rule_count": len(PHYSIOGNOMY_RULES),
    }


def normalize_image(image_bytes: bytes) -> bytes:
    """Handy-Fotos kommen in allen moeglichen Formen: HEIC (iPhone-Standard), falsch
    rotiert (EXIF-Orientierung wird von Kamera-Apps oft nur als Metadaten-Flag statt
    gedrehter Pixel gespeichert), WEBP, RGBA/CMYK-Farbmodi. Ohne Normalisierung sieht
    das Vision-Modell teils ein unlesbares oder seitlich verdrehtes Bild und faellt
    dann bei mehreren Personen auf aehnliche generische Schaetzwerte zurueck. Deshalb
    wird jedes Foto serverseitig auf ein aufrecht stehendes RGB-JPEG normalisiert."""
    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
    except UnidentifiedImageError as err:
        raise ValueError("Foto konnte nicht gelesen werden. Bitte ein JPEG- oder PNG-Foto verwenden.") from err
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def analyze_face_image(client: anthropic.Anthropic, image_bytes: bytes) -> dict:
    image_data = base64.standard_b64encode(normalize_image(image_bytes)).decode("utf-8")
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": EXTRACTION_PROMPT_FACE},
                ],
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA_FACE}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def analyze_hand_image(client: anthropic.Anthropic, image_bytes: bytes) -> dict:
    image_data = base64.standard_b64encode(normalize_image(image_bytes)).decode("utf-8")
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    api_key = request.form.get("api_key", "").strip() or os.environ.get("ANTHROPIC_API_KEY", "").strip()
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
            extracted = analyze_hand_image(client, image_bytes)
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
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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


@app.post("/api/analyze-face")
def analyze_face():
    api_key = request.form.get("api_key", "").strip() or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "Kein API-Key angegeben."}), 400

    face_file = request.files.get("face_image")
    if not face_file or not face_file.filename:
        return jsonify({"error": "Bitte ein Gesichtsfoto hochladen."}), 400

    age_raw = request.form.get("age", "").strip()
    age = None
    if age_raw:
        try:
            age = int(age_raw)
        except ValueError:
            return jsonify({"error": "Alter muss eine Zahl sein."}), 400

    client = anthropic.Anthropic(api_key=api_key)

    try:
        image_bytes = face_file.read()
        extracted = analyze_face_image(client, image_bytes)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except anthropic.AuthenticationError:
        return jsonify({"error": "API-Key ungueltig oder abgelehnt."}), 401
    except anthropic.RateLimitError:
        return jsonify({"error": "Rate-Limit erreicht. Bitte spaeter erneut versuchen."}), 429
    except anthropic.APIStatusError as e:
        return jsonify({"error": f"API-Fehler: {e.message}"}), 502
    except anthropic.APIConnectionError:
        return jsonify({"error": "Keine Verbindung zur Anthropic-API. Internetverbindung pruefen."}), 502

    return jsonify(build_physiognomy_output(extracted, age))


@app.post("/api/zodiac")
def zodiac():
    birth_raw = request.form.get("birth_date", "").strip()
    if not birth_raw:
        return jsonify({"error": "Bitte ein Geburtsdatum angeben."}), 400
    try:
        birth_date = date.fromisoformat(birth_raw)
    except ValueError:
        return jsonify({"error": "Ungueltiges Geburtsdatum."}), 400

    report = build_zodiac_report(birth_date, ZODIAC_KB)

    partner_raw = request.form.get("partner_birth_date", "").strip()
    if partner_raw:
        try:
            partner_date = date.fromisoformat(partner_raw)
        except ValueError:
            return jsonify({"error": "Ungueltiges Geburtsdatum der Partnerin/des Partners."}), 400
        partner_sign = western_sign_for_date(partner_date.month, partner_date.day)
        report["partner_sign"] = partner_sign
        report["partner_sign_name"] = ZODIAC_KB["western_zodiac_signs"][partner_sign]["name_de"]
        report["compatibility"] = compatibility_report(report["sign"], partner_sign, ZODIAC_KB)

    return jsonify(report)


@app.post("/api/moon")
def moon():
    date_raw = request.form.get("date", "").strip()
    target_date = date.today()
    if date_raw:
        try:
            target_date = date.fromisoformat(date_raw)
        except ValueError:
            return jsonify({"error": "Ungueltiges Datum."}), 400

    return jsonify(build_moon_report(target_date, MOON_KB))


@app.post("/api/tarot")
def tarot():
    spread = request.form.get("spread", "daily_card").strip()
    result = draw_spread(spread, TAROT_KB)
    if result is None:
        return jsonify({"error": "Unbekannte Legung."}), 400
    return jsonify(result)


@app.post("/api/numerology")
def numerology():
    name = request.form.get("name", "").strip()
    if not name:
        return jsonify({"error": "Bitte einen vollen Namen angeben."}), 400

    birth_raw = request.form.get("birth_date", "").strip()
    if not birth_raw:
        return jsonify({"error": "Bitte ein Geburtsdatum angeben."}), 400
    try:
        birth_date = date.fromisoformat(birth_raw)
    except ValueError:
        return jsonify({"error": "Ungueltiges Geburtsdatum."}), 400

    report = build_numerology_report(name, birth_date, NUMEROLOGY_KB)

    partner_name = request.form.get("partner_name", "").strip()
    partner_birth_raw = request.form.get("partner_birth_date", "").strip()
    if partner_name and partner_birth_raw:
        try:
            partner_birth_date = date.fromisoformat(partner_birth_raw)
        except ValueError:
            return jsonify({"error": "Ungueltiges Geburtsdatum der Partnerin/des Partners."}), 400
        partner_report = build_numerology_report(partner_name, partner_birth_date, NUMEROLOGY_KB)
        report["partner_life_path"] = partner_report["life_path"]["number"]
        report["compatibility"] = numerology_compatibility(
            report["life_path"]["number"], partner_report["life_path"]["number"], NUMEROLOGY_KB
        )

    return jsonify(report)


@app.post("/api/iching")
def iching():
    question = request.form.get("question", "").strip() or None
    reading = build_reading(ICHING_KB, question=question)
    return jsonify(reading)


@app.post("/api/journal")
def journal():
    entry_text = request.form.get("entry_text", "").strip()
    if not entry_text:
        return jsonify({"error": "Bitte einen Journal-Text schreiben."}), 400

    category = request.form.get("category", "").strip()
    if category and category not in JOURNAL_KB["journal_categories"]:
        return jsonify({"error": "Unbekannte Kategorie."}), 400

    today = date.today()
    moon_phase = moon_phase_for_date(today)
    crisis = detect_crisis(entry_text, JOURNAL_KB)

    sun_sign = None
    life_path = None
    personal_year = None
    days_to_birthday = None

    birth_raw = request.form.get("birth_date", "").strip()
    if birth_raw:
        try:
            birth_date = date.fromisoformat(birth_raw)
        except ValueError:
            return jsonify({"error": "Ungueltiges Geburtsdatum."}), 400
        sun_sign = western_sign_for_date(birth_date.month, birth_date.day)
        life_path = life_path_number(birth_date)
        personal_year = personal_year_number(birth_date, today.year)
        days_to_birthday = days_until_birthday(birth_date, today)

    result = {
        "crisis_detected": crisis,
        "crisis_response": JOURNAL_KB["ethics"]["crisis_detection"]["response"] if crisis else None,
        "moon_phase": moon_phase,
        "sun_sign": sun_sign,
        "life_path": life_path,
        "personal_year": personal_year,
        "auto_insights": [] if crisis else auto_insights(
            moon_phase=moon_phase, personal_year=personal_year, days_to_birthday=days_to_birthday
        ),
        "ai_reflection": None,
    }

    use_ai = request.form.get("use_ai", "true").strip().lower() != "false"
    api_key = request.form.get("api_key", "").strip() or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if use_ai and api_key and not crisis:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = build_analysis_prompt(
            entry_text,
            JOURNAL_KB,
            sun_sign=sun_sign or "nicht angegeben",
            moon_phase=moon_phase,
            life_path=life_path if life_path is not None else "nicht angegeben",
            personal_year=personal_year if personal_year is not None else "nicht angegeben",
        )
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            result["ai_reflection"] = next(b.text for b in response.content if b.type == "text")
        except anthropic.AuthenticationError:
            return jsonify({"error": "API-Key ungueltig oder abgelehnt."}), 401
        except anthropic.RateLimitError:
            return jsonify({"error": "Rate-Limit erreicht. Bitte spaeter erneut versuchen."}), 429
        except anthropic.APIStatusError as e:
            return jsonify({"error": f"API-Fehler: {e.message}"}), 502
        except anthropic.APIConnectionError:
            return jsonify({"error": "Keine Verbindung zur Anthropic-API. Internetverbindung pruefen."}), 502

    return jsonify(result)


@app.post("/api/impulse")
def impulse():
    date_raw = request.form.get("date", "").strip()
    target_date = date.today()
    if date_raw:
        try:
            target_date = date.fromisoformat(date_raw)
        except ValueError:
            return jsonify({"error": "Ungueltiges Datum."}), 400

    moon_phase = moon_phase_for_date(target_date)

    zodiac_sign = None
    birth_date = None
    birth_raw = request.form.get("birth_date", "").strip()
    if birth_raw:
        try:
            birth_date = date.fromisoformat(birth_raw)
        except ValueError:
            return jsonify({"error": "Ungueltiges Geburtsdatum."}), 400
        zodiac_sign = western_sign_for_date(birth_date.month, birth_date.day)

    feed = build_impulse_feed(
        target_date, IMPULSE_KB, moon_phase=moon_phase, zodiac_sign=zodiac_sign, birth_date=birth_date
    )
    feed["moon_phase"] = moon_phase
    feed["zodiac_sign"] = zodiac_sign
    return jsonify(feed)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
