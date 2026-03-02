"""Tests for the formatter module."""

import unittest
from unittest.mock import MagicMock

from rich.console import Console
from rich.text import Text

from django_prismtest.formatter import (
    format_traceback,
    make_console,
    render_error_list,
    render_summary,
    status_icon,
)


class TestStatusIcon(unittest.TestCase):
    def test_pass_icon(self):
        icon = status_icon("pass")
        assert "✔" in icon

    def test_fail_icon(self):
        icon = status_icon("fail")
        assert "✘" in icon

    def test_error_icon(self):
        icon = status_icon("error")
        assert "✘" in icon

    def test_skip_icon(self):
        icon = status_icon("skip")
        assert "⊘" in icon

    def test_unknown_returns_space(self):
        icon = status_icon("unknown_outcome")
        assert icon == " "


class TestMakeConsole(unittest.TestCase):
    def test_returns_console(self):
        console = make_console()
        assert isinstance(console, Console)

    def test_force_terminal(self):
        console = make_console()
        assert console.is_terminal


class TestFormatTraceback(unittest.TestCase):
    SAMPLE_TB = (
        'Traceback (most recent call last):\n'
        '  File "/app/myproject/views.py", line 42, in my_view\n'
        '    result = do_something()\n'
        '  File "/usr/lib/python3.13/unittest/mock.py", line 1, in call\n'
        '    return self._mock_call(*args)\n'
        'AssertionError: 1 != 2'
    )

    def test_returns_text_object(self):
        result = format_traceback(self.SAMPLE_TB)
        assert isinstance(result, Text)

    def test_highlight_path_emphasizes_project_lines(self):
        result = format_traceback(self.SAMPLE_TB, highlight_path="/app/myproject/")
        plain = result.plain
        assert "/app/myproject/views.py" in plain

    def test_no_highlight_path_still_works(self):
        result = format_traceback(self.SAMPLE_TB)
        assert "Traceback" in result.plain


class TestRenderSummary(unittest.TestCase):
    def _make_result(self, *, run=5, failures=0, errors=0, skipped=0,
                     expected=0, unexpected=0):
        r = MagicMock()
        r.testsRun = run
        r.failures = [None] * failures
        r.errors = [None] * errors
        r.skipped = [None] * skipped
        r.expectedFailures = [None] * expected
        r.unexpectedSuccesses = [None] * unexpected
        r.wasSuccessful.return_value = (failures == 0 and errors == 0)
        return r

    def test_all_passed(self):
        result = self._make_result(run=3)
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_summary(result, 1.23, [], console=console)
        output = buf.getvalue()
        assert "PASSED" in output

    def test_failures_shown(self):
        result = self._make_result(run=3, failures=1)
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_summary(result, 1.0, [], console=console)
        output = buf.getvalue()
        assert "FAILED" in output


class TestRenderErrorList(unittest.TestCase):
    def test_renders_failure_panel(self):
        import io
        errors = [("test_foo (tests.TestFoo)", "Traceback:\nAssertionError")]
        buf = io.StringIO()
        console = make_console(file=buf)
        render_error_list("FAIL", errors, console=console)
        output = buf.getvalue()
        assert "FAIL" in output
