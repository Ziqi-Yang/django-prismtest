"""Django test runner that uses PrismTestResult for beautiful output."""

from __future__ import annotations

import unittest

from django.test.runner import DiscoverRunner

from django_prismtest.result import PrismTestResult


class PrismTestRunner(unittest.TextTestRunner):
    """A TextTestRunner that defaults to PrismTestResult."""

    resultclass = PrismTestResult


class PrismDiscoverRunner(DiscoverRunner):
    """Drop-in replacement for Django's DiscoverRunner with prism output.

    Usage in Django settings::

        TEST_RUNNER = "django_prismtest.runner.PrismDiscoverRunner"

    Optional settings::

        # Highlight your project code in tracebacks
        PRISMTEST_HIGHLIGHT_PATH = "/path/to/your/project/"
    """

    test_runner = PrismTestRunner

    def get_resultclass(self):
        # Honour Django's --debug-sql and --pdb flags
        parent = super().get_resultclass()
        if parent is not None:
            # debug-sql or pdb mode requested – defer to Django's classes
            return parent
        return PrismTestResult

    def get_test_runner_kwargs(self):
        kwargs = super().get_test_runner_kwargs()
        kwargs["resultclass"] = self.get_resultclass()
        return kwargs
