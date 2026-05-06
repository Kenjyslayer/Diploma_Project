"""In-site administration UI (tabs). Django `/admin/` remains available for advanced edits."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Contribution, Dispute, ModerationReport, Profile, Request as ResourceRequest
from .permissions import staff_required

User = get_user_model()


@staff_required
def staff_dashboard(request):
    ctx = {
        "n_users": User.objects.count(),
        "n_requests": ResourceRequest.objects.count(),
        "n_contributions": Contribution.objects.count(),
        "n_disputes_open": Dispute.objects.filter(status=Dispute.STATUS_OPEN).count(),
        "n_verifications_pending": Profile.objects.filter(verification_status=Profile.VERIFICATION_PENDING).count(),
        "n_moderation_open": ModerationReport.objects.filter(status=ModerationReport.STATUS_OPEN).count(),
    }
    ctx["staff_nav"] = "dash"
    return render(request, "core/staff/dashboard.html", ctx)


@staff_required
def staff_users(request):
    qs = User.objects.select_related("profile").order_by("username")
    flt = (request.GET.get("filter") or "").strip()
    now = timezone.now()
    if flt == "banned":
        qs = qs.filter(profile__banned_at__isnull=False)
    elif flt == "restricted":
        qs = qs.filter(profile__restricted_until__gt=now)
    elif flt == "verif_pending":
        qs = qs.filter(profile__verification_status=Profile.VERIFICATION_PENDING)
    elif flt == "verif_rejected":
        qs = qs.filter(profile__verification_status=Profile.VERIFICATION_REJECTED)
    elif flt == "unverified":
        qs = qs.exclude(profile__verification_status=Profile.VERIFICATION_VERIFIED)
    users = qs
    return render(
        request,
        "core/staff/users.html",
        {"users": users, "staff_nav": "users", "filter": flt, "now": now},
    )


@staff_required
@require_POST
def staff_user_action(request, user_id: int):
    u = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    p = getattr(u, "profile", None)
    if not p:
        messages.error(request, "User has no profile.")
        return redirect("staff_users")
    action = (request.POST.get("action") or "").strip()
    note = (request.POST.get("note") or "").strip()
    hours_raw = (request.POST.get("hours") or "").strip()
    if action == "unrestrict":
        p.restricted_until = None
        p.restricted_reason = ""
        p.banned_at = None
        p.banned_reason = ""
        p.save(update_fields=["restricted_until", "restricted_reason", "banned_at", "banned_reason"])
        messages.success(request, f"User {u.username} unrestricted.")
    elif action == "restrict_temp":
        try:
            hours = int(hours_raw)
        except Exception:
            hours = 24
        hours = max(1, min(24 * 30, hours))
        p.restricted_until = timezone.now() + timedelta(hours=hours)
        p.restricted_reason = note or f"Temporary restriction ({hours}h) applied by staff."
        p.save(update_fields=["restricted_until", "restricted_reason"])
        messages.success(request, f"User {u.username} restricted for {hours}h.")
    elif action == "ban_permanent":
        p.banned_at = timezone.now()
        p.banned_reason = note or "Permanent ban applied by staff."
        p.restricted_until = None
        p.restricted_reason = ""
        p.save(update_fields=["banned_at", "banned_reason", "restricted_until", "restricted_reason"])
        messages.success(request, f"User {u.username} permanently banned.")
    else:
        messages.error(request, "Unknown action.")
    back = request.META.get("HTTP_REFERER") or None
    return redirect(back or "staff_users")


@staff_required
def staff_verifications(request):
    users = (
        User.objects.select_related("profile")
        .filter(profile__verification_status__in=(Profile.VERIFICATION_PENDING, Profile.VERIFICATION_REJECTED))
        .order_by("username")
    )
    pending = (
        User.objects.select_related("profile")
        .filter(profile__verification_status=Profile.VERIFICATION_PENDING)
        .order_by("username")
    )
    return render(
        request,
        "core/staff/verifications.html",
        {"users": users, "pending": pending, "staff_nav": "verifications"},
    )


@staff_required
@require_POST
def staff_verification_action(request, user_id: int):
    u = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    p = getattr(u, "profile", None)
    if not p:
        messages.error(request, "User has no profile.")
        return redirect("staff_verifications")
    action = request.POST.get("action")
    note = (request.POST.get("note") or "").strip()
    if action == "approve":
        if not p.passport_scan:
            messages.error(request, "Cannot approve without a passport scan.")
            return redirect("staff_verifications")
        if p.role == "military" and not p.reserve_plus_pdf:
            messages.error(request, "Military verification requires a \"Резерв+\" PDF.")
            return redirect("staff_verifications")
        p.verification_status = Profile.VERIFICATION_VERIFIED
        p.verification_note = note
        p.is_verified = True
        p.save(update_fields=["verification_status", "verification_note", "is_verified"])
        messages.success(request, f"Verified user {u.username}.")
    elif action == "reject":
        p.verification_status = Profile.VERIFICATION_REJECTED
        p.verification_note = note or "Rejected."
        p.is_verified = False
        p.save(update_fields=["verification_status", "verification_note", "is_verified"])
        messages.success(request, f"Rejected verification for {u.username}.")
    else:
        messages.error(request, "Unknown action.")
    return redirect("staff_verifications")


@staff_required
def staff_moderation(request):
    open_reports = ModerationReport.objects.select_related('created_by', 'request').filter(
        status=ModerationReport.STATUS_OPEN
    )
    resolved_reports = ModerationReport.objects.select_related('created_by', 'request').filter(
        status=ModerationReport.STATUS_RESOLVED
    )[:200]
    return render(
        request,
        "core/staff/moderation.html",
        {
            "open_reports": open_reports,
            "resolved_reports": resolved_reports,
            "staff_nav": "moderation",
            "now": timezone.now(),
        },
    )


@staff_required
@require_POST
def staff_moderation_resolve(request, report_id: int):
    r = get_object_or_404(ModerationReport, pk=report_id)
    r.status = ModerationReport.STATUS_RESOLVED
    r.resolved_at = timezone.now()
    r.resolved_by = request.user
    r.admin_note = (request.POST.get("admin_note") or "").strip()
    r.save(update_fields=["status", "resolved_at", "resolved_by", "admin_note"])
    messages.success(request, f"Report #{r.id} resolved.")
    return redirect("staff_moderation")


@staff_required
@require_POST
def staff_moderation_action(request, report_id: int):
    r = get_object_or_404(ModerationReport.objects.select_related("created_by"), pk=report_id)
    action = (request.POST.get("action") or "").strip()
    note = (request.POST.get("note") or "").strip()
    hours_raw = (request.POST.get("hours") or "").strip()
    actor = r.created_by
    p = getattr(actor, "profile", None) if actor else None
    if not actor or not p:
        messages.error(request, "Report has no user/profile to action.")
        return redirect("staff_moderation")

    if action == "unrestrict":
        p.restricted_until = None
        p.restricted_reason = ""
        p.banned_at = None
        p.banned_reason = ""
        p.save(update_fields=["restricted_until", "restricted_reason", "banned_at", "banned_reason"])
        r.action_taken = ModerationReport.ACTION_UNRESTRICT
        r.action_note = note
        r.action_by = request.user
        r.action_at = timezone.now()
        r.action_duration_hours = None
        r.status = ModerationReport.STATUS_RESOLVED
        r.resolved_at = timezone.now()
        r.resolved_by = request.user
        r.save(
            update_fields=[
                "action_taken",
                "action_note",
                "action_by",
                "action_at",
                "action_duration_hours",
                "status",
                "resolved_at",
                "resolved_by",
            ]
        )
        messages.success(request, f"User {actor.username} unrestricted.")
        return redirect("staff_moderation")

    if action == "restrict_temp":
        try:
            hours = int(hours_raw)
        except Exception:
            hours = 24
        hours = max(1, min(24 * 30, hours))  # cap at 30 days
        p.restricted_until = timezone.now() + timedelta(hours=hours)
        p.restricted_reason = note or f"Temporary restriction ({hours}h) applied by staff."
        p.save(update_fields=["restricted_until", "restricted_reason"])
        r.action_taken = ModerationReport.ACTION_RESTRICT_TEMP
        r.action_note = note
        r.action_by = request.user
        r.action_at = timezone.now()
        r.action_duration_hours = hours
        r.status = ModerationReport.STATUS_RESOLVED
        r.resolved_at = timezone.now()
        r.resolved_by = request.user
        r.save(
            update_fields=[
                "action_taken",
                "action_note",
                "action_by",
                "action_at",
                "action_duration_hours",
                "status",
                "resolved_at",
                "resolved_by",
            ]
        )
        messages.success(request, f"User {actor.username} restricted for {hours}h.")
        return redirect("staff_moderation")

    if action == "ban_permanent":
        p.banned_at = timezone.now()
        p.banned_reason = note or "Permanent ban applied by staff."
        p.restricted_until = None
        p.restricted_reason = ""
        p.save(update_fields=["banned_at", "banned_reason", "restricted_until", "restricted_reason"])
        r.action_taken = ModerationReport.ACTION_BAN_PERMANENT
        r.action_note = note
        r.action_by = request.user
        r.action_at = timezone.now()
        r.action_duration_hours = None
        r.status = ModerationReport.STATUS_RESOLVED
        r.resolved_at = timezone.now()
        r.resolved_by = request.user
        r.save(
            update_fields=[
                "action_taken",
                "action_note",
                "action_by",
                "action_at",
                "action_duration_hours",
                "status",
                "resolved_at",
                "resolved_by",
            ]
        )
        messages.success(request, f"User {actor.username} permanently banned.")
        return redirect("staff_moderation")

    messages.error(request, "Unknown moderation action.")
    return redirect("staff_moderation")


@staff_required
def staff_requests(request):
    reqs = ResourceRequest.objects.select_related("created_by", "hidden_by").order_by("-created_at")
    return render(
        request,
        "core/staff/requests.html",
        {"requests": reqs, "staff_nav": "requests", "now": timezone.now()},
    )


@staff_required
@require_POST
def staff_request_action(request, request_id: int):
    r = get_object_or_404(ResourceRequest, pk=request_id)
    action = (request.POST.get("action") or "").strip()
    note = (request.POST.get("note") or "").strip()
    if action == "hide":
        r.is_hidden = True
        r.hidden_at = timezone.now()
        r.hidden_by = request.user
        r.hidden_reason = note or "Hidden by staff."
        r.save(update_fields=["is_hidden", "hidden_at", "hidden_by", "hidden_reason"])
        messages.success(request, f"Request #{r.id} hidden.")
    elif action == "unhide":
        r.is_hidden = False
        r.hidden_at = None
        r.hidden_by = None
        r.hidden_reason = ""
        r.save(update_fields=["is_hidden", "hidden_at", "hidden_by", "hidden_reason"])
        messages.success(request, f"Request #{r.id} restored.")
    elif action == "warn":
        if not note:
            messages.error(request, "Warning text is required.")
            return redirect("staff_requests")
        r.staff_warning = note
        r.staff_warning_at = timezone.now()
        r.staff_warning_by = request.user
        r.save(update_fields=["staff_warning", "staff_warning_at", "staff_warning_by"])
        messages.success(request, f"Warning added to request #{r.id}.")
    elif action == "clear_warning":
        r.staff_warning = ""
        r.staff_warning_at = None
        r.staff_warning_by = None
        r.save(update_fields=["staff_warning", "staff_warning_at", "staff_warning_by"])
        messages.success(request, f"Warning cleared for request #{r.id}.")
    elif action == "delete":
        confirm = (request.POST.get("confirm") or "").strip().lower()
        if confirm != "delete":
            messages.error(request, 'Type "delete" in confirmation to delete the request.')
            return redirect("staff_requests")
        if r.contributions.exists():
            messages.error(request, "Cannot delete a request that has contributions. Hide it instead.")
            return redirect("staff_requests")
        r.delete()
        messages.success(request, f"Request #{request_id} deleted.")
        return redirect("staff_requests")
    else:
        messages.error(request, "Unknown action.")
    return redirect("staff_requests")


@staff_required
def staff_contributions(request):
    qs = Contribution.objects.select_related("user", "request").order_by("-created_at")
    return render(request, "core/staff/contributions.html", {"contributions": qs, "staff_nav": "contributions"})


@staff_required
@require_POST
def staff_contribution_status(request, contribution_id: int):
    c = get_object_or_404(Contribution, pk=contribution_id)
    action = request.POST.get("action")
    if action in ("approve", "reject") and c.status != Contribution.STATUS_PENDING:
        messages.error(
            request,
            "Staff approve/reject applies only after the request owner has accepted the contribution "
            '(status must be “Accepted — send within deadline”).',
        )
        return redirect("staff_contributions")
    if action == "approve":
        c.status = Contribution.STATUS_APPROVED
    elif action == "reject":
        c.status = Contribution.STATUS_REJECTED
    elif action == "verify":
        if not c.proof_file:
            messages.error(request, "Cannot verify without an uploaded proof file.")
            return redirect("staff_contributions")
        if c.status != Contribution.STATUS_APPROVED:
            messages.error(request, "Approve the contribution first, then verify after proof.")
            return redirect("staff_contributions")
        c.status = Contribution.STATUS_VERIFIED
    else:
        messages.error(request, "Unknown action.")
        return redirect("staff_contributions")
    try:
        c.save()
        messages.success(request, f"Contribution #{c.id} updated ({c.status}).")
    except ValidationError as e:
        messages.error(request, str(e))
    return redirect("staff_contributions")


@staff_required
def staff_disputes(request):
    qs = Dispute.objects.select_related("contribution", "created_by").order_by("-created_at")
    return render(request, "core/staff/disputes.html", {"disputes": qs, "staff_nav": "disputes"})


@staff_required
@require_POST
def staff_dispute_resolve(request, dispute_id: int):
    d = get_object_or_404(Dispute, pk=dispute_id)
    d.status = Dispute.STATUS_RESOLVED
    d.resolved_at = timezone.now()
    d.admin_note = (d.admin_note or "") + "\n" + request.POST.get("admin_note", "").strip()
    d.save()
    messages.success(request, f"Dispute #{d.id} marked resolved.")
    return redirect("staff_disputes")
