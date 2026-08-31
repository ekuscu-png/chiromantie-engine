"""
Sternzeichen-Auswertung von zodiac_master_knowledge_base.json.

Anders als Chiromantie/Physiognomik braucht dieser Bereich kein Foto und keine
Vision-Analyse: das Sternzeichen ergibt sich deterministisch aus dem Geburtsdatum,
daher reine Datums-Arithmetik plus direkte KB-Lookups (keine Regel-Engine noetig).
"""

from __future__ import annotations

from datetime import date

# (Zeichen, (Start-Monat, Start-Tag), (End-Monat, End-Tag)) - Steinbock wraps Jahreswechsel.
# Cusp-Tage (Zeichenwechsel) sind zwischen astrologischen Quellen um +/-1 Tag uneinig,
# da der exakte Sonneneintritt astronomisch von Jahr zu Jahr leicht schwankt. Diese
# Grenzen sind bewusst einen Tag spaeter angesetzt als die urspruengliche KB (z.B. 23.
# August = Loewe statt Jungfrau), passend zur zweiten verbreiteten Konvention.
_SIGN_RANGES = [
    ("aries", (3, 22), (4, 20)),
    ("taurus", (4, 21), (5, 21)),
    ("gemini", (5, 22), (6, 21)),
    ("cancer", (6, 22), (7, 23)),
    ("leo", (7, 24), (8, 23)),
    ("virgo", (8, 24), (9, 23)),
    ("libra", (9, 24), (10, 23)),
    ("scorpio", (10, 24), (11, 22)),
    ("sagittarius", (11, 23), (12, 22)),
    ("capricorn", (12, 23), (1, 20)),
    ("aquarius", (1, 21), (2, 19)),
    ("pisces", (2, 20), (3, 21)),
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
