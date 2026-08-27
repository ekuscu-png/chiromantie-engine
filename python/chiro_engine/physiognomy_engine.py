"""
Physiognomik-spezifische Auswertung von physiognomy_master_knowledge_base.json.

Zwei Ebenen:
  - direct_interpretations(): liest fuer jedes erkannte Einzelmerkmal (Stirn,
    Augenbrauen, Augen, Nase, Mund, Kinn, Ohren, Haut, Gesichtsform, ...) den
    passenden Eintrag direkt aus der KB (kein Regel-Matching noetig, da die
    KB pro Merkmalswert bereits eine fertige Deutung enthaelt).
  - build_compound_features() + load_compound_rules(): uebersetzen die 200+
    Kombinationsregeln (compound_rules_200plus) in RuleDefinition-Objekte,
    die vom bestehenden RuleEngine ausgewertet werden koennen.
"""

from __future__ import annotations

from .rule_engine import RuleDefinition, RuleOutput

_MEANING_KEYS = ("meaning", "personality", "career", "warning")

_COMPOUND_RULE_GROUPS = {
    "personality_rules": "personality",
    "career_rules": "career",
    "wealth_rules": "wealth",
    "relationship_rules": "relationships",
    "health_rules": "health",
    "life_phase_rules_age_based": "life_phase",
    "compound_lucky_signs": "lucky_signs",
}

_SIMPLE_LOOKUPS = [
    ("forehead_height", "Stirn – Höhe", ("forehead_deep", "height_detailed")),
    ("forehead_shape", "Stirn – Form", ("forehead_deep", "shape_detailed")),
    ("forehead_width", "Stirn – Breite", ("forehead_deep", "width_detailed")),
    ("eyebrows_length", "Augenbrauen – Länge", ("eyebrows_deep", "length_detailed")),
    ("eyebrows_thickness", "Augenbrauen – Dichte", ("eyebrows_deep", "thickness_detailed")),
    ("eyebrows_shape", "Augenbrauen – Form", ("eyebrows_deep", "shape_detailed")),
    ("eyebrows_spacing", "Augenbrauen – Abstand", ("eyebrows_deep", "spacing_detailed")),
    ("eyes_size", "Augen – Größe", ("eyes_deep", "size_detailed")),
    ("eyes_shape", "Augen – Form", ("eyes_deep", "shape_detailed")),
    ("eyes_distance", "Augen – Abstand", ("eyes_deep", "distance_detailed")),
    ("eyes_expression", "Augen – Ausdruck", ("eyes_deep", "expression_detailed")),
    ("nose_length", "Nase – Länge", ("nose_deep", "length_detailed")),
    ("nose_bridge", "Nase – Rücken", ("nose_deep", "bridge_detailed")),
    ("nose_tip", "Nase – Spitze", ("nose_deep", "tip_detailed")),
    ("nose_wings", "Nase – Flügel", ("nose_deep", "wings_detailed")),
    ("nose_nostrils", "Nase – Nasenlöcher", ("nose_deep", "nostril_detailed")),
    ("nose_root_shan_gen", "Nasenwurzel (Shan Gen)", ("nose_deep", "root_shan_gen_detailed")),
    ("mouth_size", "Mund – Größe", ("mouth_lips_deep", "size_detailed")),
    ("lips_thickness", "Lippen – Fülle", ("mouth_lips_deep", "lip_thickness_detailed")),
    ("lips_shape", "Lippen – Form", ("mouth_lips_deep", "shape_detailed")),
    ("lips_corners", "Mundwinkel", ("mouth_lips_deep", "corners_detailed")),
    ("lips_color", "Lippen – Farbe", ("mouth_lips_deep", "color_of_lips")),
    ("philtrum_length", "Philtrum (Ren Zhong)", ("mouth_lips_deep", "philtrum_ren_zhong_deep")),
    ("chin_shape", "Kinn – Form", ("chin_jaw_deep", "chin_shape_detailed")),
    ("jaw_shape", "Kiefer", ("chin_jaw_deep", "jaw_detailed")),
    ("ears_size", "Ohren – Größe", ("ears_deep", "size_detailed")),
    ("ears_position", "Ohren – Position", ("ears_deep", "position_detailed")),
    ("ears_earlobe", "Ohrläppchen", ("ears_deep", "earlobe_detailed")),
    ("ears_shape", "Ohren – Form", ("ears_deep", "shape_detailed")),
    ("skin_color", "Haut – Farbe/Glanz", ("skin_deep", "color_detailed")),
    ("skin_texture", "Haut – Textur", ("skin_deep", "texture_detailed")),
]


def _entry_text(entry: dict) -> str:
    return " ".join(entry[k] for k in _MEANING_KEYS if entry.get(k))


