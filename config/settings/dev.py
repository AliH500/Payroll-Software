"""Local development settings."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1"]

# In dev, no collectstatic step runs, so use the simple staticfiles storage
# instead of WhiteNoise's manifest-based one (which requires a manifest file).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
