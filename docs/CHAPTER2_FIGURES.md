# Рисунки розділу 2 (Mermaid)

Експорт у PNG/SVG: [mermaid.live](https://mermaid.live) або draw.io → **Insert → Advanced → Mermaid**.

---

## Рисунок 2.1 — Компонентна схема системи

```mermaid
flowchart LR
  subgraph clients["Клієнти"]
    WB[Веб-клієнт<br/>браузер]
    API[Клієнт API<br/>інтеграція]
  end

  K[Сервіс координації<br/>Django UI + REST /api/]
  A[Сервіс автентифікації<br/>OAuth2 /o/]
  DB[(PostgreSQL<br/>спільна БД)]
  OAS[OpenAPI<br/>/api/schema/]

  WB -->|HTTPS, cookies,<br/>CSRF| K
  API -->|HTTPS,<br/>Bearer JWT або OAuth2| K

  WB -->|HTTPS<br/>Authorization Code| A
  API -->|HTTPS<br/>token endpoint| A

  K <-->|SQL| DB
  A <-->|SQL| DB
  K --> OAS
```

---

## Рисунок 2.2 — Інформаційна модель даних (ER, узагальнено)

**Важливо при копіюванні:** у поле Mermaid (mermaid.live, draw.io) вставляй **лише** код діаграми — **без** рядків ` ```mermaid ` і ` ``` ` на початку й в кінці. Якщо інструмент сам додає обгортку — не дублюй її.

**Чому був `No diagram type detected`:** у багатьох середовищах (зокрема вбудований Mermaid у **draw.io**) тип **`erDiagram` не підключений або відключений** — парсер не розпізнає діаграму. Нижче — варіант **`classDiagram`**, який зазвичай рендериться скрізь; семантика та сама, що в ER.

Клас **`ResourceRequest`** на діаграмі = модель **`Request`** у коді Django (ім’я змінено, щоб уникнути збігів із глобальним `Request` у JS у деяких рендерерах).

```mermaid
classDiagram
  direction TB

  class AuthUser {
    int id
    string username
  }

  class Profile {
    int id
    string role
    string verification_status
    int is_verified
  }

  class ResourceRequest {
    int id
    string title
    string category
    string status
    int total_quantity
    int remaining_quantity
  }

  class Contribution {
    int id
    int quantity
    string status
    string verification_code
  }

  class Conversation {
    int id
  }

  class ChatMessage {
    int id
    string body
  }

  class ModerationReport {
    int id
    string reason
    string status
  }

  class AuditLogEntry {
    int id
    string action
  }

  class Dispute {
    int id
    string status
  }

  AuthUser "1" --> "1" Profile : has_profile
  AuthUser "1" --> "*" ResourceRequest : creates
  AuthUser "1" --> "*" Contribution : contributes
  ResourceRequest "1" --> "*" Contribution : contains
  ResourceRequest "1" --> "*" Conversation : thread_for
  AuthUser "1" --> "*" Conversation : participates
  Conversation "1" --> "*" ChatMessage : has
  ResourceRequest "1" --> "*" ModerationReport : reported_in
  Contribution "1" --> "*" Dispute : disputed
  AuthUser "1" --> "*" AuditLogEntry : acts
  ResourceRequest "1" --> "*" AuditLogEntry : targets_req
  Contribution "1" --> "*" AuditLogEntry : targets_contrib
```

У підписі до рисунка в Word: *зв’язок `AuthUser` → `Conversation` з міткою `participates` відображає дві ролі через поля `contributor_id` та `receiver_id`*. Клас **`ChatMessage`** = модель **`Message`**.

### Альтернатива: `erDiagram` (лише для Mermaid ≥ 8.6 з увімкненим ER)

Якщо на [mermaid.live](https://mermaid.live) `erDiagram` працює — можна лишити ER-нотацію там; у draw.io надійніше використовувати **`classDiagram`** вище.

---

## Рисунок 2.4 — Діаграма послідовностей OAuth2 і виклик REST API

```mermaid
sequenceDiagram
  autonumber
  participant U as Користувач
  participant B as Браузер / клієнт
  participant O as Сервіс OAuth2 /o/
  participant C as Сервіс координації /api/

  U->>B: Запуск авторизації клієнта
  B->>O: GET /o/authorize (client_id, redirect_uri, scope, state)
  O-->>B: Форма логіну та згоди
  U->>O: Логін, підтвердження scope
  O-->>B: HTTP redirect з authorization code
  B->>O: POST /o/token/ (code, client_id, client_secret або PKCE)
  O-->>B: access_token (+ refresh_token)
  B->>C: REST /api/ з Authorization Bearer access_token
  C-->>B: JSON-відповідь
```

---

## Рисунок 2.9 — Розгортання (Docker Compose, логічна схема)

```mermaid
flowchart TB
  subgraph internet["Мережа"]
    BR[Браузер користувача]
    EXT[Зовнішній API-клієнт]
  end

  subgraph compose["Docker Compose"]
    direction TB
    COORD["Контейнер coordination<br/>WSGI coordination<br/>порт 8000"]
    AUTH["Контейнер auth<br/>WSGI auth<br/>порт 8001"]
    PG[(PostgreSQL<br/>порт 5432)]
  end

  BR -->|HTTP/HTTPS<br/>UI + сесія| COORD
  EXT -->|HTTPS<br/>REST /api/| COORD
  BR -->|OAuth2<br/>/o/| AUTH
  EXT -->|OAuth2<br/>token| AUTH

  COORD <--> PG
  AUTH <--> PG
```

> Порти **8000 / 8001** — як у `ARCHITECTURE.md` для локального запуску; для продакшену підстав власні значення або підпис «умовні позначення».
