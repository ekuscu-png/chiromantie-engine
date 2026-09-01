"""
I Ging / Buch der Wandlungen von iching_knowledge_base.json.

Die klassische Muenz-Methode wird digital simuliert: 6 Linien mit den
gewichteten Wahrscheinlichkeiten aus der KB (6/9 = wandelnde Linien, je 12.5%;
7/8 = stabile Linien, je 37.5%). Das Hexagramm wird nicht ueber eine
hartkodierte King-Wen-Tabelle bestimmt, sondern direkt aus den
Trigramm-Binaercodes der mitgelieferten KB abgeleitet - so passt die
Zuordnung garantiert zu den 64 Hexagrammen, die tatsaechlich in der Datei
stehen.
"""

from __future__ import annotations

import random
import re


def _throw_line() -> dict:
    r = random.random()
    if r < 0.125:
        return {"value": 6, "yang": False, "changing": True}
    if r < 0.5:
        return {"value": 7, "yang": True, "changing": False}
    if r < 0.875:
        return {"value": 8, "yang": False, "changing": False}
    return {"value": 9, "yang": True, "changing": True}


def cast_lines() -> list[dict]:
    """6 Linien von unten (Index 0) nach oben (Index 5), wie beim Muenzwurf aufgebaut."""
    return [_throw_line() for _ in range(6)]


def _bare_trigram_name(name_de: str) -> str:
    """bagua_8_trigrams.name_de traegt einen Artikel und teils einen Klammerzusatz
    ("Der Wind (auch: Holz)"), waehrend hexagrams_64.upper_trigram/lower_trigram
    nur das nackte Substantiv nutzen ("Wind") - hier auf dasselbe Format bringen."""
    name = re.sub(r"^(Der|Die|Das)\s+", "", name_de)
    name = re.sub(r"\s*\(.*?\)\s*$", "", name)
    return name.strip()


def _trigram_names(kb: dict) -> dict[str, str]:
    """Binaercode (oben-mitte-unten, '1'=Yang) -> deutscher Trigramm-Name (nackt, ohne Artikel)."""
    return {data["binary"]: _bare_trigram_name(data["name_de"]) for data in kb["bagua_8_trigrams"].values()}


def _hexagram_numbers(kb: dict) -> dict[tuple[str, str], int]:
    """(oberes Trigramm, unteres Trigramm) auf Deutsch -> Hexagramm-Nummer."""
    lookup: dict[tuple[str, str], int] = {}
    for number_str, data in kb["hexagrams_64"].items():
        lookup[(data["upper_trigram"], data["lower_trigram"])] = int(number_str)
    return lookup


def _line_bit(line: dict, *, changed: bool) -> str:
    is_yang = line["yang"]
    if changed and line["changing"]:
        is_yang = not is_yang
    return "1" if is_yang else "0"


def _trigram_binary(trigram_lines: list[dict], *, changed: bool) -> str:
    """trigram_lines = [unten, mitte, oben]; KB-Binaercode ist oben-mitte-unten."""
    bottom, middle, top = trigram_lines
    return _line_bit(top, changed=changed) + _line_bit(middle, changed=changed) + _line_bit(bottom, changed=changed)


def _hexagram_for_lines(lines: list[dict], kb: dict, *, changed: bool) -> int | None:
    names = _trigram_names(kb)
    numbers = _hexagram_numbers(kb)
    lower_name = names.get(_trigram_binary(lines[0:3], changed=changed))
    upper_name = names.get(_trigram_binary(lines[3:6], changed=changed))
    if lower_name is None or upper_name is None:
        return None
    return numbers.get((upper_name, lower_name))


def build_reading(kb: dict, *, question: str | None = None, lines: list[dict] | None = None) -> dict:
    lines = lines if lines is not None else cast_lines()

    primary_number = _hexagram_for_lines(lines, kb, changed=False)
    primary = kb["hexagrams_64"].get(str(primary_number)) if primary_number else None

    changing_positions = [i + 1 for i, line in enumerate(lines) if line["changing"]]
    changing_lines = []
    if primary:
        for position in changing_positions:
            text = primary.get("changing_lines", {}).get(str(position))
            if text:
                changing_lines.append({"position": position, "text": text})

    resulting_number = None
    resulting = None
    if changing_positions:
        resulting_number = _hexagram_for_lines(lines, kb, changed=True)
        resulting = kb["hexagrams_64"].get(str(resulting_number)) if resulting_number else None

    return {
        "question": question or None,
        "lines": [{"value": l["value"], "yang": l["yang"], "changing": l["changing"]} for l in lines],
        "hexagram_number": primary_number,
        "hexagram": primary,
        "changing_lines": changing_lines,
        "resulting_hexagram_number": resulting_number,
        "resulting_hexagram": resulting,
    }
