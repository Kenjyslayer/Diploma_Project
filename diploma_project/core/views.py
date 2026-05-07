from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from datetime import timedelta

from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import (
    RegisterForm,
    RequestForm,
    ContributionProposeForm,
    ProofUploadForm,
    DisputeForm,
    MessageForm,
    LoginForm,
    VerificationUploadForm,
    RequestCloseForm,
    ProfileSettingsForm,
)
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .models import Request, Contribution, Dispute, Conversation, Message
from .services import expire_pending_contributions_for_request
from .shipping.handoff_slip import build_qr_payload, qr_png_data_uri


def _can_view_military_request(http_request, req: Request) -> bool:
    u = http_request.user
    if not u.is_authenticated:
        return False
    if req.created_by_id == u.id:
        return True
    if u.is_staff or u.is_superuser:
        return True
    p = getattr(u, 'profile', None)
    if p and p.role in ('admin', 'military'):
        return True
    return False


def _visible_requests_for_user(http_request):
    qs = Request.objects.all()
    u = http_request.user
    if not u.is_authenticated:
        return qs.exclude(category='military').exclude(status=Request.STATUS_CLOSED).exclude(is_hidden=True)
    if u.is_staff or u.is_superuser:
        return qs.exclude(status=Request.STATUS_CLOSED)
    p = getattr(u, 'profile', None)
    if p and p.role == 'admin':
        return qs.exclude(status=Request.STATUS_CLOSED)
    if p and p.role == 'military':
        return qs.exclude(status=Request.STATUS_CLOSED).exclude(is_hidden=True)
    # Civil (default): hide military requests
    return qs.exclude(category='military').exclude(status=Request.STATUS_CLOSED).exclude(is_hidden=True)


def _shipping_config():
    return {
        'nova_poshta_configured': bool((getattr(settings, 'NOVA_POSHTA_API_KEY', '') or '').strip())
        or bool(getattr(settings, 'NOVA_POSHTA_USE_MOCK_DATA', False)),
        'ukrposhta_configured': bool(
            (getattr(settings, 'UKRPOSHTA_BEARER_TOKEN', '') or '').strip()
            and (getattr(settings, 'UKRPOSHTA_POSTCODE_SEARCH_URL', '') or '').strip()
        ),
    }


def _assign_contribution_from_form(contribution: Contribution, cleaned: dict) -> None:
    contribution.quantity = cleaned['quantity']
    contribution.contrib_delivery_kind = cleaned.get('contrib_delivery_kind') or ''
    contribution.contrib_np_city_ref = cleaned.get('contrib_np_city_ref') or ''
    contribution.contrib_np_warehouse_ref = cleaned.get('contrib_np_warehouse_ref') or ''
    contribution.contrib_np_label = cleaned.get('contrib_np_label') or ''
    contribution.contrib_up_postcode = cleaned.get('contrib_up_postcode') or ''
    contribution.contrib_up_office_id = cleaned.get('contrib_up_office_id') or ''
    contribution.contrib_up_label = cleaned.get('contrib_up_label') or ''
    contribution.contrib_dropoff_note = cleaned.get('contrib_dropoff_note') or ''


def _request_detail_page_context(http_request, req: Request, propose_form=None):
    if propose_form is None:
        propose_form = ContributionProposeForm(resource_request=req)
    user_has_contribution = False
    show_delivery = False
    is_owner = False
    if http_request.user.is_authenticated:
        user_has_contribution = req.contributions.filter(user=http_request.user).exists()
        show_delivery = user_has_contribution or (req.created_by_id == http_request.user.id)
        is_owner = req.created_by_id == http_request.user.id
    incoming_for_owner = []
    if is_owner:
        incoming_for_owner = list(
            req.contributions.filter(
                status__in=(
                    Contribution.STATUS_PROPOSED,
                    Contribution.STATUS_REVISION_REQUESTED,
                )
            )
            .select_related('user')
            .order_by('-created_at')
        )
    owner_chat_map = {}
    if is_owner and incoming_for_owner:
        owner_chat_map = {
            conv.contributor_id: conv
            for conv in Conversation.objects.filter(
                resource_request=req,
                contributor_id__in=[c.user_id for c in incoming_for_owner],
            )
        }
    contributions = req.contributions.select_related('user').order_by('-created_at')
    my_conversation = None
    if http_request.user.is_authenticated:
        my_conversation = Conversation.objects.filter(
            resource_request=req,
            contributor=http_request.user,
        ).first()
    ctx = {
        'req': req,
        'propose_form': propose_form,
        'contributions': contributions,
        'show_delivery': show_delivery,
        'user_has_contribution': user_has_contribution,
        'is_owner': is_owner,
        'incoming_for_owner': incoming_for_owner,
        'owner_chat_map': owner_chat_map,
        'my_conversation': my_conversation,
    }
    ctx.update(_shipping_config())
    return ctx


