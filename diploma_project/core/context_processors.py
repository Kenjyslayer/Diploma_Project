from django.utils import timezone

from .models import Contribution, ModerationReport, Profile


def staff_portal(request):
    u = request.user
    if not u.is_authenticated:
        return {"show_staff_portal": False}
    if u.is_staff or u.is_superuser:
        now = timezone.now()
        notif = (
            Profile.objects.filter(verification_status=Profile.VERIFICATION_PENDING).count()
            + ModerationReport.objects.filter(status=ModerationReport.STATUS_OPEN).count()
        )
        return {"show_staff_portal": True, "now": now, "notif_count": notif}
    p = getattr(u, "profile", None)
    now = timezone.now()
    show_staff = bool(p and p.role == "admin")
    notif = 0
    if p:
        notif += Contribution.objects.filter(
            request__created_by=u,
            status__in=(Contribution.STATUS_PROPOSED, Contribution.STATUS_REVISION_REQUESTED),
        ).count()
        notif += Contribution.objects.filter(user=u, status=Contribution.STATUS_REVISION_REQUESTED).count()
        if show_staff:
            notif += Profile.objects.filter(verification_status=Profile.VERIFICATION_PENDING).count()
            notif += ModerationReport.objects.filter(status=ModerationReport.STATUS_OPEN).count()
    return {"show_staff_portal": show_staff, "now": now, "notif_count": notif}
