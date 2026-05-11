from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from core.models import AuditLogEntry, Contribution, Request


def _client_ip(request: HttpRequest) -> str | None:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return xff or (request.META.get("REMOTE_ADDR") or None)


def log_audit(
    *,
    request: HttpRequest | None,
    actor,
    action: str,
    target_user=None,
    target_request: Request | None = None,
    target_contribution: Contribution | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    try:
        actor_user = actor if getattr(actor, "pk", None) else None
        AuditLogEntry.objects.create(
            actor=actor_user,
            action=action,
            target_user=target_user,
            target_request=target_request,
            target_contribution=target_contribution,
            ip=_client_ip(request) if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1000] if request else "",
            meta=meta or {},
        )
    except Exception:
        # Audit logging must never break business actions.
        return

