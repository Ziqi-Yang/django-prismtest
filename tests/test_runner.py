"""Tests for the PrismDiscoverRunner."""

import unittest

from django.test.runner import DiscoverRunner

from django_prismtest.result import PrismTestResult
from django_prismtest.runner import PrismDiscoverRunner, PrismTestRunner


class TestPrismTestRunner(unittest.TestCase):
    def test_resultclass_is_prism(self):
        assert PrismTestRunner.resultclass is PrismTestResult


class TestPrismDiscoverRunner(unittest.TestCase):
    def test_inherits_discover_runner(self):
        assert issubclass(PrismDiscoverRunner, DiscoverRunner)

    def test_test_runner_is_prism(self):
        assert PrismDiscoverRunner.test_runner is PrismTestRunner

    def test_get_resultclass_returns_prism(self):
        runner = PrismDiscoverRunner(verbosity=0)
        assert runner.get_resultclass() is PrismTestResult

    def test_debug_sql_defers_to_parent(self):
        runner = PrismDiscoverRunner(verbosity=0, debug_sql=True)
        result_cls = runner.get_resultclass()
        # Should return Django's DebugSQLTextTestResult, not Prism
        assert result_cls is not PrismTestResult
