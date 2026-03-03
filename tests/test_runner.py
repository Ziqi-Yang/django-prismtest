"""Tests for the PrismDiscoverRunner."""

import io
import unittest
from unittest.mock import patch

from django.db.backends.base.creation import BaseDatabaseCreation
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


class TestSetupDatabasesParallel(unittest.TestCase):
    """Tests for parallel DB log suppression in setup_databases."""

    def _make_runner(self, parallel=4):
        runner = PrismDiscoverRunner(verbosity=0)
        runner.parallel = parallel
        return runner

    def test_suppresses_log_in_parallel(self):
        runner = self._make_runner(parallel=4)

        def fake_setup(self_runner, **kwargs):
            # Simulate Django calling BaseDatabaseCreation.log during setup
            creation = type("FakeCreation", (), {})()
            for i in range(4):
                BaseDatabaseCreation.log(
                    creation, f"Cloning test database for alias 'default_{i}'..."
                )
            return [("default", {})]

        with patch.object(
            DiscoverRunner, "setup_databases", fake_setup
        ), patch("sys.stderr", new_callable=io.StringIO) as fake_stderr:
            result = runner.setup_databases()

        output = fake_stderr.getvalue()
        # Individual "Cloning" messages should NOT appear
        assert "Cloning test database" not in output
        # Summary line should appear
        assert "Cloned" in output
        assert "4" in output
        assert result == [("default", {})]

    def test_no_change_when_not_parallel(self):
        runner = self._make_runner(parallel=1)
        sentinel = object()

        with patch.object(
            DiscoverRunner, "setup_databases", return_value=sentinel
        ) as mock_setup:
            result = runner.setup_databases()

        mock_setup.assert_called_once()
        assert result is sentinel

    def test_log_restored_on_exception(self):
        runner = self._make_runner(parallel=4)
        original_log = BaseDatabaseCreation.log

        def exploding_setup(self_runner, **kwargs):
            raise RuntimeError("boom")

        with patch.object(DiscoverRunner, "setup_databases", exploding_setup):
            with self.assertRaises(RuntimeError):
                runner.setup_databases()

        # log must be restored even after an exception
        assert BaseDatabaseCreation.log is original_log


class TestTeardownDatabasesParallel(unittest.TestCase):
    """Tests for parallel DB log suppression in teardown_databases."""

    def _make_runner(self, parallel=4):
        runner = PrismDiscoverRunner(verbosity=0)
        runner.parallel = parallel
        return runner

    def test_suppresses_log_in_parallel(self):
        runner = self._make_runner(parallel=4)

        def fake_teardown(self_runner, old_config, **kwargs):
            creation = type("FakeCreation", (), {})()
            for i in range(4):
                BaseDatabaseCreation.log(
                    creation, f"Destroying test database for alias 'default_{i}'..."
                )

        with patch.object(
            DiscoverRunner, "teardown_databases", fake_teardown
        ), patch("sys.stderr", new_callable=io.StringIO) as fake_stderr:
            runner.teardown_databases(old_config=[("default", {})])

        output = fake_stderr.getvalue()
        # Individual per-worker messages should NOT appear
        assert "Destroying test database for alias" not in output
        # Summary line should appear
        assert "Destroyed" in output
        assert "4" in output

    def test_no_change_when_not_parallel(self):
        runner = self._make_runner(parallel=1)

        with patch.object(
            DiscoverRunner, "teardown_databases"
        ) as mock_teardown:
            runner.teardown_databases(old_config=[])

        mock_teardown.assert_called_once()

    def test_log_restored_on_exception(self):
        runner = self._make_runner(parallel=4)
        original_log = BaseDatabaseCreation.log

        def exploding_teardown(self_runner, old_config, **kwargs):
            raise RuntimeError("boom")

        with patch.object(
            DiscoverRunner, "teardown_databases", exploding_teardown
        ):
            with self.assertRaises(RuntimeError):
                runner.teardown_databases(old_config=[])

        assert BaseDatabaseCreation.log is original_log
