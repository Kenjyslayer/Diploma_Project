# Прогін тестів для рисунка 4.1 (скриншот терміналу)

## Варіант A — Docker (як у CI / у вас уже спрацювало)

У корені репозиторію `Diploma/` (де лежить `docker-compose.yml`):

```powershell
cd C:\Users\yomad\Documents\Diploma
docker compose run --rm --no-deps -e DATABASE_URL= coordination bash -lc "cd diploma_project && python manage.py test core.tests -v 2"
```

**Чому `-e DATABASE_URL=`:** у образі за замовчуванням очікується Postgres на хості `db`. Якщо запускати **без** піднятого `docker compose up`, треба **скинути** `DATABASE_URL`, щоб тести йшли на **SQLite в пам’яті** (як у успішному прогоні).

Після `Ran 6 tests` і рядка **`OK`** зроби скриншот вікна PowerShell — це і є **рис. 4.1**.

---

## Варіант B — локальний Python (якщо встановлений Python 3.12+ і залежності)

```powershell
cd C:\Users\yomad\Documents\Diploma\diploma_project
$env:DATABASE_URL = ""
python manage.py test core.tests -v 2
```

Якщо `python` не знаходиться — використай шлях до інтерпретатора з твого venv.

---

## Що має бути видно на скрині

- рядок **`Found 6 test(s).`** (або після прогону видно 6 тестів);
- у кінці **`Ran 6 tests in ...s`** та **`OK`**.

Довгий список міграцій можна **не вміщати** в кадр — обріж знімок з моменту появи імен тестів (`test_login_writes_...`) до `OK`.

---

## Очікуваний фрагмент виводу (еталон)

```
test_login_writes_audit_log_entry ... ok
test_civil_military_keyword_detection ... ok
test_owner_accepts_proposal_sets_pending_and_reserves_quantity ... ok
test_oauth2_access_token_can_access_api_requests ... ok
test_civil_request_is_blocked_if_contains_military_terms ... ok
test_unverified_user_is_blocked_from_create_request_post ... ok

----------------------------------------------------------------------
Ran 6 tests in X.XXXs

OK
```
