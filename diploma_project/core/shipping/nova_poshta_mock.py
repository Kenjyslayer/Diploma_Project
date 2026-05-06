"""
Offline demo data for Nova Poshta city / warehouse pickers (no real API calls).

Used when NOVA_POSHTA_USE_MOCK_DATA is True (empty API key, or NOVA_POSHTA_OFFLINE_DEMO=1).
Refs are synthetic strings stored in the DB with the request/contribution.
"""

from __future__ import annotations

from typing import Any

# City Ref -> list of warehouses (NP-like shape for the frontend).
MOCK_WAREHOUSES: dict[str, list[dict[str, Any]]] = {
    "mock-np-city-if": [
        {
            "Ref": "mock-np-if-1",
            "ShortAddress": "Нова Пошта №1 — вул. Макухи, 41",
            "Description": "Нова Пошта №1 — вул. Макухи, 41",
        },
        {
            "Ref": "mock-np-if-2",
            "ShortAddress": "Нова Пошта №2 — вул. Гетьмана Мазепи, 168",
            "Description": "Нова Пошта №2 — вул. Гетьмана Мазепи, 168",
        },
        {
            "Ref": "mock-np-if-3",
            "ShortAddress": "Нова Пошта №3 — вул. Залізнична, 22",
            "Description": "Нова Пошта №3 — вул. Залізнична, 22",
        },
        {
            "Ref": "mock-np-if-4",
            "ShortAddress": "Нова Пошта №4 — вул. Незалежності, 46",
            "Description": "Нова Пошта №4 — вул. Незалежності, 46",
        },
        {
            "Ref": "mock-np-if-5",
            "ShortAddress": "Нова Пошта №5 — вул. Довженка, 21",
            "Description": "Нова Пошта №5 — вул. Довженка, 21",
        },
    ],
    "mock-np-city-ky": [
        {
            "Ref": "mock-np-ky-1",
            "ShortAddress": "Нова Пошта №1 — вул. Пирогівський Шлях, 135",
            "Description": "Нова Пошта №1 — вул. Пирогівський Шлях, 135",
        },
        {
            "Ref": "mock-np-ky-8",
            "ShortAddress": "Нова Пошта №8 — вул. Басейна, 4",
            "Description": "Нова Пошта №8 — вул. Басейна, 4",
        },
        {
            "Ref": "mock-np-ky-18",
            "ShortAddress": "Нова Пошта №18 — вул. Попудренка, 52",
            "Description": "Нова Пошта №18 — вул. Попудренка, 52",
        },
        {
            "Ref": "mock-np-ky-114",
            "ShortAddress": "Нова Пошта №114 — вул. Антоновича, 50",
            "Description": "Нова Пошта №114 — вул. Антоновича, 50",
        },
        {
            "Ref": "mock-np-ky-295",
            "ShortAddress": "Нова Пошта №295 — просп. Степана Бандери, 23",
            "Description": "Нова Пошта №295 — просп. Степана Бандери, 23",
        },
    ],
    "mock-np-city-lv": [
        {
            "Ref": "mock-np-lv-1",
            "ShortAddress": "Нова Пошта №1 — вул. Городоцька, 355",
            "Description": "Нова Пошта №1 — вул. Городоцька, 355",
        },
        {
            "Ref": "mock-np-lv-2",
            "ShortAddress": "Нова Пошта №2 — вул. Богдана Хмельницького, 212",
            "Description": "Нова Пошта №2 — вул. Богдана Хмельницького, 212",
        },
        {
            "Ref": "mock-np-lv-5",
            "ShortAddress": "Нова Пошта №5 — вул. Зелена, 147",
            "Description": "Нова Пошта №5 — вул. Зелена, 147",
        },
        {
            "Ref": "mock-np-lv-6",
            "ShortAddress": "Нова Пошта №6 — вул. Наукова, 35А",
            "Description": "Нова Пошта №6 — вул. Наукова, 35А",
        },
        {
            "Ref": "mock-np-lv-9",
            "ShortAddress": "Нова Пошта №9 — вул. Личаківська, 152",
            "Description": "Нова Пошта №9 — вул. Личаківська, 152",
        },
    ],
}

MOCK_CITIES: list[dict[str, Any]] = [
    {
        "Ref": "mock-np-city-if",
        "Description": "Івано-Франківськ",
        "DescriptionRu": "Ивано-Франковск",
    },
    {
        "Ref": "mock-np-city-ky",
        "Description": "Київ",
        "DescriptionRu": "Киев",
    },
    {
        "Ref": "mock-np-city-lv",
        "Description": "Львів",
        "DescriptionRu": "Львов",
    },
]

# Extra search tokens (ASCII / alternate spellings) -> city Ref
_SEARCH_ALIASES: dict[str, tuple[str, ...]] = {
    "mock-np-city-if": ("ivano", "frankivsk", "frankovsk", "ifs"),
    "mock-np-city-ky": ("kyiv", "kiev", "ky"),
    "mock-np-city-lv": ("lviv", "lwów", "lvov"),
}


def _city_matches(city: dict[str, Any], q: str) -> bool:
    q = (q or "").strip().lower()
    if not q:
        return False
    ref = city["Ref"]
    hay = " ".join(
        [
            city.get("Description") or "",
            city.get("DescriptionRu") or "",
            " ".join(_SEARCH_ALIASES.get(ref, ())),
        ]
    ).lower()
    return q in hay


def mock_search_cities(find_string: str, limit: int = 30) -> dict[str, Any]:
    find_string = (find_string or "").strip()
    if len(find_string) < 2:
        return {"success": True, "data": []}
    out = [c for c in MOCK_CITIES if _city_matches(c, find_string)]
    return {"success": True, "data": out[:limit]}


def mock_warehouses_for_city(city_ref: str) -> dict[str, Any]:
    data = MOCK_WAREHOUSES.get((city_ref or "").strip(), [])
    return {"success": True, "data": data}
