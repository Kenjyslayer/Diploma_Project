"""Nova Poshta public JSON API (v2.0) — server-side only; never expose API key to the browser."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

NP_URL = "https://api.novaposhta.ua/v2.0/json/"


def _use_mock_data() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "NOVA_POSHTA_USE_MOCK_DATA", False))


def _post(api_key: str, model: str, method: str, method_properties: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "apiKey": api_key,
        "modelName": model,
        "calledMethod": method,
        "methodProperties": method_properties,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        NP_URL,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except Exception as exc:
        return {"success": False, "data": [], "errors": [str(exc)]}


def search_cities(api_key: str, find_string: str, limit: int = 30) -> dict[str, Any]:
    if _use_mock_data():
        from .nova_poshta_mock import mock_search_cities

        return mock_search_cities(find_string, limit)
    if not api_key:
        return {"success": False, "error": "NO_API_KEY"}
    find_string = (find_string or "").strip()
    if len(find_string) < 2:
        return {"success": True, "data": []}
    body = _post(
        api_key,
        "Address",
        "getCities",
        {"FindByString": find_string, "Limit": str(limit)},
    )
    return body


def warehouses_for_city(api_key: str, city_ref: str) -> dict[str, Any]:
    if _use_mock_data():
        from .nova_poshta_mock import mock_warehouses_for_city

        return mock_warehouses_for_city(city_ref)
    if not api_key:
        return {"success": False, "error": "NO_API_KEY"}
    return _post(
        api_key,
        "Address",
        "getWarehouses",
        {"CityRef": city_ref},
    )
