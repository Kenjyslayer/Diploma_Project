from django.utils import timezone

from .models import Contribution, ModerationReport, Profile


def staff_portal(request):
    u = request.user
    if not u.is_authenticated:
        return {"show_staff_portal": False}
    now = timezone.now()

    # Per-link badge counts (used in navbar).
    owner_needs_review = Contribution.objects.filter(
        request__created_by=u,
        status__in=(Contribution.STATUS_PROPOSED, Contribution.STATUS_REVISION_REQUESTED),
    ).count()
    my_changes_requested = Contribution.objects.filter(
        user=u,
        status=Contribution.STATUS_REVISION_REQUESTED,
    ).count()

    staff_queue = 0
    if u.is_staff or u.is_superuser:
        staff_queue = (
            Profile.objects.filter(verification_status=Profile.VERIFICATION_PENDING).count()
            + ModerationReport.objects.filter(status=ModerationReport.STATUS_OPEN).count()
        )
        notif = staff_queue
        return {
            "show_staff_portal": True,
            "now": now,
            "notif_count": notif,
            "notif_owner_review": owner_needs_review,
            "notif_my_offers_changes": my_changes_requested,
            "notif_staff_queue": staff_queue,
        }
    if u.is_staff or u.is_superuser:
        # (handled above)
        pass
    p = getattr(u, "profile", None)
    show_staff = bool(p and p.role == "admin")
    notif = owner_needs_review + my_changes_requested
    if p:
        if show_staff:
            staff_queue = (
                Profile.objects.filter(verification_status=Profile.VERIFICATION_PENDING).count()
                + ModerationReport.objects.filter(status=ModerationReport.STATUS_OPEN).count()
            )
            notif += staff_queue
    return {
        "show_staff_portal": show_staff,
        "now": now,
        "notif_count": notif,
        "notif_owner_review": owner_needs_review,
        "notif_my_offers_changes": my_changes_requested,
        "notif_staff_queue": staff_queue,
    }
