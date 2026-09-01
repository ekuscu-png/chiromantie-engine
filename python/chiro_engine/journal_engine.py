"""
Journal-Auswertung von journal_knowledge_base.json.

Diese App hat keine Datenbank und keine Nutzerkonten - ein Journal-Eintrag
wird deshalb einzeln, direkt beim Absenden ausgewertet. Alles, was echten
Verlauf ueber mehrere Eintraege braucht (Wochen-Muster, Gratitude-Streaks,
wiederkehrende Themen, Mond-im-Zeichen), wird hier bewusst NICHT simuliert,
da dafuer Daten fehlen, die diese App nicht speichert. Die Krisen-Erkennung
ist eine einfache Stichwort-Suche, keine echte Risikoeinschaetzung, und
ersetzt keine professionelle Hilfe.
"""

from __future__ import annotations

from datetime import date


def journal_categories(kb: dict) -> dict:
    return kb["journal_categories"]


def detect_crisis(entry_text: str, kb: dict) -> bool:
    keywords = kb["ethics"]["crisis_detection"]["keywords_trigger_alert"]
    lowered = entry_text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def days_until_birthday(birth_date: date, today: date) -> int:
    def safe_date(year: int) -> date:
        try:
            return date(year, birth_date.month, birth_date.day)
        except ValueError:
            return date(year, 3, 1)  # 29. Februar in einem Nicht-Schaltjahr

    next_birthday = safe_date(today.year)
    if next_birthday < today:
        next_birthday = safe_date(today.year + 1)
    return (next_birthday - today).days


def auto_insights(*, moon_phase: str, personal_year: int | None, days_to_birthday: int | None) -> list[str]:
    """Nur die Regeln aus auto_insight_rules, die ohne Verlauf und ohne Ephemeriden
    zuverlaessig pruefbar sind."""
    insights: list[str] = []
    if moon_phase == "new_moon":
        insights.append("Heute ist Neumond — ein guter Tag für neue Intentionen. Was möchtest du in diesem Zyklus säen?")
    elif moon_phase == "full_moon":
        insights.append("Es ist Vollmond — emotionale Intensität ist heute bei vielen Menschen verstärkt.")
    if personal_year == 9:
        insights.append("Du bist in einem 9er-Jahr — dem Jahr der Vollendung. Loslassen kann jetzt Thema sein.")
    elif personal_year == 1:
        insights.append("1er-Jahr — perfekt für Neuanfänge. Was du jetzt beginnst, prägt tendenziell die nächsten 9 Jahre.")
    if days_to_birthday is not None and 0 <= days_to_birthday < 30:
        insights.append("Dein Geburtstag naht — die Zeit der 'Solar Return'. Reflexion über das vergangene Jahr ist jetzt kraftvoll.")
    return insights


def build_analysis_prompt(
    entry_text: str,
    kb: dict,
    *,
    sun_sign: str,
    moon_phase: str,
    life_path,
    personal_year,
) -> str:
    template = kb["llm_analysis_prompts"]["single_entry_analysis"]["prompt_template"]
    unavailable = "nicht verfügbar (erfordert Ephemeriden-Daten)"
    filled = (
        template.replace("{sun_sign}", sun_sign)
        .replace("{moon_sign}", unavailable)
        .replace("{life_path}", str(life_path))
        .replace("{personal_year}", str(personal_year))
        .replace("{moon_phase}", moon_phase)
        .replace("{moon_in_sign}", unavailable)
        .replace("{entry_text}", entry_text)
    )
    return filled
