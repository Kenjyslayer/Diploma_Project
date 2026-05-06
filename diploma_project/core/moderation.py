"""Moderation helpers for reporting suspicious requests to staff."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from .content_policy import civil_moderation_score, civil_text_contains_military_terms
from .models import ModerationReport, Profile, Request

User = get_user_model()


def maybe_report_suspicious_civil_request_submission(
    *,
    created_by: User | None,
    title: str,
    description: str,
    category: str,
    request_obj: Request | None = None,
) -> ModerationReport | None:
    """
    Create an OPEN moderation report if a civil request looks suspicious.
    Works even if the request was blocked and not saved (stores snapshot).
    """
    if category != 'civil':
        return None
    if not civil_text_contains_military_terms(title, description):
        return None
    score = civil_moderation_score(title, description)
    actor = created_by if getattr(created_by, 'is_authenticated', False) else None

    # De-dupe: avoid spamming identical reports from same user in a short window.
    if actor:
        since_dup = timezone.now() - timedelta(minutes=5)
        existing = ModerationReport.objects.filter(
            created_by=actor,
            status=ModerationReport.STATUS_OPEN,
            created_at__gte=since_dup,
            snapshot_title=(title or '')[:255],
            snapshot_category=category,
        ).first()
        if existing:
            return existing

    # Escalate repeated attempts within a short window.
    attempts = 1
    if actor:
        since = timezone.now() - timedelta(minutes=30)
        attempts = (
            ModerationReport.objects.filter(
                created_by=actor,
                created_at__gte=since,
            ).count()
            + 1
        )
        if attempts >= 3:
            score = 100
            # Temporary restriction (soft ban) after repeated attempts.
            try:
                p = getattr(actor, "profile", None)
                if p:
                    p.restricted_until = timezone.now() + timedelta(hours=24)
                    p.restricted_reason = (
                        f"Temporary restriction: repeated blocked civil submissions ({attempts} in 30 min)."
                    )
                    p.save(update_fields=["restricted_until", "restricted_reason"])
            except Exception:
                pass
    return ModerationReport.objects.create(
        created_by=actor,
        request=request_obj,
        snapshot_title=(title or '')[:255],
        snapshot_description=(description or ''),
        snapshot_category=category,
        reason=(
            f"Repeated blocked civil submissions ({attempts} in last 30 min)."
            if attempts >= 3
            else "Civil request contains military-like terms (AI-assisted policy)."
        ),
        score=score,
    )

