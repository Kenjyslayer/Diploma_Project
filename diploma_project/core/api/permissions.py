from rest_framework.permissions import BasePermission


class IsVerifiedAndNotBanned(BasePermission):
    """
    Mirrors the UI gating: verified users can act; banned users cannot.
    Staff/superusers are allowed.
    """

    message = "Account must be verified and not banned."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        profile = getattr(user, "profile", None)
        if not profile:
            return False
        if profile.banned_at:
            return False
        return profile.verification_status == "verified"


class IsRequestOwnerOrStaff(BasePermission):
    message = "You must be the request owner or staff."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        return getattr(obj, "created_by_id", None) == user.id


class IsContributionOwnerRequestOwnerOrStaff(BasePermission):
    message = "You must be the contributor, request owner, or staff."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        if getattr(obj, "user_id", None) == user.id:
            return True
        req = getattr(obj, "request", None)
        return bool(req and getattr(req, "created_by_id", None) == user.id)