def _get_or_create_conversation_for_request(req: Request, contributor_id: int) -> Conversation:
    receiver_id = req.created_by_id
    conv, _ = Conversation.objects.get_or_create(
        resource_request=req,
        contributor_id=contributor_id,
        defaults={'receiver_id': receiver_id, 'last_activity_at': timezone.now()},
    )
    return conv


def _post_system_message(conv: Conversation, body: str) -> None:
    # Lightweight system message: store as Message with a prefix.
    Message.objects.create(conversation=conv, sender_id=conv.receiver_id, body=f"[SYSTEM] {body}".strip())
    conv.last_activity_at = timezone.now()
    conv.save(update_fields=['last_activity_at'])


def _create_request_context(form, extra: dict | None = None):
    ctx = {"form": form}
    if extra:
        ctx.update(extra)
    ctx.update(_shipping_config())
    return ctx


def home(request):
    requests = _visible_requests_for_user(request).order_by('-created_at')
    return render(request, 'core/home.html', {'requests': requests})


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('verify_identity')
    else:
        form = RegisterForm()

    ctx = {'form': form}
    ctx.update(_shipping_config())
    return render(request, 'core/register.html', ctx)


def _needs_verification_submission(u) -> bool:
    p = getattr(u, 'profile', None)
    if not p:
        return True
    # Only VERIFIED users may post/contribute. Pending review is not enough.
    return p.verification_status != p.VERIFICATION_VERIFIED


def _require_verification_submission_or_redirect(request):
    if _needs_verification_submission(request.user):
        p = getattr(request.user, "profile", None)
        if p and p.verification_status == p.VERIFICATION_PENDING:
            messages.error(request, 'Your verification is pending review. You can post or contribute only after approval.')
        else:
            messages.error(request, 'Upload verification documents in your Profile before posting or contributing.')
        return redirect('profile')
    return None


def _require_not_restricted_or_redirect(request):
    u = request.user
    if not getattr(u, "is_authenticated", False):
        return None
    p = getattr(u, "profile", None)
    banned_at = getattr(p, "banned_at", None) if p else None
    if banned_at:
        messages.error(request, "Your account is banned from posting and contributing.")
        return redirect("profile")
    until = getattr(p, "restricted_until", None) if p else None
    if until and until > timezone.now():
        messages.error(
            request,
            f'Your account is temporarily restricted until {until.strftime("%Y-%m-%d %H:%M")} (UTC).',
        )
        return redirect("profile")
    return None


@login_required
def verify_identity(request):
    # Backward-compatible route; profile page is the main UX.
    return redirect('profile')


@login_required
def profile(request):
    profile = getattr(request.user, 'profile', None)
    if not profile:
        raise PermissionDenied
    action = request.POST.get('action') if request.method == 'POST' else None

    verify_form = VerificationUploadForm()
    settings_initial = {
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'email': request.user.email,
        'phone_number': profile.phone_number,
        'role': profile.role if profile.role in ('civil', 'military') else 'civil',
        'preferred_dropoff_kind': profile.preferred_dropoff_kind or Request.DELIVERY_KIND_NOVA,
        'preferred_np_city_ref': profile.preferred_np_city_ref,
        'preferred_np_warehouse_ref': profile.preferred_np_warehouse_ref,
        'preferred_np_label': profile.preferred_np_label,
        'preferred_up_postcode': profile.preferred_up_postcode,
        'preferred_up_office_id': profile.preferred_up_office_id,
        'preferred_up_label': profile.preferred_up_label,
    }
    settings_form = ProfileSettingsForm(initial=settings_initial, user=request.user)

    if request.method == 'POST' and action == 'settings':
        settings_form = ProfileSettingsForm(request.POST, user=request.user)
        if settings_form.is_valid():
            old_role = profile.role
            new_role = settings_form.cleaned_data.get('role', old_role)
            settings_form.save()
            if old_role != new_role:
                messages.warning(request, 'Account type changed. Please re-upload verification documents below.')
            else:
                messages.success(request, 'Profile updated.')
            return redirect('profile')

    if request.method == 'POST' and action == 'verify':
        verify_form = VerificationUploadForm(request.POST, request.FILES)
        if verify_form.is_valid():
            profile.passport_scan = verify_form.cleaned_data['passport_scan']
            profile.reserve_plus_pdf = None
            if profile.role == 'military':
                rp = verify_form.cleaned_data.get('reserve_plus_pdf')
                if not rp:
                    verify_form.add_error('reserve_plus_pdf', 'Military accounts must upload a \"Резерв+\" PDF.')
                else:
                    profile.reserve_plus_pdf = rp
            if not verify_form.errors:
                profile.verification_status = profile.VERIFICATION_PENDING
                profile.verification_note = ''
                profile.is_verified = False
                profile.save(
                    update_fields=[
                        'passport_scan',
                        'reserve_plus_pdf',
                        'verification_status',
                        'verification_note',
                        'is_verified',
                    ]
                )
                messages.success(request, 'Verification documents submitted. Awaiting review.')
                return redirect('dashboard')

    ctx = {
        'profile': profile,
        'needs_submission': _needs_verification_submission(request.user),
        'verify_form': verify_form,
        'settings_form': settings_form,
    }
    ctx["now"] = timezone.now()
    # Profile completeness/progress (lightweight UX, not a strict gate).
    steps = []
    steps.append(("Name", bool((request.user.first_name or "").strip()) and bool((request.user.last_name or "").strip())))
    steps.append(("Phone", bool((profile.phone_number or "").strip())))
    steps.append(("Preferred drop-off", bool((profile.preferred_dropoff_point or "").strip())))
    steps.append(("Documents uploaded", bool(profile.passport_scan) and (profile.role != "military" or bool(profile.reserve_plus_pdf)))
    )
    steps.append(("Verified", profile.verification_status == profile.VERIFICATION_VERIFIED))
    done = sum(1 for _, ok in steps if ok)
    total = len(steps) if steps else 1
    ctx["profile_steps"] = steps
    ctx["profile_progress_percent"] = int(round(done * 100 / total))
    ctx.update(_shipping_config())
    return render(request, 'core/profile.html', ctx)


