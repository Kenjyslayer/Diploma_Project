"""Generate PNG QR codes for printable shipping handoff slips (MVP — not an official carrier label)."""

from __future__ import annotations

import base64
import io
import json
from typing import Any

from ..models import Contribution, Request as ResourceRequest


def build_qr_payload(contribution: Contribution, req: ResourceRequest) -> str:
    """
    Compact machine-readable payload for staff / internal scanners.
    Not a real Nova Poshta / Hermes waybill number.
    """
    payload: dict[str, Any] = {
        "app": "fulfillment-mvp",
        "v": 1,
        "contribution_id": contribution.id,
        "verification": str(contribution.verification_code),
        "request_id": req.id,
        "quantity": contribution.quantity,
        "send_before_utc": contribution.expires_at.isoformat() if contribution.expires_at else None,
    }
    if req.delivery_country == ResourceRequest.COUNTRY_UA:
        payload["contrib_kind"] = contribution.contrib_delivery_kind or ""
        if contribution.contrib_delivery_kind == ResourceRequest.DELIVERY_KIND_NOVA:
            payload["ship_from"] = (contribution.contrib_np_label or "").strip()
            payload["np_city_ref"] = contribution.contrib_np_city_ref or ""
            payload["np_wh_ref"] = contribution.contrib_np_warehouse_ref or ""
        elif contribution.contrib_delivery_kind == ResourceRequest.DELIVERY_KIND_UKR:
            payload["ship_from"] = (contribution.contrib_up_label or "").strip()
            payload["up_postcode"] = contribution.contrib_up_postcode or ""
    else:
        payload["ship_note"] = (contribution.contrib_dropoff_note or "").strip()

    payload["deliver_to_hint"] = _recipient_hint(req)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _recipient_hint(req: ResourceRequest) -> str:
    if req.delivery_country == ResourceRequest.COUNTRY_UA:
        if req.delivery_kind == ResourceRequest.DELIVERY_KIND_NOVA and req.np_label:
            return (req.np_label or "").strip()[:500]
        if req.delivery_kind == ResourceRequest.DELIVERY_KIND_UKR and req.up_label:
            return (req.up_label or "").strip()[:500]
    return (req.delivery_location or "").strip()[:500]


def qr_png_data_uri(text: str, box_size: int = 6) -> str:
    import qrcode

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
