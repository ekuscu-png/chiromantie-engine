"""
Sternzeichen-Auswertung von zodiac_master_knowledge_base.json.

Anders als Chiromantie/Physiognomik braucht dieser Bereich kein Foto und keine
Vision-Analyse: das Sternzeichen ergibt sich deterministisch aus dem Geburtsdatum,
daher reine Datums-Arithmetik plus direkte KB-Lookups (keine Regel-Engine noetig).
"""

from __future__ import annotations

from datetime import date

# (Zeichen, (Start-Monat, Start-Tag), (End-Monat, End-Tag)) - Steinbock wraps Jahreswechsel.
_SIGN_RANGES = [
    ("aries", (3, 21), (4, 19)),
    ("taurus", (4, 20), (5, 20)),
    ("gemini", (5, 21), (6, 20)),
    ("cancer", (6, 21), (7, 22)),
    ("leo", (7, 23), (8, 22)),
    ("virgo", (8, 23), (9, 22)),
    ("libra", (9, 23), (10, 22)),
    ("scorpio", (10, 23), (11, 21)),
    ("sagittarius", (11, 22), (12, 21)),
    ("capricorn", (12, 22), (1, 19)),
    ("aquarius", (1, 20), (2, 18)),
    ("pisces", (2, 19), (3, 20)),
]


def western_sign_for_date(month: int, day: int) -> str:
    for sign, (start_month, start_day), (end_month, end_day) in _SIGN_RANGES:
        if start_month <= end_month:
            in_range = (start_month, start_day) <= (month, day) <= (end_month, end_day)
        else:
            in_range = (month, day) >= (start_month, start_day) or (month, day) <= (end_month, end_day)
        if in_range:
            return sign
    raise ValueError(f"Kein Sternzeichen fuer Datum {month}/{day} gefunden")


def chinese_animal_for_year(year: int, kb: dict) -> str | None:
    animals = kb["chinese_zodiac"]["animals"]
    for name, data in animals.items():
        if year in data["years"]:
            return name
    for name, data in animals.items():
        reference_year = data["years"][0]
        if (year - reference_year) % 12 == 0:
            return name
    return None


def build_zodiac_report(birth_date: date, kb: dict) -> dict:
    sign = western_sign_for_date(birth_date.month, birth_date.day)
    animal = chinese_animal_for_year(birth_date.year, kb)
    return {
        "sign": sign,
        "sign_data": kb["western_zodiac_signs"][sign],
        "career": kb["career_matches_by_sign"].get(sign),
        "health": kb["health_by_sign"].get(sign),
        "money": kb["money_by_sign"].get(sign),
        "chinese_animal": animal,
        "chinese_animal_data": kb["chinese_zodiac"]["animals"].get(animal) if animal else None,
        "chinese_new_year_caveat": birth_date.month in (1, 2),
    }


def compatibility_report(sign1: str, sign2: str, kb: dict) -> dict | None:
    return kb["compatibility_matrix_144"].get(f"{sign1}_{sign2}")