def direct_interpretations(extracted: dict, kb: dict) -> list[dict]:
    """Liest fuer jedes erkannte Merkmal die passende Deutung direkt aus der KB."""
    results: list[dict] = []

    face_shape = extracted.get("face_shape")
    if face_shape and face_shape != "unknown":
        shape_entry = kb["face_shapes_extended"].get(face_shape)
        if shape_entry:
            parts = [shape_entry.get("personality_long") or shape_entry.get("personality_short")]
            for key in ("wealth_pattern", "relationships_pattern", "health_pattern"):
                if shape_entry.get(key):
                    parts.append(shape_entry[key])
            results.append({
                "section": "Gesichtsform",
                "value": face_shape,
                "text": " ".join(p for p in parts if p),
            })

    san_ting = extracted.get("san_ting_balance")
    if san_ting and san_ting != "unknown":
        text = kb["three_courts_san_ting"]["balance_analysis"].get(san_ting)
        if text:
            results.append({"section": "Drei Höfe (San Ting) – Balance", "value": san_ting, "text": text})

    glabella = extracted.get("glabella_area")
    if glabella and glabella != "unknown":
        text = kb["twelve_palaces_detailed"]["1_ming_gong_life_palace"]["interpretations"].get(glabella)
        if text:
            results.append({"section": "Palast des Lebens (Yin Tang)", "value": glabella, "text": text})

    for extracted_key, label, path in _SIMPLE_LOOKUPS:
        value = extracted.get(extracted_key)
        if not value or value == "unknown":
            continue
        node = kb
        for part in path:
            node = node.get(part, {})
        entry = node.get(value)
        if entry:
            results.append({"section": label, "value": value, "text": _entry_text(entry)})

    for pos in extracted.get("moles") or []:
        if pos in ("none", "other_position", "unknown"):
            continue
        entry = kb["moles_extended_positions"]["positions"].get(pos)
        if entry and entry.get("meaning"):
            results.append({"section": f"Muttermal: {pos}", "value": pos, "text": entry["meaning"]})

    return results


def age_phase_interpretation(age: int, kb: dict) -> dict | None:
    """life_phase_rules_age_based nutzt 'user.age BETWEEN x AND y', was ausserhalb
    der Condition-DSL liegt (kein BETWEEN-Operator) - daher direkte Bereichs-Pruefung."""
    ranges = [
        (15, 30), (31, 34), (35, 40), (41, 50),
        (51, 55), (56, 65), (66, 75), (76, 100),
    ]
    for (lo, hi), raw in zip(ranges, kb["compound_rules_200plus"]["life_phase_rules_age_based"]):
        if lo <= age <= hi:
            return {"section": "Aktuelle Lebensphase", "value": f"{lo}-{hi}", "text": raw["output"]}
    return None


def load_compound_rules(kb: dict) -> list[RuleDefinition]:
    """Uebersetzt compound_rules_200plus in RuleDefinition-Objekte fuer den RuleEngine."""
    rules: list[RuleDefinition] = []
    compound = kb["compound_rules_200plus"]
    for group_key, domain in _COMPOUND_RULE_GROUPS.items():
        for raw in compound.get(group_key, []):
            rules.append(
                RuleDefinition(
                    id=raw["id"],
                    condition=raw["condition"],
                    output=RuleOutput(domain=domain, text=raw["output"]),
                    category=domain,
                )
            )
    return rules


