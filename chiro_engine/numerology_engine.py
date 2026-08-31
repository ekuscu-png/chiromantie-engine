"""
Numerologie-Berechnung von numerology_master.json (pythagoreisches System).

Alle Kernzahlen (Lebenszahl, Ausdruckszahl, Seelenzahl, Persoenlichkeitszahl,
Geburtstagszahl, Personal-Year-Zahl) ergeben sich deterministisch aus
Geburtsdatum und Namen - keine KI, keine Ephemeriden noetig.
"""

from __future__ import annotations

import unicodedata
from datetime import date

_VOWELS = set("AEIOU")
_MASTER_NUMBERS = (11, 22, 33)


def _build_letter_map(kb: dict) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for value_str, letters in kb["systems"]["pythagorean"]["letter_values"].items():
        for letter in letters:
            mapping[letter] = int(value_str)
    return mapping


def _normalize_name(name: str) -> str:
    name = name.replace("ß", "ss").replace("ẞ", "SS")
    decomposed = unicodedata.normalize("NFKD", name.upper())
    return "".join(c for c in decomposed if "A" <= c <= "Z")


def reduce_number(n: int) -> int:
    """Quersumme bis einstellig, haelt aber bei Meisterzahlen (11, 22, 33) an."""
    while n > 9 and n not in _MASTER_NUMBERS:
        n = sum(int(d) for d in str(n))
    return n


def _reduce_fully(n: int) -> int:
    """Wie reduce_number, aber ignoriert Meisterzahlen (fuer die Kompatibilitaets-Matrix, die nur 1-9 kennt)."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def life_path_number(birth_date: date) -> int:
    digits = f"{birth_date.day:02d}{birth_date.month:02d}{birth_date.year:04d}"
    return reduce_number(sum(int(d) for d in digits))


def _name_number(name: str, letter_map: dict[str, int], predicate) -> int:
    normalized = _normalize_name(name)
    total = sum(letter_map.get(ch, 0) for ch in normalized if predicate(ch))
    return reduce_number(total)


def expression_number(name: str, letter_map: dict[str, int]) -> int:
    return _name_number(name, letter_map, lambda ch: True)


def soul_urge_number(name: str, letter_map: dict[str, int]) -> int:
    return _name_number(name, letter_map, lambda ch: ch in _VOWELS)


def personality_number(name: str, letter_map: dict[str, int]) -> int:
    return _name_number(name, letter_map, lambda ch: ch not in _VOWELS)


def personal_year_number(birth_date: date, year: int) -> int:
    return reduce_number(reduce_number(birth_date.day) + reduce_number(birth_date.month) + reduce_number(year))


def number_interpretation(n: int, kb: dict) -> dict | None:
    if n in _MASTER_NUMBERS:
        return kb["master_numbers"].get(str(n))
    return kb["core_numbers_1_9"].get(str(n))


def karmic_debt_for_day(day: int, kb: dict) -> dict | None:
    if day in (13, 14, 16, 19):
        return kb["karmic_debt_numbers"].get(str(day))
    return None


def numerology_compatibility(number1: int, number2: int, kb: dict) -> str | None:
    a, b = sorted((_reduce_fully(number1), _reduce_fully(number2)))
    return kb["compatibility_matrix"].get(f"{a}_{b}")


def build_numerology_report(name: str, birth_date: date, kb: dict, *, today: date | None = None) -> dict:
    letter_map = _build_letter_map(kb)
    life_path = life_path_number(birth_date)
    expression = expression_number(name, letter_map)
    soul_urge = soul_urge_number(name, letter_map)
    personality = personality_number(name, letter_map)
    birthday_reduced = reduce_number(birth_date.day)
    personal_year = personal_year_number(birth_date, (today or date.today()).year)

    return {
        "life_path": {"number": life_path, "data": number_interpretation(life_path, kb)},
        "expression": {"number": expression, "data": number_interpretation(expression, kb)},
        "soul_urge": {"number": soul_urge, "data": number_interpretation(soul_urge, kb)},
        "personality": {"number": personality, "data": number_interpretation(personality, kb)},
        "birthday": {
            "number": birth_date.day,
            "reduced": birthday_reduced,
            "data": number_interpretation(birthday_reduced, kb),
        },
        "personal_year": {"number": personal_year, "meaning": kb["personal_year_meanings"].get(str(personal_year))},
        "karmic_debt": karmic_debt_for_day(birth_date.day, kb),
    }
