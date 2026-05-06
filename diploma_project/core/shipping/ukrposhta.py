"""
Ukrposhta: office lists differ by account/API product. We keep a small optional hook
and always allow the user to type the final office line + map pin in the form.

Set UKRPOSHTA_BEARER_TOKEN (and optionally UKRPOSHTA_POSTCODE_SEARCH_URL) in the environment
if you connect a real Ukrposhta API contract.
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings


def postoffices_by_postcode(postcode: str) -> dict[str, Any]:
    """
    If settings provide a search URL template with {postcode} and a bearer token, call it.
    Otherwise return a soft failure so the UI can use manual text + map only.
    """
    token = getattr(settings, "UKRPOSHTA_BEARER_TOKEN", "") or ""
    url_tmpl = getattr(settings, "UKRPOSHTA_POSTCODE_SEARCH_URL", "") or ""
    postcode = (postcode or "").strip().replace(" ", "")
    if not postcode:
        return {"success": False, "error": "EMPTY_POSTCODE", "offices": []}
    if not token or not url_tmpl:
        return {
            "success": False,
            "error": "NO_UKRPOSHTA_CONFIG",
            "message": "Configure UKRPOSHTA_BEARER_TOKEN and UKRPOSHTA_POSTCODE_SEARCH_URL, or enter the office manually.",
            "offices": [],
        }
    url = url_tmpl.format(postcode=urllib.parse.quote(postcode))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, list):
        return {"success": True, "offices": data}
    if isinstance(data, dict) and "data" in data:
        return {"success": True, "offices": data.get("data") or []}
    return {"success": True, "offices": [], "raw": data}
