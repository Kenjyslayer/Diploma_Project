This project uses Django i18n (gettext) for translations.

To generate/update .po files:
  python diploma_project/manage.py makemessages -l uk -l en -l de

To compile .mo files:
  python diploma_project/manage.py compilemessages

On Windows, Django requires GNU gettext tools (msguniq/msgfmt). If you see:
  "Can't find msguniq"
install gettext, then restart the terminal/IDE.

Recommended install:
  - Windows: install "gettext" via Chocolatey (choco install gettext) OR use MSYS2/pacman gettext

