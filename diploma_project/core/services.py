"""Business helpers kept out of views (MVP)."""

from django.db import transaction
from django.utils import timezone

from .models import Contribution, Request


FULFILLMENT_DAYS = 7


def expire_pending_contributions_for_request(request_obj: Request) -> int:
    """
    Mark pending contributions past expires_at as expired and restore request quantities.
    Called from views (no Celery) so expiry is applied when users visit relevant pages.
    Returns number of contributions expired in this run.
    """
    now = timezone.now()
    count = 0
    with transaction.atomic():
        req = Request.objects.select_for_update().get(pk=request_obj.pk)
        pending = (
            Contribution.objects.select_for_update()
            .filter(request=req, status="pending")
            .exclude(expires_at__isnull=True)
        )
        for c in pending:
            if c.expires_at <= now:
                c.status = "expired"
                c.save()
                count += 1
    return count
