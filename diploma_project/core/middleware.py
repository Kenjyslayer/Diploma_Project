from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse


def _client_ip(request: HttpRequest) -> str:
    # For local/docker demo behind no proxy this is enough.
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return xff or (request.META.get("REMOTE_ADDR") or "unknown")


@dataclass(frozen=True)
class RateRule:
    window_seconds: int
    max_requests: int
    key_prefix: str
    include_username: bool = False


def _match_rule(request: HttpRequest) -> RateRule | None:
    """
    Path-based rate limiting.

    This is intentionally simple for diploma demo. For multi-instance production,
    use a shared cache (Redis) and/or a reverse proxy rate limiter.
    """

    rules: dict[str, dict] = getattr(settings, "RATE_LIMIT_RULES", {})
    path = request.path or "/"
    method = (request.method or "GET").upper()

    # Exact match first
    key = f"{method} {path}"
    if key in rules:
        r = rules[key]
        return RateRule(
            int(r["window_seconds"]),
            int(r["max_requests"]),
            str(r.get("key_prefix") or key),
            bool(r.get("include_username") or False),
        )

    # Prefix matches (e.g. POST /requests/report/*)
    for k, r in rules.items():
        if not k.endswith("*"):
            continue
        if not k.startswith(f"{method} "):
            continue
        prefix = k[len(method) + 1 : -1]  # drop "METHOD " and trailing "*"
        if path.startswith(prefix):
            return RateRule(
                int(r["window_seconds"]),
                int(r["max_requests"]),
                str(r.get("key_prefix") or k),
                bool(r.get("include_username") or False),
            )

    return None


class RateLimitMiddleware:
    """
    Returns HTTP 429 when rate limit exceeded for sensitive endpoints:
    - login (anti-bruteforce)
    - token endpoints (/o/token/, /api/auth/jwt/token/)
    - report/create endpoints (anti-spam)
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.cache = caches[getattr(settings, "RATE_LIMIT_CACHE_ALIAS", "default")]

    def __call__(self, request: HttpRequest) -> HttpResponse:
        rule = _match_rule(request)
        if not rule:
            return self.get_response(request)

        ip = _client_ip(request)
        bucket = int(time.time()) // max(1, rule.window_seconds)
        username = ""
        if rule.include_username:
            username = (request.POST.get("username") or request.POST.get("client_id") or "").strip().lower()
        cache_key = f"rl:{rule.key_prefix}:{ip}:{username}:{bucket}"

        try:
            current = self.cache.get(cache_key)
            if current is None:
                self.cache.set(cache_key, 1, timeout=rule.window_seconds + 5)
                current = 1
            else:
                try:
                    current = int(current) + 1
                except Exception:
                    current = 999999
                self.cache.set(cache_key, current, timeout=rule.window_seconds + 5)
        except Exception:
            # If cache is misconfigured, do not block the request.
            return self.get_response(request)

        if current > rule.max_requests:
            resp = HttpResponse("Too Many Requests", status=429, content_type="text/plain; charset=utf-8")
            resp["Retry-After"] = str(rule.window_seconds)
            return resp

        return self.get_response(request)


class SecurityHeadersMiddleware:
    """
    Adds security headers and a CSP compatible with our CDN assets.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        resp = self.get_response(request)

        resp.setdefault("X-Frame-Options", "DENY")
        resp.setdefault("X-Content-Type-Options", "nosniff")
        resp.setdefault("Referrer-Policy", "same-origin")

        # CSP: allow Bootstrap/Icons/Fonts CDN used in templates.
        csp = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
        )
        resp.setdefault("Content-Security-Policy", csp)
        return resp

