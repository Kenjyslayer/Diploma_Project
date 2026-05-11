# Threat model (short)

Scope: this document summarizes key threats for the coordination system and the concrete mitigations implemented in this repository.

## Assumptions
- Public internet access in production (Render), HTTPS enforced by platform and Django settings.
- Two web components: Coordination (UI+API) and Auth (OAuth2).
- Primary risks: account takeover, spam/abuse, privilege escalation, unsafe content, data leakage.

## Threats and mitigations

| Threat | Example | Impact | Mitigation (implementation) |
|---|---|---|---|
| Brute-force login | Attacker tries many passwords | Account takeover | Rate limiting `POST /login/` + per-IP+username keys (`diploma_project/core/middleware.py`, `RATE_LIMIT_RULES` in `diploma_project/diploma_project/settings.py`) |
| Token endpoint abuse | Spamming `POST /o/token/` or JWT token endpoint | DoS / credential stuffing | Rate limiting `POST /o/token/`, `POST /api/auth/jwt/token/` (`core/middleware.py`) |
| Request/report spam | Flooding request creation / reporting | Staff overload, DB growth | Rate limiting `POST /create/`, `POST /requests/*/report/` + moderation queue (`core/middleware.py`, `core/models.py: ModerationReport`) |
| Privilege escalation | User tries to access staff actions | Unauthorized admin actions | Server-side checks (`core/permissions.py`, `core/views_staff.py: @staff_required`) |
| Unsafe/military content under civil category | Civil user submits military items | Policy breach | Content policy validation in `Request.clean()` + moderation reports (`core/content_policy.py`, `core/moderation.py`, `core/models.py: Request`) |
| CSRF on browser actions | Forged POSTs from malicious site | Unauthorized state changes | Django CSRF middleware + cookie settings (see `MIDDLEWARE` and CSRF settings in `diploma_project/diploma_project/settings.py`) |
| Clickjacking | Framing UI to trick users | Unauthorized actions | `X-Frame-Options: DENY` (`core/middleware.py: SecurityHeadersMiddleware`) |
| MIME sniffing | Browser interprets files as HTML/JS | XSS / data exfiltration | `X-Content-Type-Options: nosniff` (`core/middleware.py`) |
| XSS via third-party scripts/styles | Injected resources | Session compromise | Content Security Policy tailored to used CDNs (`core/middleware.py: SecurityHeadersMiddleware`) |
| Missing accountability | Admin actions not traceable | Difficult incident response | Audit log entries for staff actions and key user actions (`core/models.py: AuditLogEntry`, `core/audit.py`, `core/views_staff.py`, `core/views.py`) |

## Notes for the report
- Rate limiting in this demo uses Django cache. For multi-instance production, use a shared cache backend (Redis) or enforce limits at reverse proxy/API gateway level.
- OAuth2 implementation follows standard Authorization Code flow; tokens are transmitted via `Authorization: Bearer ...` over HTTPS.