def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('/')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('/')


def _initial_request_delivery_from_profile(profile) -> dict:
    """
    Pre-fill create-request delivery fields from the creator's preferred drop-off point.
    This does NOT implement any new address logic; it just uses what was saved on registration.
    """
    if not profile:
        return {}
    kind = getattr(profile, 'preferred_dropoff_kind', '') or ''
    # Backward-compat fallback: older users may have only the free-text field.
    if kind not in (Request.DELIVERY_KIND_NOVA, Request.DELIVERY_KIND_UKR):
        text = (getattr(profile, 'preferred_dropoff_point', '') or '').strip()
        if text:
            return {
                'delivery_country': Request.COUNTRY_UA,
                'delivery_kind': Request.DELIVERY_KIND_MANUAL,
                'delivery_location': text,
            }
        return {}
    initial = {
        'delivery_country': Request.COUNTRY_UA,
        'delivery_kind': kind,
        'delivery_location': '',
        'np_city_ref': '',
        'np_warehouse_ref': '',
        'np_label': '',
        'up_postcode': '',
        'up_office_id': '',
        'up_label': '',
    }
    if kind == Request.DELIVERY_KIND_NOVA:
        initial.update(
            {
                'np_city_ref': getattr(profile, 'preferred_np_city_ref', '') or '',
                'np_warehouse_ref': getattr(profile, 'preferred_np_warehouse_ref', '') or '',
                'np_label': getattr(profile, 'preferred_np_label', '') or '',
            }
        )
    if kind == Request.DELIVERY_KIND_UKR:
        initial.update(
            {
                'up_postcode': getattr(profile, 'preferred_up_postcode', '') or '',
                'up_office_id': getattr(profile, 'preferred_up_office_id', '') or '',
                'up_label': getattr(profile, 'preferred_up_label', '') or '',
            }
        )
    return initial


def _assign_request_delivery_from_profile(req: Request, profile) -> None:
    """
    Requests do not allow manual drop-off selection anymore.
    Delivery fields are always derived from the request owner's profile.
    """
    initial = _initial_request_delivery_from_profile(profile)
    if not initial:
        raise ValidationError(
            {
                "delivery_location": "Set your preferred drop-off point in Profile before creating requests.",
            }
        )
    req.delivery_country = initial.get("delivery_country") or Request.COUNTRY_UA
    req.delivery_kind = initial.get("delivery_kind") or Request.DELIVERY_KIND_MANUAL
    req.delivery_location = initial.get("delivery_location") or ""
    req.np_city_ref = initial.get("np_city_ref") or ""
    req.np_warehouse_ref = initial.get("np_warehouse_ref") or ""
    req.np_label = initial.get("np_label") or ""
    req.up_postcode = initial.get("up_postcode") or ""
    req.up_office_id = initial.get("up_office_id") or ""
    req.up_label = initial.get("up_label") or ""


