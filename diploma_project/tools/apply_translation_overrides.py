from __future__ import annotations

import sys
from pathlib import Path


def apply_overrides(po_path: Path, overrides: dict[str, str]) -> int:
    lines = po_path.read_text(encoding="utf-8").splitlines(True)
    out: list[str] = []
    i = 0
    changed = 0

    current_msgid: str | None = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("msgid "):
            current_msgid = line[len("msgid ") :].strip().strip('"')
            out.append(line)
            i += 1
            continue
        if line.startswith("msgstr ") and current_msgid and current_msgid in overrides:
            # Replace only simple one-line msgstr entries.
            out.append('msgstr "' + overrides[current_msgid].replace('"', '\\"') + '"\n')
            changed += 1
            i += 1
            # Drop any continuation lines for msgstr (rare in this project strings).
            while i < len(lines) and lines[i].startswith('"'):
                i += 1
            continue
        out.append(line)
        i += 1

    po_path.write_text("".join(out), encoding="utf-8")
    return changed


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    uk = {
        "MVP": "MVP",
        "Bootstrap 5": "Bootstrap 5",
        "Create an account": "Створити акаунт",
        "Preferred drop-off point": "Бажане відділення/пункт",
        "City": "Місто",
        "Branch / parcel locker": "Відділення / поштомат",
        "Select branch…": "Виберіть відділення…",
        "Find offices": "Знайти відділення",
        "Office line": "Рядок відділення",
        "Already registered?": "Вже зареєстровані?",
        "Owner": "Власник",
        "Reason": "Причина",
        "Select…": "Виберіть…",
        "Details (optional)": "Деталі (необов’язково)",
        "Short explanation…": "Коротке пояснення…",
        "Send report": "Надіслати скаргу",
        "Closed by owner": "Закрито власником",
        "Progress": "Прогрес",
        "Delivery destination": "Адреса доставки",
        "Notes": "Нотатки",
        "No extra notes beyond manual coordination.": "Додаткових нотаток немає — узгодження вручну.",
        "Bulk action (optional note applied to all)": "Групова дія (необов’язкова нотатка застосовується до всіх)",
        "Reason (optional)…": "Причина (необов’язково)…",
        "Decline all proposals": "Відхилити всі пропозиції",
        "qty": "к-ть",
        "You requested changes": "Ви попросили зміни",
        "Contributor Nova Poshta": "Внесок: Нова Пошта",
        "Contributor Ukrposhta": "Внесок: Укрпошта",
        "Optional note (decline / request changes)": "Нотатка (для відхилення / запиту змін)",
        "Explain what should change…": "Поясніть, що потрібно змінити…",
        "Accept": "Прийняти",
        "Decline": "Відхилити",
        "Waiting for the contributor to resubmit after your feedback.": "Очікуємо, поки користувач внесе правки та надішле пропозицію знову.",
        "Owner actions": "Дії власника",
        "You can edit this request or close it if it’s no longer needed.": "Ви можете відредагувати запит або закрити його, якщо він більше не потрібен.",
        "Close reason": "Причина закриття",
        "required because there are contributions/proposals": "обов’язково, бо є внески/пропозиції",
        "optional": "необов’язково",
        "Propose a contribution": "Запропонувати внесок",
        "Could not send proposal.": "Не вдалося надіслати пропозицію.",
        "Quantity": "Кількість",
        "Your drop-off (carrier)": "Ваш пункт відправки (перевізник)",
        "Select warehouse…": "Виберіть відділення…",
        "Configure Ukrposhta API env vars, or type the office line manually.": "Налаштуйте змінні середовища Ukrposhta API або введіть рядок відділення вручну.",
        "How will you ship?": "Як ви відправите?",
        "Send proposal": "Надіслати пропозицію",
        "This request is closed (fully fulfilled).": "Цей запит закрито (повністю виконано).",
        "Please": "Будь ласка",
        "log in": "увійдіть",
        "to contribute.": "щоб зробити внесок.",
        "Contributions": "Внески",
        "Django admin": "Адмінка Django",
        "Exit to site": "Вийти на сайт",
        "Operations overview": "Огляд операцій",
        "Open disputes →": "Відкриті суперечки →",
        "Verifications pending": "Верифікації в очікуванні",
        "Review verifications →": "Перевірити верифікації →",
        "Moderation reports open": "Відкриті звіти модерації",
        "Review reports →": "Переглянути звіти →",
        "Quick links": "Швидкі посилання",
        "Filters": "Фільтри",
        "All": "Усі",
        "Banned": "Забанені",
        "Restricted": "Обмежені",
        "Verification pending": "Верифікація в очікуванні",
        "Verification rejected": "Верифікацію відхилено",
        "Not verified": "Не верифіковані",
        "Username": "Логін",
        "Email": "Email",
        "Role": "Роль",
        "Verification": "Верифікація",
        "Moderation status": "Статус модерації",
        "Quick actions": "Швидкі дії",
        "verified": "верифіковано",
        "pending": "очікує",
        "rejected": "відхилено",
        "not submitted": "не подано",
        "banned": "забанено",
        "restricted": "обмежено",
        "until": "до",
        "ok": "ок",
        "User": "Користувач",
        "Temp restrict": "Тимчасово обмежити",
        "Ban": "Бан",
        "Unban": "Розбанити",
        "You cannot delete yourself.": "Ви не можете видалити самі себе.",
        "You cannot delete a superuser.": "Не можна видалити superuser.",
        "You cannot change your own admin status here.": "Тут не можна змінювати свій власний статус адміна.",
        "Set your preferred drop-off point in Profile first.": "Спочатку вкажіть бажане відділення в Профілі.",
        "Civil accounts cannot create military requests.": "Цивільні акаунти не можуть створювати військові запити.",
        "You must be verified to create military requests.": "Щоб створювати військові запити, потрібно бути верифікованим.",
        "Enter a valid reason.": "Вкажіть коректну причину.",
        "Closed requests cannot be edited.": "Закриті запити не можна редагувати.",
        "User has no profile.": "Користувач не має профілю.",
        "Unknown action.": "Невідома дія.",
        "Cannot approve without a passport scan.": "Неможливо підтвердити без скану паспорта.",
        'Military verification requires a "Резерв+" PDF.': 'Військова верифікація вимагає PDF "Резерв+".',
        "User %(username)s permanently banned.": "Користувача %(username)s забанено назавжди.",
        "Unknown moderation action.": "Невідома дія модерації.",
        "Request #%(id)s hidden.": "Запит #%(id)s приховано.",
        "Warning text is required.": "Текст попередження є обов’язковим.",
        "Warning added to request #%(id)s.": "Додано попередження до запиту #%(id)s.",
        "Warning cleared for request #%(id)s.": "Попередження для запиту #%(id)s очищено.",
        'Type "delete" in confirmation to delete the request.': 'Введіть "delete" у полі підтвердження, щоб видалити запит.',
        "Cannot delete a request that has contributions. Hide it instead.": "Неможливо видалити запит із внесками. Краще приховайте його.",
        "Cannot verify without an uploaded proof file.": "Неможливо верифікувати без завантаженого підтвердження.",
        "Approve the contribution first, then verify after proof.": "Спочатку підтвердьте внесок, потім верифікуйте після підтвердження.",
        "Contribution #%(id)s updated (%(status)s).": "Внесок #%(id)s оновлено (%(status)s).",
    }

    de = {
        "Dashboard": "Dashboard",
        "Admin": "Admin",
        "MVP": "MVP",
        "Django templates": "Django-Vorlagen",
        "Bootstrap 5": "Bootstrap 5",
        "Nova Poshta / Ukrposhta keys via environment variables": "Nova-Poshta-/Ukrposhta-Schlüssel über Umgebungsvariablen",
        "Status": "Status",
        "Code": "Code",
        "Chat": "Chat",
        "Browse needs, contribute partial quantities, and coordinate delivery.": "Durchsuche Bedarfe, unterstütze mit Teilmengen und koordiniere die Lieferung.",
        "Your account is banned from posting and contributing.": "Dein Konto ist gesperrt. Du kannst keine Anfragen erstellen oder Beiträge leisten.",
        "Account type changed. Please re-upload verification documents below.": "Kontotyp geändert. Bitte lade die Verifizierungsdokumente unten erneut hoch.",
        "Set your preferred drop-off point in Profile first.": "Lege zuerst deine bevorzugte Abgabestelle im Profil fest.",
        "Back": "Zurück",
        "Please fix the errors below.": "Bitte behebe die Fehler unten.",
        "Title": "Titel",
        "Category": "Kategorie",
        "Total quantity": "Gesamtmenge",
        "Save changes": "Änderungen speichern",
        "Cancel": "Abbrechen",
        "Create an account": "Konto erstellen",
        "Preferred drop-off point": "Bevorzugte Abgabestelle",
        "City": "Stadt",
        "Branch / parcel locker": "Filiale / Paketautomat",
        "Select branch…": "Filiale auswählen…",
        "Find offices": "Filialen finden",
        "Office line": "Filialzeile",
        "Already registered?": "Bereits registriert?",
        "Owner": "Ersteller",
        "Reason": "Grund",
        "Select…": "Auswählen…",
        "Details (optional)": "Details (optional)",
        "Short explanation…": "Kurze Erklärung…",
        "Send report": "Meldung senden",
        "Closed by owner": "Vom Ersteller geschlossen",
        "Progress": "Fortschritt",
        "Delivery destination": "Lieferziel",
        "Notes": "Notizen",
        "No extra notes beyond manual coordination.": "Keine zusätzlichen Notizen – manuelle Abstimmung.",
        "Bulk action (optional note applied to all)": "Sammelaktion (optional, Notiz gilt für alle)",
        "Reason (optional)…": "Grund (optional)…",
        "Decline all proposals": "Alle Vorschläge ablehnen",
        "qty": "Menge",
        "You requested changes": "Du hast Änderungen angefordert",
        "Contributor Nova Poshta": "Beitrag: Nova Poshta",
        "Contributor Ukrposhta": "Beitrag: Ukrposhta",
        "Optional note (decline / request changes)": "Optionale Notiz (ablehnen / Änderungen anfordern)",
        "Explain what should change…": "Erkläre, was geändert werden soll…",
        "Accept": "Annehmen",
        "Decline": "Ablehnen",
        "Waiting for the contributor to resubmit after your feedback.": "Warte, bis der Beitragende nach deinem Feedback erneut einreicht.",
        "Owner actions": "Aktionen des Erstellers",
        "You can edit this request or close it if it’s no longer needed.": "Du kannst diese Anfrage bearbeiten oder schließen, wenn sie nicht mehr benötigt wird.",
        "Close reason": "Schließgrund",
        "required because there are contributions/proposals": "erforderlich, da es Beiträge/Vorschläge gibt",
        "optional": "optional",
        "Propose a contribution": "Beitrag vorschlagen",
        "Could not send proposal.": "Vorschlag konnte nicht gesendet werden.",
        "Quantity": "Menge",
        "Your drop-off (carrier)": "Deine Abgabe (Versanddienst)",
        "Select warehouse…": "Filiale auswählen…",
        "Configure Ukrposhta API env vars, or type the office line manually.": "Konfiguriere die Ukrposhta-API-Variablen oder gib die Filialzeile manuell ein.",
        "How will you ship?": "Wie wirst du versenden?",
        "Send proposal": "Vorschlag senden",
        "This request is closed (fully fulfilled).": "Diese Anfrage ist geschlossen (vollständig erfüllt).",
        "Please": "Bitte",
        "log in": "anmelden",
        "to contribute.": "um beizutragen.",
        "Details": "Details",
        "Staff": "Team",
        "Administration": "Verwaltung",
        "Users": "Benutzer",
        "Verifications": "Verifizierungen",
        "Contributions": "Beiträge",
        "Django admin": "Django-Admin",
        "Exit to site": "Zur Seite",
        "Operations overview": "Operationsübersicht",
        "Open disputes →": "Offene Streitfälle →",
        "Verifications pending": "Ausstehende Verifizierungen",
        "Review verifications →": "Verifizierungen prüfen →",
        "Moderation reports open": "Offene Moderationsmeldungen",
        "Review reports →": "Meldungen prüfen →",
        "Quick links": "Schnellzugriff",
        "Filters": "Filter",
        "All": "Alle",
        "Banned": "Gesperrt",
        "Restricted": "Eingeschränkt",
        "Verification pending": "Verifizierung ausstehend",
        "Verification rejected": "Verifizierung abgelehnt",
        "Not verified": "Nicht verifiziert",
        "Username": "Benutzername",
        "Email": "E‑Mail",
        "Role": "Rolle",
        "Verification": "Verifizierung",
        "Moderation status": "Moderationsstatus",
        "Quick actions": "Schnellaktionen",
        "verified": "verifiziert",
        "pending": "ausstehend",
        "rejected": "abgelehnt",
        "not submitted": "nicht eingereicht",
        "banned": "gesperrt",
        "restricted": "eingeschränkt",
        "until": "bis",
        "ok": "ok",
        "User": "Benutzer",
        "Note…": "Notiz…",
        "Temp restrict": "Temporär einschränken",
        "Ban": "Sperren",
        "Unban": "Entsperren",
        "You cannot delete yourself.": "Du kannst dich nicht selbst löschen.",
        "You cannot delete a superuser.": "Du kannst keinen Superuser löschen.",
        "You cannot change your own admin status here.": "Du kannst hier deinen eigenen Admin-Status nicht ändern.",
        "Delete this user?": "Diesen Benutzer löschen?",
        "Delete user": "Benutzer löschen",
    }

    base = Path(__file__).resolve().parents[1]  # diploma_project/
    n1 = apply_overrides(base / "locale" / "uk" / "LC_MESSAGES" / "django.po", uk)
    n2 = apply_overrides(base / "locale" / "de" / "LC_MESSAGES" / "django.po", de)
    print("applied", {"uk": n1, "de": n2})


if __name__ == "__main__":
    main()

