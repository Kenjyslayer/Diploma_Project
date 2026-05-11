import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diploma_project.settings_coordination")

application = get_wsgi_application()