def build_compound_features(extracted: dict, kb: dict) -> dict:
    """Bildet die extrahierten Merkmale bestmoeglich auf das flache Vokabular ab,
    das die compound_rules_200plus-Bedingungen verwenden (z.B. 'forehead' == 'wide_high').
    Deckt nicht alle 200+ Regeln ab, aber einen Grossteil der haeufigen Kombinationen."""
    features: dict = {}

    face_shape = extracted.get("face_shape")
    if face_shape and face_shape != "unknown":
        features["face_shape"] = face_shape
        shape_entry = kb["face_shapes_extended"].get(face_shape, {})
        if shape_entry.get("element"):
            features["element"] = shape_entry["element"]
        if face_shape == "long_narrow":
            features["face"] = "long_narrow"

    if extracted.get("face_symmetry") == "asymmetric":
        features["face"] = "asymmetric"

    if extracted.get("san_ting_balance") == "all_three_equal":
        features["san_ting"] = "balanced"

    glabella = extracted.get("glabella_area")
    if glabella in ("wide", "wide_bright"):
        features["yin_tang"] = glabella

    forehead_h = extracted.get("forehead_height")
    forehead_w = extracted.get("forehead_width")
    if forehead_w in ("wide", "very_wide") and forehead_h in ("high", "very_high"):
        features["forehead"] = "wide_high"
    elif forehead_h == "very_high":
        features["forehead"] = "very_high"
    elif forehead_w in ("wide", "very_wide"):
        features["forehead"] = "wide"

    thickness = extracted.get("eyebrows_thickness")
    ebrow_shape = extracted.get("eyebrows_shape")
    spacing = extracted.get("eyebrows_spacing")
    if spacing == "monobrow":
        features["brows"] = "monobrow"
    elif ebrow_shape == "one_arched_one_straight":
        features["brows"] = "asymmetric"
    elif ebrow_shape == "downturned_ends":
        features["brows"] = "downturned"
    elif thickness in ("thin", "very_thin", "sparse_gappy") and ebrow_shape == "arched_high_dramatic":
        features["brows"] = "thin_arched"
    elif thickness in ("thick", "very_thick"):
        features["brows"] = "thick"
    elif thickness in ("thin", "very_thin", "sparse_gappy"):
        features["brows"] = "thin"
    elif ebrow_shape == "straight_horizontal":
        features["brows"] = "straight"

    expr = extracted.get("eyes_expression")
    eshape = extracted.get("eyes_shape")
    esize = extracted.get("eyes_size")
    if expr == "fiery_intense":
        features["eyes"] = "fiery"
    elif expr == "bright_clear_lively":
        features["eyes"] = "clear_bright"
    elif eshape == "almond":
        features["eyes"] = "almond"
    elif eshape == "hooded_droopy_lid":
        features["eyes"] = "hooded"
    elif eshape == "downturned_corners":
        features["eyes"] = "downturned"
    elif eshape == "asymmetric_eyes":
        features["eyes"] = "asymmetric"
    elif esize in ("large", "very_large"):
        features["eyes"] = "large"

    if extracted.get("dark_circles_under_eyes") == "deep":
        features["dark_circles_under_eyes"] = "deep"
    if extracted.get("crows_feet") == "deep_many":
        features["crows_feet"] = "deep_many"

    bridge = extracted.get("nose_bridge")
    if bridge in ("very_high_straight", "high_straight"):
        features["nose"] = "straight_high"
    elif bridge == "humped_aquiline":
        features["nose"] = "sharp"

    tip = extracted.get("nose_tip")
    if tip == "pointed_sharp":
        features["nose_tip"] = "pointed_sharp"
    elif tip in ("round_fleshy_ideal", "round_bulbous_very_large"):
        features["nose_tip"] = "round_fleshy"

    wings = extracted.get("nose_wings")
    if wings in ("full_fleshy", "very_full_thick"):
        features["wings"] = "full"

    nostrils = extracted.get("nose_nostrils")
    if nostrils in ("large_visible", "very_large_flaring"):
        features["nostrils"] = "visible"
    elif nostrils in ("small_hidden", "very_small_hidden"):
        features["nostrils"] = "hidden"

    san_gen = extracted.get("nose_root_shan_gen")
    if san_gen in ("very_high_wide", "high_wide"):
        features["san_gen"] = "high_full"
    elif san_gen == "low_sunken":
        features["san_gen"] = "low"

    if extracted.get("philtrum_length") in ("very_deep_long", "long_clear_deep"):
        features["philtrum"] = "long_clear"

    lips_thick = extracted.get("lips_thickness")
    lips_shape = extracted.get("lips_shape")
    lips_color = extracted.get("lips_color")
    if lips_color == "natural_healthy_pink":
        features["lips"] = "natural_red"
    elif lips_color == "pale_lips":
        features["lips"] = "pale"
    elif lips_color == "bluish_lips":
        features["lips"] = "blue_purple"
    elif lips_shape == "cupids_bow_pronounced":
        features["lips"] = "cupids_bow"
    elif lips_thick in ("full_both", "very_full_both"):
        features["lips"] = "full"
    elif lips_thick in ("thin_both", "very_thin_both"):
        features["lips"] = "thin"

    mouth_size = extracted.get("mouth_size")
    corners = extracted.get("lips_corners")
    if mouth_size in ("large", "very_large"):
        features["mouth"] = "large"
    elif corners in ("upturned", "very_upturned"):
        features["mouth"] = "upturned"

    chin = extracted.get("chin_shape")
    if chin in ("round_full", "very_round_full"):
        features["chin"] = "round_full"
    elif chin in ("square_angular", "very_square"):
        features["chin"] = "strong"
    elif chin in ("receding_weak", "very_receding"):
        features["chin"] = "weak"

    jaw = extracted.get("jaw_shape")
    if jaw in ("wide_strong", "very_wide_strong"):
        features["jaw"] = "wide_strong"
    elif jaw == "very_angular_defined":
        features["jaw"] = "very_angular"
    elif jaw == "medium":
        features["jaw"] = "medium"

    earlobe = extracted.get("ears_earlobe")
    ears_size = extracted.get("ears_size")
    if earlobe in ("very_large_fleshy_pendulous", "large_fleshy"):
        features["ears"] = "buddha_lobes"
        features["earlobes"] = "large_fleshy"
    elif ears_size in ("very_large_prominent", "large"):
        features["ears"] = "large"

    if extracted.get("cheekbone_prominence") == "high_prominent":
        features["cheekbones"] = "high_prominent"

    if extracted.get("cheeks_fullness") == "full":
        features["cheeks"] = "full"

    skin_color = extracted.get("skin_color")
    if skin_color == "clear_luminous_glowing":
        features["skin"] = "glowing"
    elif skin_color == "very_pale":
        features["skin"] = "very_pale"

    return features
