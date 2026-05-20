"""Settings for the test suite. Uses Postgres so RLS/tenant tests run end-to-end."""

import os

# pytest can be invoked before .env is loaded; supply a deterministic dev secret.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-not-for-real-environments")
os.environ.setdefault("DJANGO_DEBUG", "False")

from .base import *

# Fast hashing for tests; never reachable from non-test settings.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

ALLOWED_HOSTS = ["testserver", "localhost", ".localhost"]
TENANT_BASE_DOMAIN = "localhost"

# Deterministic test key (NEVER reuse in any non-test environment).
FIELD_ENCRYPTION_KEYS = ["zN9hN5JRX9-4y6jVbR9p2NfYpVQXdGtN5wXgQjJZ7dQ="]

# Avoid WhiteNoise's manifest-based static-file resolution in tests
# (no collectstatic runs, so the manifest doesn't exist).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
