# Architecture (Coordination + Auth/Verification)

This repository implements a coordination system for volunteer/humanitarian help with **secure user verification**.

## Components

```mermaid
flowchart LR
  userBrowser[WebClient_Browser] -->|HTTPS_Cookies_CSRF| coordination[CoordinationService_Django]
  apiClient[APIClient_VolunteerCenter] -->|HTTPS_BearerToken_JWT_or_OAuth2| coordination

  userBrowser -->|HTTPS_OAuth2_AuthorizeCode| auth[AuthVerificationService_Django]
  apiClient -->|HTTPS_OAuth2_Token| auth

  coordination <-->|PostgreSQL| db[(Database_PostgreSQL)]
  auth <-->|PostgreSQL| db

  coordination -->|OpenAPI_JSON| openapi[OpenAPI_Schema]
```

### Service entrypoints
- **Coordination service** (UI + REST API): `diploma_project/wsgi_coordination.py` + `diploma_project/urls_coordination.py`
- **Auth/Verification service** (OAuth2 endpoints): `diploma_project/wsgi_auth.py` + `diploma_project/urls_auth.py`

Both services share the same Django settings module and the same database for consistency.

## Network interfaces

### Coordination REST API
- Base path: `/api/`
- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/swagger/`
- ReDoc: `/api/docs/redoc/`

### Auth endpoints
- OAuth2 base: `/o/` (HTML index with links); flows use `/o/authorize/`, `POST /o/token/`, etc.
- JWT endpoints (API login/refresh):\n+  - `/api/auth/jwt/token/`\n+  - `/api/auth/jwt/refresh/`

## Authentication & authorization

### Web UI (browser)
- Uses **Django sessions** with CSRF protection (cookie-based).

### REST API (machine-to-machine / integrations)
API accepts **Bearer tokens** via `Authorization: Bearer <token>`:\n+- **JWT** (SimpleJWT): for direct API login in controlled environments.\n+- **OAuth2 access tokens** (django-oauth-toolkit): for standard client integrations.\n+
Authorization (RBAC) is enforced by server-side checks (staff/superuser + verified users + ownership rules).

## Sequence diagrams

### Registration → verification → ability to post

```mermaid
sequenceDiagram
  participant U as User
  participant C as CoordinationService
  participant DB as Database

  U->>C: Register (web form)
  C->>DB: Create User + Profile (verification_status=pending/not_submitted)
  U->>C: Upload verification docs
  C->>DB: Store docs + set status=pending
  U->>C: Attempt create request
  C->>C: Gate by verification_status
  C-->>U: Allowed only when verified
```

### OAuth2: authorize code → access token → call API

```mermaid
sequenceDiagram
  participant U as User
  participant B as Browser
  participant A as AuthService
  participant C as CoordinationService

  U->>B: Open client app
  B->>A: GET /o/authorize (client_id, scope)
  A-->>B: Login/consent (session)
  B->>A: POST consent
  A-->>B: Redirect with code
  B->>A: POST /o/token (code + client_secret)
  A-->>B: access_token + refresh_token
  B->>C: GET /api/requests (Authorization: Bearer access_token)
  C-->>B: JSON response
```

### Contribution workflow (propose → approve → proof → verify)

```mermaid
sequenceDiagram
  participant Contrib as Contributor
  participant Owner as RequestOwner
  participant C as CoordinationService
  participant DB as Database
  participant Staff as StaffAdmin

  Contrib->>C: POST contribution proposal
  C->>DB: Create Contribution(status=proposed)
  Owner->>C: Owner action approve/decline/request_changes
  C->>DB: Update status (pending/declined/revision_requested)
  Contrib->>C: Upload proof file (if required)
  C->>DB: Store proof_file
  Staff->>C: Verify contribution
  C->>DB: status=verified
```

## Local run (two services)

If Docker is installed, use `docker-compose.yml` to start:\n+- coordination: `http://localhost:8000`\n+- auth: `http://localhost:8001` (OAuth2 endpoints)\n+\n+Both point to the same Postgres container.\n+