@login_required
def create_request(request):
    restricted = _require_not_restricted_or_redirect(request)
    if restricted:
        return restricted
    gate = _require_verification_submission_or_redirect(request)
    if gate:
        return gate
    if request.method == 'POST':
        form = RequestForm(request.POST)
        if form.is_valid():
            req: Request = form.save(commit=False)
            req.created_by = request.user
            profile = getattr(request.user, 'profile', None)
            # Auto-fill delivery from profile (no user choice on request form).
            try:
                _assign_request_delivery_from_profile(req, profile)
            except ValidationError as e:
                messages.error(request, 'Set your preferred drop-off point in Profile first.')
                for field, errs in getattr(e, 'message_dict', {}).items():
                    if field in form.fields:
                        form.add_error(field, errs)
                    else:
                        messages.error(request, ' '.join(str(x) for x in errs))
                return render(request, 'core/create_request.html', _create_request_context(form))
            # Civil users cannot create military requests (even if they pick the category).
            if profile and profile.role == 'civil' and req.category == 'military':
                messages.error(request, 'Civil accounts cannot create military requests.')
                try:
                    from .moderation import maybe_report_suspicious_civil_request_submission

                    maybe_report_suspicious_civil_request_submission(
                        created_by=request.user,
                        title=req.title,
                        description=req.description,
                        category='civil',
                        request_obj=None,
                    )
                except Exception:
                    pass
                from .models import ModerationReport

                attempts = ModerationReport.objects.filter(
                    created_by=request.user,
                    created_at__gte=timezone.now() - timedelta(minutes=30),
                ).count()
                return render(
                    request,
                    'core/create_request.html',
                    _create_request_context(
                        form,
                        {
                            "suspicious_block": True,
                            "attempts": attempts,
                            "attempts_left": max(0, 3 - attempts),
                        },
                    ),
                )
            # Military requests can only be created by verified users.
            if req.category == 'military' and not (profile and profile.is_verified):
                messages.error(request, 'You must be verified to create military requests.')
                return render(request, 'core/create_request.html', _create_request_context(form))
            try:
                req.full_clean()
                req.save()
            except ValidationError as e:
                # AI-assisted moderation report (even if request is blocked).
                try:
                    from .moderation import maybe_report_suspicious_civil_request_submission

                    rep = maybe_report_suspicious_civil_request_submission(
                        created_by=request.user,
                        title=req.title,
                        description=req.description,
                        category=req.category,
                        request_obj=None,
                    )
                except Exception:
                    rep = None
                for field, errs in getattr(e, 'message_dict', {}).items():
                    if field in form.fields:
                        form.add_error(field, errs)
                    else:
                        messages.error(request, ' '.join(str(x) for x in errs))
                extra = {}
                if rep is not None:
                    from .models import ModerationReport

                    attempts = ModerationReport.objects.filter(
                        created_by=request.user,
                        created_at__gte=timezone.now() - timedelta(minutes=30),
                    ).count()
                    extra = {
                        "suspicious_block": True,
                        "attempts": attempts,
                        "attempts_left": max(0, 3 - attempts),
                    }
                return render(request, 'core/create_request.html', _create_request_context(form, extra))
            return redirect('/requests/')
        else:
            # If the user is repeatedly attempting to submit suspicious content, still report it
            # even when the form is invalid (e.g. missing quantity).
            try:
                from .moderation import maybe_report_suspicious_civil_request_submission

                rep = maybe_report_suspicious_civil_request_submission(
                    created_by=request.user,
                    title=(request.POST.get('title') or ''),
                    description=(request.POST.get('description') or ''),
                    category=(request.POST.get('category') or 'civil'),
                    request_obj=None,
                )
            except Exception:
                rep = None
            if rep is not None:
                from .models import ModerationReport

                attempts = ModerationReport.objects.filter(
                    created_by=request.user,
                    created_at__gte=timezone.now() - timedelta(minutes=30),
                ).count()
                return render(
                    request,
                    'core/create_request.html',
                    _create_request_context(
                        form,
                        {
                            "suspicious_block": True,
                            "attempts": attempts,
                            "attempts_left": max(0, 3 - attempts),
                        },
                    ),
                )
    else:
        profile = getattr(request.user, 'profile', None)
        form = RequestForm()

    return render(request, 'core/create_request.html', _create_request_context(form))


def request_list(request):
    # Default: closed requests are shadowed (hidden) for everyone.
    # They only appear when explicitly filtered (status=closed).
    qs = _visible_requests_for_user(request).order_by('-created_at')

    status = (request.GET.get('status') or '').strip()
    if status in (Request.STATUS_OPEN, Request.STATUS_PARTIALLY_FULFILLED, Request.STATUS_CLOSED):
        if status == Request.STATUS_CLOSED:
            # Explicitly opt-in to view closed.
            base = Request.objects.all()
            u = request.user
            if not u.is_authenticated:
                base = base.exclude(category='military')
            else:
                if not (u.is_staff or u.is_superuser):
                    p = getattr(u, 'profile', None)
                    if not (p and p.role in ('admin', 'military')):
                        base = base.exclude(category='military')
            qs = base.exclude(is_hidden=True).order_by('-created_at')
        qs = qs.filter(status=status)

    progress = (request.GET.get('progress') or '').strip()
    if progress in ('25', '50', '75'):
        # fulfilled_percent = round((total - remaining)/total * 100)
        # Use fulfilled_quantity threshold: fulfilled >= ceil(total * pct)
        pct = int(progress)
        # Approximate using integer math: fulfilled*100 >= total*pct
        # fulfilled = total - remaining
        qs = qs.extra(
            where=["( (total_quantity - remaining_quantity) * 100 ) >= ( total_quantity * %s )"],
            params=[pct],
        )

    ctx = {
        'requests': qs,
        'filter_status': status,
        'filter_progress': progress,
    }
    return render(request, 'core/request_list.html', ctx)


