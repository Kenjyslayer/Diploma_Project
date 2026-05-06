from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    """Allow Django staff/superusers or Profile.role == admin."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            return redirect_to_login(next=request.get_full_path())
        if u.is_staff or u.is_superuser:
            return view_func(request, *args, **kwargs)
        profile = getattr(u, "profile", None)
        if profile and profile.role == "admin":
            return view_func(request, *args, **kwargs)
        raise PermissionDenied

    return _wrapped
