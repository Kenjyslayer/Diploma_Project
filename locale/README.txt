This project uses Django i18n (gettext) for translations.

To generate/update .po files:
  python diploma_project/manage.py makemessages -l uk -l en -l de

To compile .mo files (or without GNU gettext on Windows):
  python diploma_project/tools/sync_i18n.py

Docker (after code changes):
  docker compose run --rm -v ./diploma_project:/app/diploma_project coordination bash -lc "pip install -q polib && python diploma_project/tools/sync_i18n.py"

Legacy overrides only:
  python diploma_project/tools/apply_translation_overrides.py
  then run sync_i18n.py to compile .mo

To compile .mo files with gettext:
  python diploma_project/manage.py compilemessages

On Windows, Django requires GNU gettext tools (msguniq/msgfmt). If you see:
  "Can't find msguniq"
install gettext, then restart the terminal/IDE.

Recommended install:
  - Windows: install "gettext" via Chocolatey (choco install gettext) OR use MSYS2/pacman gettext