# 🔥 НОВА СТОРІНКА ДЕТАЛЕЙ
def request_detail(request, request_id):
    req = get_object_or_404(Request, id=request_id)
    # Hide military requests from civil / anonymous users (except owner or staff/admin).
    if req.category == 'military' and not _can_view_military_request(request, req):
        raise PermissionDenied
    # Staff moderation: hidden requests are only visible to staff/admin or the owner.
    if req.is_hidden:
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.is_staff or request.user.is_superuser:
            pass
        else:
            p = getattr(request.user, 'profile', None)
            if not (req.created_by_id == request.user.id or (p and p.role == 'admin')):
                raise PermissionDenied
    expire_pending_contributions_for_request(req)
    req.refresh_from_db()
    ctx = _request_detail_page_context(request, req)
    if ctx.get('is_owner'):
        ctx['close_form'] = RequestCloseForm()
        ctx['has_any_contributions'] = req.contributions.exists()
    return render(request, 'core/request_detail.html', ctx)


@login_required
@require_POST
def close_request(request, request_id: int):
    gate = _require_verification_submission_or_redirect(request)
    if gate:
        return gate
    req = get_object_or_404(Request, id=request_id)
    if req.created_by_id != request.user.id:
        raise PermissionDenied
    form = RequestCloseForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Enter a valid reason.')
        return redirect('request_detail', request_id=req.id)
    reason = (form.cleaned_data.get('reason') or '').strip()
    has_any = req.contributions.exists()
    if has_any and not reason:
        messages.error(request, 'A reason is required when there are contributions/proposals on this request.')
        return redirect('request_detail', request_id=req.id)
    req.status = Request.STATUS_CLOSED
    req.closed_at = timezone.now()
    req.closed_reason = reason
    req.save(update_fields=['status', 'closed_at', 'closed_reason'])
    # Notify existing conversations.
    for conv in Conversation.objects.filter(resource_request=req):
        _post_system_message(conv, f"Request was closed by owner. Reason: {reason or '—'}")
    messages.success(request, 'Request closed.')
    return redirect('request_detail', request_id=req.id)


# 🔥 ОСНОВНА ЛОГІКА
@login_required
def contribute(request, request_id):
    restricted = _require_not_restricted_or_redirect(request)
    if restricted:
        return restricted
    gate = _require_verification_submission_or_redirect(request)
    if gate:
        return gate
    req = get_object_or_404(Request, id=request_id)

    if request.method == 'POST':
        expire_pending_contributions_for_request(req)
        req.refresh_from_db()
        if req.created_by_id == request.user.id:
            messages.error(request, 'You cannot contribute to your own request.')
            return redirect('request_detail', request_id=req.id)
        if req.status == Request.STATUS_CLOSED:
            messages.error(request, 'This request is already closed.')
            return redirect('request_detail', request_id=req.id)
        form = ContributionProposeForm(request.POST, resource_request=req)
        if form.is_valid():
            contribution = Contribution(user=request.user, request=req)
            _assign_contribution_from_form(contribution, form.cleaned_data)
            try:
                contribution.full_clean()
                contribution.save()
                messages.success(
                    request,
                    'Your proposal was sent. The request owner will approve it before the send window and '
                    'verification code apply.',
                )
                if req.created_by_id and req.created_by_id != request.user.id:
                    conv = _get_or_create_conversation_for_request(req, request.user.id)
                    _post_system_message(conv, f"Contributor sent an offer (qty {contribution.quantity}). Awaiting owner review.")
                    messages.info(
                        request,
                        format_html(
                            'Chat with the request owner: <a href="{}">open conversation</a>.',
                            reverse('conversation_detail', args=[conv.id]),
                        ),
                    )
                return redirect('request_detail', request_id=req.id)
            except ValidationError as e:
                errd = getattr(e, 'error_dict', None) or getattr(e, 'message_dict', None)
                if errd:
                    for field, errs in errd.items():
                        if field in form.fields:
                            form.add_error(field, errs)
                        else:
                            messages.error(request, ' '.join(str(x) for x in errs))
                else:
                    messages.error(
                        request,
                        ' '.join(str(m) for m in getattr(e, 'messages', [])) or 'Invalid contribution.',
                    )
                return render(
                    request,
                    'core/request_detail.html',
                    _request_detail_page_context(request, req, propose_form=form),
                )
        else:
            return render(
                request,
                'core/request_detail.html',
                _request_detail_page_context(request, req, propose_form=form),
            )

    return redirect('request_detail', request_id=req.id)


