"""Serve uploaded files through Django (required when DEBUG=False on Render)."""

from __future__ import annotations

import mimetypes

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Contribution, Profile
from .permissions import staff_required

User = get_user_model()

_ALLOWED_VERIFICATION_FILES = frozenset({"passport", "reserve"})


def _open_field_file(field) -> FileResponse:
    if not field:
        raise Http404
    try:
        field.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    content_type, _ = mimetypes.guess_type(field.name)
    return FileResponse(field, content_type=content_type or "application/octet-stream")


def _is_staff_user(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == "admin")


@staff_required
def staff_verification_file(request, user_id: int, file_kind: str):
    if file_kind not in _ALLOWED_VERIFICATION_FILES:
        raise Http404
    target = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile: Profile = target.profile
    if file_kind == "passport":
        return _open_field_file(profile.passport_scan)
    return _open_field_file(profile.reserve_plus_pdf)


def profile_photo_file(request, user_id: int):
    if not request.user.is_authenticated:
        raise PermissionDenied
    target = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile: Profile = target.profile
    viewer = request.user
    if viewer.pk != target.pk and not _is_staff_user(viewer):
        if not profile.profile_photo_public:
            raise PermissionDenied
    return _open_field_file(profile.profile_photo)


def contribution_proof_file(request, contribution_id: int):
    if not request.user.is_authenticated:
        raise PermissionDenied
    contrib = get_object_or_404(
        Contribution.objects.select_related("request", "user"),
        pk=contribution_id,
    )
    viewer = request.user
    if not (
        _is_staff_user(viewer)
        or contrib.user_id == viewer.pk
        or contrib.request.created_by_id == viewer.pk
    ):
        raise PermissionDenied
    return _open_field_file(contrib.proof_file)
