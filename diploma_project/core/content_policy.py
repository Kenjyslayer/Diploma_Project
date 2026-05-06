"""Content moderation helpers (lightweight, deterministic).

We deliberately start with a keyword/regex policy (no external LLM dependency).
Later you can plug in an AI assistant and keep the same interface.
"""

from __future__ import annotations

import re

# Minimal starter list; expand as needed.
_MILITARY_PATTERNS = [
    r"\bgun\b",
    r"\brifle\b",
    r"\bweapon\b",
    r"\bammo\b",
    r"\bgrenade\b",
    r"\bmissile\b",
    r"\brocket\b",
    r"\btomahawk\b",
    r"\b2omahawk\b",
    r"\bak-?47\b",
    r"ак-?47",  # Cyrillic AK-47
    r"\bakm\b",
    r"акм",
    r"ак-?\s?74",
    r"ak-?\s?74",
    r"рпг-?\s?\d+",
    r"\brpg-?\s?\d+\b",
    r"\bptrk\b",
    r"птрк",
    r"\bmanpads\b",
    r"пзрк",
    r"стингер|stinger",
    r"джавелін|javelin",
    r"nlaw",
    r"стугна",
    r"гранатомет",
    r"міномет",
    r"міна\b|міни\b",
    r"\bmine\b|\bmines\b",
    r"вибухівк|вибухов|вибух",
    r"детонатор",
    r"боєкомплект|бк\b",
    r"бронежилет",
    r"каска\b|шолом",
    r"приціл нічного бачення|пнв|nvgs?",
    r"\barmor\b|\barmour\b",
    r"\bballistic\b",
    r"\bm4\b",
    r"\bdrone\b",
    # Calibers / ammo formats (common ways people try to hide military intent)
    r"\b7\s*[,.:]?\s*62\b",
    r"\b5\s*[,.:]?\s*45\b",
    r"\b5\s*[,.:]?\s*56\b",
    r"\b7\s*[,.:]?\s*92\b",
    r"\b9\s*(?:x\s*19|мм|mm)\b",
    r"\b12\s*(?:ga|gauge)\b",
    r"\bcaliber\b",
    r"\bcalibre\b",
    r"калібр",
    r"боєприпас",
    r"набо[їи]",
    r"рак(е|є)т",  # ракета/ракети
    r"збро",      # зброя/зброї
    r"гранат",
    r"кулемет",
    r"автомат",
    r"патрон",
]

_RX = re.compile("|".join(f"(?:{p})" for p in _MILITARY_PATTERNS), flags=re.IGNORECASE)


def civil_text_contains_military_terms(title: str, description: str) -> bool:
    blob = f"{title or ''}\n{description or ''}"
    return bool(_RX.search(blob))


def civil_moderation_score(title: str, description: str) -> int:
    """Simple scoring for 'AI assistant' moderation (rule-based)."""
    blob = f"{title or ''}\n{description or ''}"
    hits = _RX.findall(blob)
    if not hits:
        return 0
    # Cap so UI is stable.
    return min(100, 20 + (len(hits) * 15))