@login_required
def revise_contribution(request, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id, user=request.user)
    if contribution.status != Contribution.STATUS_REVISION_REQUESTED:
        messages.error(request, 'Nothing to revise for this contribution.')
        return redirect('request_detail', request_id=contribution.request_id)
    req = contribution.request
    expire_pending_contributions_for_request(req)
    if request.method == 'POST':
        form = ContributionProposeForm(request.POST, resource_request=req)
        if form.is_valid():
            _assign_contribution_from_form(contribution, form.cleaned_data)
            contribution.status = Contribution.STATUS_PROPOSED
            try:
                contribution.full_clean()
                contribution.save()
                if req.created_by_id:
                    conv = _get_or_create_conversation_for_request(req, request.user.id)
                    _post_system_message(conv, "Contributor resubmitted an updated offer after changes requested.")
                messages.success(request, 'Updated proposal sent to the request owner.')
                return redirect('request_detail', request_id=req.id)
            except ValidationError as e:
                errd = getattr(e, 'error_dict', None) or getattr(e, 'message_dict', None)
                if errd:
                    for field, errs in errd.items():
                        if field in form.fields:
                            form.add_error(field, errs)
                        else:
                            messages.error(request, ' '.join(str(x) for x in errs))
                else:
                    messages.error(request, 'Could not save your update.')
    else:
        initial = {
            'quantity': contribution.quantity,
            'contrib_delivery_kind': contribution.contrib_delivery_kind
            or Request.DELIVERY_KIND_NOVA,
            'contrib_np_city_ref': contribution.contrib_np_city_ref,
            'contrib_np_warehouse_ref': contribution.contrib_np_warehouse_ref,
            'contrib_np_label': contribution.contrib_np_label,
            'contrib_up_postcode': contribution.contrib_up_postcode,
            'contrib_up_office_id': contribution.contrib_up_office_id,
            'contrib_up_label': contribution.contrib_up_label,
            'contrib_dropoff_note': contribution.contrib_dropoff_note,
        }
        form = ContributionProposeForm(initial=initial, resource_request=req)
    ctx = {'contribution': contribution, 'req': req, 'form': form}
    ctx.update(_shipping_config())
    return render(request, 'core/revise_contribution.html', ctx)


@login_required
@require_POST
def contribution_owner_action(request, contribution_id):
    contribution = get_object_or_404(
        Contribution.objects.select_related('request'),
        id=contribution_id,
    )
    req = contribution.request
    if req.created_by_id != request.user.id:
        raise PermissionDenied
    action = request.POST.get('action')
    note = (request.POST.get('note') or '').strip()
    if action == 'accept':
        if contribution.status != Contribution.STATUS_PROPOSED:
            messages.error(request, 'Only a pending proposal can be accepted.')
            return redirect('request_detail', request_id=req.id)
        try:
            contribution.status = Contribution.STATUS_PENDING
            contribution.full_clean()
            contribution.save()
            conv = _get_or_create_conversation_for_request(req, contribution.user_id)
            _post_system_message(
                conv,
                f"Owner accepted the offer (qty {contribution.quantity}). Send-by: {contribution.expires_at.strftime('%Y-%m-%d %H:%M UTC')}.",
            )
            messages.success(
                request,
                format_html(
                    'Contribution accepted. Contributor send-by: {} UTC · verification code {}.',
                    contribution.expires_at.strftime('%Y-%m-%d %H:%M'),
                    contribution.verification_code,
                ),
            )
        except ValidationError as e:
            contribution.refresh_from_db()
            messages.error(request, ' '.join(str(m) for m in getattr(e, 'messages', [])))
    elif action == 'decline':
        if contribution.status not in (
            Contribution.STATUS_PROPOSED,
            Contribution.STATUS_REVISION_REQUESTED,
        ):
            messages.error(request, 'This contribution cannot be declined in its current state.')
            return redirect('request_detail', request_id=req.id)
        contribution.status = Contribution.STATUS_DECLINED
        contribution.owner_note = note
        contribution.save(update_fields=['status', 'owner_note'])
        conv = _get_or_create_conversation_for_request(req, contribution.user_id)
        _post_system_message(conv, f"Owner declined the offer. Reason: {note or '—'}")
        messages.success(request, 'Contribution declined.')
    elif action == 'request_changes':
        if contribution.status != Contribution.STATUS_PROPOSED:
            messages.error(request, 'You can only request changes while a new proposal is awaiting review.')
            return redirect('request_detail', request_id=req.id)
        contribution.status = Contribution.STATUS_REVISION_REQUESTED
        contribution.owner_note = note or 'Please adjust your drop-off details or quantity.'
        contribution.save(update_fields=['status', 'owner_note'])
        conv = _get_or_create_conversation_for_request(req, contribution.user_id)
        _post_system_message(conv, f"Owner requested changes: {contribution.owner_note}")
        messages.success(request, 'Feedback sent; the contributor can update and resubmit.')
    else:
        messages.error(request, 'Unknown action.')
    return redirect('request_detail', request_id=req.id)


@login_required
def owner_open_chat(request, request_id: int, contributor_id: int):
    req = get_object_or_404(Request, id=request_id)
    if req.created_by_id != request.user.id:
        raise PermissionDenied
    conv, _ = Conversation.objects.get_or_create(
        resource_request=req,
        contributor_id=contributor_id,
        defaults={'receiver_id': request.user.id, 'last_activity_at': timezone.now()},
    )
    return redirect('conversation_detail', conversation_id=conv.id)


@login_required
@require_POST
def owner_bulk_action(request, request_id: int):
    req = get_object_or_404(Request, id=request_id)
    if req.created_by_id != request.user.id:
        raise PermissionDenied
    action = request.POST.get('action')
    note = (request.POST.get('note') or '').strip()
    if action != 'decline_all':
        messages.error(request, 'Unknown action.')
        return redirect('request_detail', request_id=req.id)
    qs = Contribution.objects.filter(
        request=req,
        status=Contribution.STATUS_PROPOSED,
    )
    n = qs.update(status=Contribution.STATUS_DECLINED, owner_note=note or 'Declined by request owner.')
    messages.success(request, f'Declined {n} proposal(s).')
    return redirect('request_detail', request_id=req.id)


