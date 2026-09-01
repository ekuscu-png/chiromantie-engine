"""
Tages-Impulse von push_notifications_knowledge_base.json.

Echte Push-Benachrichtigungen (Service Worker, Push-Abos, serverseitiger
Scheduler zu festen Uhrzeiten) sind in dieser zustandslosen Vercel-App
bewusst NICHT umgesetzt - dafuer braucht es eine Datenbank fuer Abos und
einen Cron-Trigger, beides existiert hier nicht. Stattdessen werden dieselben
Nachrichten-Pools, die ein Push-System verschicken wuerde, hier direkt auf
Anfrage als Tages-Feed gezeigt. Nachrichten mit Platzhaltern wie {theme} oder
{moon_activity}, die echte Ephemeriden oder erfundenen Freitext bräuchten,
werden dabei aussortiert - angezeigt wird nur, was ohne Erfindung befuellbar ist.
"""

from __future__ import annotations

import random
from datetime import date

_SEASONAL_DATES = {
    (3, 20): "spring_equinox",
    (6, 21): "summer_solstice",
    (9, 22): "autumn_equinox",
    (12, 21): "winter_solstice",
    (1, 1): "new_year",
}


def _static_messages(messages: list[str]) -> list[str]:
    return [m for m in messages if "{" not in m]


def pick_message(messages: list[str]) -> str | None:
    pool = _static_messages(messages)
    return random.choice(pool) if pool else None


def seasonal_message(target_date: date, kb: dict) -> str | None:
    key = _SEASONAL_DATES.get((target_date.month, target_date.day))
    if key is None:
        return None
    return kb["notification_categories"]["seasonal_special"].get(key)


def birthday_message(birth_date: date, target_date: date, kb: dict) -> str | None:
    seasonal = kb["notification_categories"]["seasonal_special"]
    if (target_date.month, target_date.day) == (birth_date.month, birth_date.day):
        return seasonal.get("birthday")
    if target_date.month == birth_date.month:
        return seasonal.get("birthday_month")
    return None


def build_impulse_feed(
    target_date: date,
    kb: dict,
    *,
    moon_phase: str,
    zodiac_sign: str | None = None,
    birth_date: date | None = None,
) -> dict:
    categories = kb["notification_categories"]
    return {
        "date": target_date.isoformat(),
        "moon_impulse": pick_message(categories["moon_phase_alerts"].get(moon_phase, [])),
        "zodiac_impulse": pick_message(categories["zodiac_specific"][zodiac_sign]) if zodiac_sign else None,
        "tarot_impulse": pick_message(categories["tarot_daily_hooks"]),
        "iching_impulse": pick_message(categories["iching_hooks"]),
        "numerology_impulse": pick_message(categories["numerology_prompts"]),
        "journal_impulse": pick_message(categories["journal_reminders"]),
        "seasonal_impulse": seasonal_message(target_date, kb),
        "birthday_impulse": birthday_message(birth_date, target_date, kb) if birth_date else None,
    }
