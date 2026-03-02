"""Pytest configuration: minimal Django settings for test suite."""

import django
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
            ],
            SECRET_KEY="prismtest-test-secret-key",
            USE_TZ=True,
        )
        django.setup()
