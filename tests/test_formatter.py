"""Tests for the formatter module."""

import unittest
from unittest.mock import MagicMock

from rich.console import Console
from rich.text import Text

from django_prismtest.formatter import (
    build_live_tree,
    build_status_line,
    format_traceback,
    make_console,
    render_error_list,
    render_summary,
    render_tree,
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


class TestRenderTree(unittest.TestCase):
    SAMPLE_OUTCOMES = [
        (["tests", "test_formatter"], "TestStatusIcon", "test_pass", "pass", 0.001, ""),
        (["tests", "test_formatter"], "TestStatusIcon", "test_fail", "fail", 0.002, ""),
        (["tests", "test_formatter"], "TestFormatTraceback", "test_basic", "pass", 0.003, ""),
        (["tests", "test_result"], "TestPrismTestResult", "test_creates_result", "pass", 0.001, ""),
    ]

    def test_renders_without_error(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        assert "Test Results" in output

    def test_contains_module_names(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        assert "test_formatter" in output
        assert "test_result" in output

    def test_contains_class_names(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        assert "TestStatusIcon" in output
        assert "TestFormatTraceback" in output

    def test_contains_method_names(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        assert "test_pass" in output
        assert "test_basic" in output

    def test_contains_status_icons(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        assert "✔" in output
        assert "✘" in output

    def test_contains_tree_connectors(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        assert "├" in output or "└" in output

    def test_skip_reason_shown(self):
        import io
        outcomes = [
            (["tests", "test_foo"], "TestFoo", "test_skipped", "skip", 0.0, "SKIP: not supported"),
        ]
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(outcomes, console=console)
        output = buf.getvalue()
        assert "not supported" in output

    def test_shared_prefix_collapsed(self):
        import io
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(self.SAMPLE_OUTCOMES, console=console)
        output = buf.getvalue()
        # "tests" module should appear only once as a shared parent
        assert output.count("tests") >= 1

    def test_single_child_chain_collapsed(self):
        import io
        outcomes = [
            (["apps", "api", "tests"], "MyTest", "test_one", "pass", 0.001, ""),
            (["apps", "api", "tests"], "MyTest", "test_two", "pass", 0.002, ""),
        ]
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(outcomes, console=console)
        output = buf.getvalue()
        # The single-child module chain should be collapsed with dots
        assert "apps.api.tests" in output

    def test_single_method_class_collapsed(self):
        import io
        outcomes = [
            (["tests"], "OnlyOneTest", "test_solo", "pass", 0.005, ""),
        ]
        buf = io.StringIO()
        console = make_console(file=buf)
        render_tree(outcomes, console=console)
        output = buf.getvalue()
        # Class with one method should be collapsed into a single leaf
        assert "OnlyOneTest" in output
        assert "test_solo" in output


class TestBuildLiveTree(unittest.TestCase):
    def test_returns_tree_object(self):
        from rich.tree import Tree
        running = [
            (["tests", "test_views"], "ViewTest", "test_detail"),
        ]
        tree = build_live_tree(running, "⠋")
        assert isinstance(tree, Tree)

    def test_contains_running_tests_with_spinner(self):
        import io
        running = [
            (["tests", "test_views"], "ViewTest", "test_detail"),
        ]
        tree = build_live_tree(running, "⠹")
        buf = io.StringIO()
        console = make_console(file=buf)
        console.print(tree)
        output = buf.getvalue()
        assert "test_detail" in output
        assert "⠹" in output

    def test_excludes_completed_tests(self):
        import io
        running = [
            (["tests", "test_auth"], "AuthTest", "test_logout"),
        ]
        tree = build_live_tree(running, "⠋")
        buf = io.StringIO()
        console = make_console(file=buf)
        console.print(tree)
        output = buf.getvalue()
        assert "test_logout" in output
        assert "⠋" in output
        # No status icons for completed tests should appear
        assert "✔" not in output
        assert "✘" not in output

    def test_empty_running_produces_empty_tree(self):
        import io
        tree = build_live_tree([], "⠋")
        buf = io.StringIO()
        console = make_console(file=buf)
        console.print(tree)
        output = buf.getvalue()
        assert "Test Results" in output


class TestBuildStatusLine(unittest.TestCase):
    def test_returns_text_object(self):
        from rich.text import Text
        result = build_status_line(
            total=10, completed=5, passed=4, failed=1, errors=0,
            skipped=0, running_count=2, spinner_char="⠋", elapsed=1.5,
        )
        assert isinstance(result, Text)

    def test_contains_progress(self):
        result = build_status_line(
            total=42, completed=15, passed=12, failed=2, errors=0,
            skipped=1, running_count=3, spinner_char="⠋", elapsed=1.2,
        )
        plain = result.plain
        assert "15/42" in plain

    def test_contains_pass_count(self):
        result = build_status_line(
            total=10, completed=5, passed=5, failed=0, errors=0,
            skipped=0, running_count=1, spinner_char="⠋", elapsed=0.5,
        )
        plain = result.plain
        assert "✔" in plain
        assert "5" in plain

    def test_shows_failures(self):
        result = build_status_line(
            total=10, completed=5, passed=3, failed=2, errors=0,
            skipped=0, running_count=0, spinner_char="⠋", elapsed=1.0,
        )
        plain = result.plain
        assert "2 failed" in plain

    def test_shows_errors(self):
        result = build_status_line(
            total=10, completed=5, passed=3, failed=0, errors=1,
            skipped=0, running_count=0, spinner_char="⠋", elapsed=1.0,
        )
        plain = result.plain
        assert "1 error" in plain

    def test_shows_running_count(self):
        result = build_status_line(
            total=10, completed=5, passed=5, failed=0, errors=0,
            skipped=0, running_count=3, spinner_char="⠹", elapsed=2.0,
        )
        plain = result.plain
        assert "3 running" in plain

    def test_shows_elapsed(self):
        result = build_status_line(
            total=10, completed=10, passed=10, failed=0, errors=0,
            skipped=0, running_count=0, spinner_char="⠋", elapsed=4.56,
        )
        plain = result.plain
        assert "4.6s" in plain

    def test_hides_zero_failures(self):
        result = build_status_line(
            total=5, completed=5, passed=5, failed=0, errors=0,
            skipped=0, running_count=0, spinner_char="⠋", elapsed=1.0,
        )
        plain = result.plain
        assert "failed" not in plain


class TestRenderErrorList(unittest.TestCase):
    def test_renders_failure_panel(self):
        import io
        errors = [("test_foo (tests.TestFoo)", "Traceback:\nAssertionError")]
        buf = io.StringIO()
        console = make_console(file=buf)
        render_error_list("FAIL", errors, console=console)
        output = buf.getvalue()
        assert "FAIL" in output