@login_required
def dashboard(request):
    my_requests = Request.objects.filter(created_by=request.user).order_by('-created_at')
    my_contributions = list(
        Contribution.objects.filter(user=request.user).select_related('request').order_by('-created_at')
    )
    for c in my_contributions:
        expire_pending_contributions_for_request(c.request)
    for c in my_contributions:
        c.refresh_from_db()
    chat_map = {
        conv.resource_request_id: conv
        for conv in Conversation.objects.filter(contributor=request.user).select_related('resource_request')
    }
    for c in my_contributions:
        c.chat_conversation = chat_map.get(c.request_id)
    awaiting = (
        Contribution.objects.filter(
            request__created_by=request.user,
            status__in=(Contribution.STATUS_PROPOSED, Contribution.STATUS_REVISION_REQUESTED),
        )
        .values('request_id')
        .annotate(n=Count('id'))
    )
    awaiting_map = {row['request_id']: row['n'] for row in awaiting}
    for r in my_requests:
        r.awaiting_review = awaiting_map.get(r.id, 0)
    my_disputes = Dispute.objects.filter(created_by=request.user).select_related('contribution', 'contribution__request').order_by('-created_at')
    return render(
        request,
        'core/dashboard.html',
        {'my_requests': my_requests, 'my_contributions': my_contributions, 'my_disputes': my_disputes},
    )


@login_required
def my_requests(request):
    qs = Request.objects.filter(created_by=request.user).order_by('-created_at')
    status = (request.GET.get('status') or '').strip()
    if status in (Request.STATUS_OPEN, Request.STATUS_PARTIALLY_FULFILLED, Request.STATUS_CLOSED):
        qs = qs.filter(status=status)
    awaiting = (
        Contribution.objects.filter(
            request__created_by=request.user,
            status__in=(Contribution.STATUS_PROPOSED, Contribution.STATUS_REVISION_REQUESTED),
        )
        .values('request_id')
        .annotate(n=Count('id'))
    )
    awaiting_map = {row['request_id']: row['n'] for row in awaiting}
    reqs = list(qs)
    for r in reqs:
        r.awaiting_review = awaiting_map.get(r.id, 0)
    return render(request, 'core/my_requests.html', {'requests': reqs, 'status': status})


@login_required
def my_offers(request):
    qs = Contribution.objects.filter(user=request.user).select_related('request').order_by('-created_at')
    status = (request.GET.get('status') or '').strip()
    if status in {c for (c, _) in Contribution.STATUS_CHOICES}:
        qs = qs.filter(status=status)
    offers = list(qs)
    for c in offers:
        expire_pending_contributions_for_request(c.request)
    for c in offers:
        c.refresh_from_db()
    chat_map = {
        conv.resource_request_id: conv
        for conv in Conversation.objects.filter(contributor=request.user).select_related('resource_request')
    }
    for c in offers:
        c.chat_conversation = chat_map.get(c.request_id)
    return render(request, 'core/my_offers.html', {'offers': offers, 'status': status})


@login_required
def upload_proof(request, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id, user=request.user)
    expire_pending_contributions_for_request(contribution.request)
    contribution.refresh_from_db()
    if contribution.status != Contribution.STATUS_PENDING:
        messages.error(request, 'This contribution is no longer pending; proof cannot be uploaded.')
        return redirect('dashboard')
    if request.method == 'POST':
        form = ProofUploadForm(request.POST, request.FILES, instance=contribution)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proof uploaded. Awaiting admin review.')
            return redirect('/dashboard/')
    else:
        form = ProofUploadForm(instance=contribution)
    return render(request, 'core/upload_proof.html', {'contribution': contribution, 'form': form})


@login_required
def shipping_handoff_slip(request, contribution_id):
    """
    Printable slip + QR for counter handoff. Not an official Nova Poshta / Hermes label (no carrier API).
    """
    contribution = get_object_or_404(
        Contribution.objects.select_related('request'),
        id=contribution_id,
        user=request.user,
    )
    expire_pending_contributions_for_request(contribution.request)
    contribution.refresh_from_db()
    if contribution.status != Contribution.STATUS_PENDING:
        messages.error(
            request,
            'Shipping handoff slip is available only after the request owner accepts your proposal '
            '(active send window).',
        )
        return redirect('dashboard')
    req = contribution.request
    payload_text = build_qr_payload(contribution, req)
    try:
        qr_data_uri = qr_png_data_uri(payload_text)
    except Exception:
        messages.error(
            request,
            'Could not generate QR code. Install dependencies: pip install "qrcode[pil]" Pillow',
        )
        return redirect('dashboard')
    return render(
        request,
        'core/shipping_handoff_slip.html',
        {
            'contribution': contribution,
            'req': req,
            'qr_data_uri': qr_data_uri,
            'qr_payload_json': payload_text,
        },
    )


