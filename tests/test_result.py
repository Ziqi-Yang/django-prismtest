"""Tests for the PrismTestResult class."""

import io
import sys
import unittest

from django_prismtest.result import PrismTestResult, _Spinner


class TestSpinner(unittest.TestCase):
    def test_start_and_stop(self):
        spinner = _Spinner()
        spinner.start("testing...")
        # Let it spin briefly
        import time
        time.sleep(0.15)
        spinner.stop()
        # Should not raise

    def test_stop_with_message(self):
        spinner = _Spinner()
        spinner.start("working...")
        import time
        time.sleep(0.1)
        spinner.stop("done")

    def test_update_text(self):
        spinner = _Spinner()
        spinner.start("initial")
        spinner.update("updated text")
        import time
        time.sleep(0.1)
        spinner.stop()


class TestPrismTestResult(unittest.TestCase):
    def _make_result(self, verbosity=2):
        stream = io.StringIO()
        # Wrap stream to have writeln (like unittest._WritelnDecorator)
        class StreamWrapper:
            def __init__(self, s):
                self._stream = s
            def write(self, text):
                self._stream.write(text)
            def writeln(self, text=""):
                self._stream.write(text + "\n")
            def flush(self):
                self._stream.flush()

        result = PrismTestResult(StreamWrapper(stream), descriptions=True, verbosity=verbosity)
        return result

    def test_creation(self):
        result = self._make_result()
        assert result.testsRun == 0
        assert result.test_timings == []

    def test_get_description_with_docstring(self):
        class FakeTest:
            def shortDescription(self):
                return "A short doc"
            def __str__(self):
                return "test_example"

        result = self._make_result()
        desc = result.getDescription(FakeTest())
        assert "test_example" in desc
        assert "A short doc" in desc

    def test_get_description_without_docstring(self):
        class FakeTest:
            def shortDescription(self):
                return None
            def __str__(self):
                return "test_example"

        result = self._make_result()
        desc = result.getDescription(FakeTest())
        assert desc == "test_example"

    def test_print_errors_is_noop(self):
        result = self._make_result()
        # Should not raise
        result.printErrors()
