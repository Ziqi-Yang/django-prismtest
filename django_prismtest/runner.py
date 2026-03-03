"""Django test runner that uses PrismTestResult for beautiful output."""

from __future__ import annotations

import sys
import unittest

from django.db.backends.base.creation import BaseDatabaseCreation
from django.test.runner import DiscoverRunner

from django_prismtest.formatter import make_console
from django_prismtest.result import PrismTestResult


class PrismTestRunner(unittest.TextTestRunner):
    """A TextTestRunner that defaults to PrismTestResult."""

    resultclass = PrismTestResult

    def __init__(self, **kwargs):
        self._parallel = kwargs.pop("parallel", False)
        self._total_tests: int = 0
        super().__init__(**kwargs)

    def run(self, test):
        self._total_tests = test.countTestCases()
        return super().run(test)

    def _makeResult(self):
        result = super()._makeResult()
        result._parallel = self._parallel
        result._total_tests = self._total_tests
        return result


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
        kwargs["parallel"] = getattr(self, "parallel", 0) > 1
        return kwargs

    def setup_databases(self, **kwargs):
        if self.parallel <= 1:
            return super().setup_databases(**kwargs)

        console = make_console(file=sys.stderr)
        messages: list[str] = []
        original_log = BaseDatabaseCreation.log

        def _quiet_log(self_creation, msg):
            messages.append(msg)

        BaseDatabaseCreation.log = _quiet_log
        try:
            with console.status("[bold cyan]Setting up test databases…"):
                result = super().setup_databases(**kwargs)
        finally:
            BaseDatabaseCreation.log = original_log

        clone_count = sum(
            1 for m in messages if "Cloning" in m or "existing clone" in m
        )
        if clone_count:
            console.print(
                f"[pass]✔[/pass] Cloned [bold]{clone_count}[/bold] test databases"
            )

        return result

    def teardown_databases(self, old_config, **kwargs):
        if self.parallel <= 1:
            return super().teardown_databases(old_config, **kwargs)

        console = make_console(file=sys.stderr)
        messages: list[str] = []
        original_log = BaseDatabaseCreation.log

        def _quiet_log(self_creation, msg):
            messages.append(msg)

        BaseDatabaseCreation.log = _quiet_log
        try:
            with console.status("[bold cyan]Destroying test databases…"):
                super().teardown_databases(old_config, **kwargs)
        finally:
            BaseDatabaseCreation.log = original_log

        destroy_count = sum(
            1 for m in messages if "Destroying" in m or "Preserving" in m
        )
        if destroy_count:
            console.print(
                f"[pass]✔[/pass] Destroyed [bold]{destroy_count}[/bold] test databases"
            )