@login_required
def open_dispute(request, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id, user=request.user)
    if contribution.status != Contribution.STATUS_PENDING:
        messages.error(request, 'Disputes are available only during the active send window after the owner accepted your proposal.')
        return redirect('dashboard')
    if request.method == 'POST':
        form = DisputeForm(request.POST)
        if form.is_valid():
            dispute = form.save(commit=False)
            dispute.contribution = contribution
            dispute.created_by = request.user
            dispute.save()
            messages.success(request, 'Dispute opened. An admin will review it.')
            return redirect('/dashboard/')
    else:
        form = DisputeForm()
    return render(request, 'core/open_dispute.html', {'contribution': contribution, 'form': form})


@login_required
@require_POST
def report_request(request, request_id: int):
    restricted = _require_not_restricted_or_redirect(request)
    if restricted:
        return restricted
    req = get_object_or_404(Request, id=request_id)
    if req.created_by_id == request.user.id:
        messages.error(request, "You cannot report your own request.")
        return redirect("request_detail", request_id=req.id)
    reason_code = (request.POST.get("reason_code") or "").strip()
    note = (request.POST.get("note") or "").strip()
    if not reason_code:
        messages.error(request, "Select a reason for the report.")
        return redirect("request_detail", request_id=req.id)
    if reason_code == "other" and not note:
        messages.error(request, "Please add details for 'Other'.")
        return redirect("request_detail", request_id=req.id)
    reasons = {
        "absurd": "Абсурдний / тролінг",
        "porn": "Порнографія / 18+",
        "hate": "Хейт / дискримінація",
        "fraud": "Шахрайство / збір коштів",
        "military": "Військовий контент під “civil”",
        "spam": "Спам",
        "other": "Інше",
    }
    reason_label = reasons.get(reason_code, reason_code)
    from .models import ModerationReport

    # De-dupe: one open report per user+request within 24h
    since = timezone.now() - timedelta(hours=24)
    existing = ModerationReport.objects.filter(
        created_by=request.user,
        request=req,
        status=ModerationReport.STATUS_OPEN,
        created_at__gte=since,
    ).first()
    if existing:
        messages.info(request, "You already reported this request recently. Staff will review it.")
        return redirect("request_detail", request_id=req.id)
    reason_text = f"User report ({reason_label})"
    if note:
        reason_text = f"{reason_text}: {note}"
    ModerationReport.objects.create(
        created_by=request.user,
        request=req,
        snapshot_title=(req.title or "")[:255],
        snapshot_description=(req.description or ""),
        snapshot_category=(req.category or ""),
        reason=reason_text[:255],
        score=80,
    )
    messages.success(request, "Reported. Staff will review this request.")
    return redirect("request_detail", request_id=req.id)


@login_required
@require_POST
def withdraw_contribution(request, contribution_id: int):
    gate = _require_verification_submission_or_redirect(request)
    if gate:
        return gate
    c = get_object_or_404(Contribution.objects.select_related('request'), id=contribution_id, user=request.user)
    if c.status not in (Contribution.STATUS_PROPOSED, Contribution.STATUS_REVISION_REQUESTED):
        messages.error(request, 'Only offers awaiting owner review or changes can be withdrawn.')
        return redirect('dashboard')
    c.status = Contribution.STATUS_WITHDRAWN
    c.owner_note = ''
    c.save(update_fields=['status', 'owner_note'])
    if c.request.created_by_id:
        conv = _get_or_create_conversation_for_request(c.request, request.user.id)
        _post_system_message(conv, 'Contributor withdrew the offer.')
    messages.success(request, 'Offer withdrawn.')
    return redirect('dashboard')


@login_required
def message_center(request):
    conversations = (
        Conversation.objects.filter(Q(contributor=request.user) | Q(receiver=request.user))
        .select_related('resource_request', 'contributor', 'receiver')
        .order_by('-last_activity_at')
    )
    return render(request, 'core/message_center.html', {'conversations': conversations})


@login_required
def conversation_detail(request, conversation_id):
    conv = get_object_or_404(
        Conversation.objects.select_related('resource_request', 'contributor', 'receiver'),
        pk=conversation_id,
    )
    if request.user.id not in (conv.contributor_id, conv.receiver_id):
        raise PermissionDenied
    expire_pending_contributions_for_request(conv.resource_request)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                conversation=conv,
                sender=request.user,
                body=form.cleaned_data['body'].strip(),
            )
            conv.last_activity_at = timezone.now()
            conv.save(update_fields=['last_activity_at'])
            return redirect('conversation_detail', conversation_id=conv.id)
    else:
        form = MessageForm()

    chat_messages = conv.messages.select_related('sender').order_by('created_at')
    other_user = conv.receiver if request.user.id == conv.contributor_id else conv.contributor
    return render(
        request,
        'core/conversation_detail.html',
        {
            'conversation': conv,
            'chat_messages': chat_messages,
            'form': form,
            'other_user': other_user,
        },
    )