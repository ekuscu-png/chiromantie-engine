"""
Mondkalender-Auswertung von moon_calendar_master.json.

Die Mondphase eines Datums lässt sich mit einer einfachen astronomischen
Naeherung berechnen (Tage seit einem bekannten Referenz-Neumond, modulo
synodischer Monat). Genauer als +/-1 Tag ist das ohne echte Ephemeriden nicht -
fuer eine Unterhaltungs-App reicht das. Mondstand im Tierkreis, Fruchtbarkeits-
Fenster und konkrete Sondertermine (Supermond, Finsternisse) brauchen dagegen
echte Ephemeriden-Daten und werden hier bewusst NICHT berechnet.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

_REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
_SYNODIC_MONTH_DAYS = 29.530588853

_PHASE_ORDER = [
    "new_moon",
    "waxing_crescent",
    "first_quarter",
    "waxing_gibbous",
    "full_moon",
    "waning_gibbous",
    "last_quarter",
    "waning_crescent",
]


def moon_phase_fraction(target_date: date) -> float:
    """0.0 = Neumond, 0.5 = Vollmond, wraps bei 1.0 zurueck zu Neumond."""
    target = datetime(target_date.year, target_date.month, target_date.day, 12, 0, tzinfo=timezone.utc)
    days_since = (target - _REFERENCE_NEW_MOON).total_seconds() / 86400.0
    return (days_since % _SYNODIC_MONTH_DAYS) / _SYNODIC_MONTH_DAYS


def moon_phase_for_date(target_date: date) -> str:
    fraction = moon_phase_fraction(target_date)
    index = int((fraction + 1 / 16) // (1 / 8)) % 8
    return _PHASE_ORDER[index]


def build_moon_report(target_date: date, kb: dict) -> dict:
    phase = moon_phase_for_date(target_date)
    return {
        "date": target_date.isoformat(),
        "phase": phase,
        "phase_data": kb["moon_phases_8"]["phases"][phase],
    }
