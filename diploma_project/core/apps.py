from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from . import models
        # Optional: bootstrap a superuser in hosted envs where shell access is unavailable.
        # Controlled purely by environment variables; safe + idempotent.
        try:
            import os

            from django.contrib.auth import get_user_model
            from django.db.utils import OperationalError, ProgrammingError

            User = get_user_model()
            username = (os.environ.get("BOOTSTRAP_ADMIN_USERNAME") or "").strip()
            password = (os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
            email = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip()
            enabled = (os.environ.get("BOOTSTRAP_ADMIN_ENABLED") or "").strip().lower() in ("1", "true", "yes")
            if not enabled:
                return
            if not (username and password):
                return
            try:
                if User.objects.filter(is_superuser=True).exists():
                    return
                if User.objects.filter(username=username).exists():
                    return
                User.objects.create_superuser(username=username, email=email or None, password=password)
            except (OperationalError, ProgrammingError):
                # DB not ready yet (migrations), skip.
                return
        except Exception:
            return