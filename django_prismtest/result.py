"""Custom test result class with live tree display and colored output."""

from __future__ import annotations

import re
import sys
import threading
import time
import unittest

from rich.console import Group
from rich.live import Live
from rich.text import Text

from django_prismtest.formatter import (
    SPINNER_FRAMES,
    build_live_tree,
    build_status_line,
    make_console,
    render_error_list,
    render_summary,
    render_tree,
)


class _LiveTreeRenderable:
    """A Rich renderable that rebuilds the live tree on each refresh.

    Rich's ``Live`` calls ``__rich_console__`` (via ``__rich__``) on every
    refresh cycle.  Each call advances the spinner frame and snapshots the
    current test state to produce an up-to-date tree with status line.
    """

    def __init__(self, result: PrismTestResult) -> None:
        self._result = result
        self._frame: int = 0

    def __rich__(self) -> Group:
        r = self._result
        spinner_char = SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]
        self._frame += 1

        with r._live_lock:
            outcomes = list(r._test_outcomes)
            running = list(r._running_tests.values())
            total = r._total_tests
            elapsed = time.time() - r._run_start_time

        completed = len(outcomes)
        passed = sum(1 for *_, o, _, _ in outcomes if o == "pass")
        failed = sum(1 for *_, o, _, _ in outcomes if o == "fail")
        errors = sum(1 for *_, o, _, _ in outcomes if o == "error")
        skipped = sum(1 for *_, o, _, _ in outcomes if o == "skip")

        status = build_status_line(
            total=total,
            completed=completed,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            running_count=len(running),
            spinner_char=spinner_char,
            elapsed=elapsed,
        )
        tree = build_live_tree(running, spinner_char)
        return Group(status, tree)


class PrismTestResult(unittest.TextTestResult):
    """A test result class that provides rich, colorful output with a live tree.

    Features:
    - Real-time live tree display showing all tests as they run
    - Braille-dot spinner for in-progress tests
    - Colored pass/fail/error/skip indicators
    - Per-test timing
    - Rich-formatted summary with panels and tables
    - Syntax-highlighted tracebacks
    """

    def __init__(self, stream, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.console = make_console(file=sys.stderr)
        self._live: Live | None = None
        self._live_lock = threading.Lock()
        self._running_tests: dict[str, tuple[list[str], str, str]] = {}
        self._total_tests: int = 0
        self._test_start_time: float = 0.0
        self.test_timings: list[tuple[str, float]] = []
        self._test_outcomes: list[tuple[list[str], str, str, str, float, str]] = []
        self._run_start_time: float = 0.0
        self._parallel: bool = False
        self.highlight_path: str | None = None
        self._configure_highlight_path()

    def _configure_highlight_path(self) -> None:
        """Read highlight path from Django settings, if available."""
        try:
            from django.conf import settings

            self.highlight_path = getattr(settings, "PRISMTEST_HIGHLIGHT_PATH", None)
        except Exception:
            pass

    def _format_test_name(self, test: unittest.TestCase, dim_all: bool = False) -> str:
        """Return Rich-markup formatted test name with differentiated parts."""
        from rich.markup import escape

        test_str = str(test)
        match = re.match(r"^(\S+)\s+\((.+)\)$", test_str)

        if match:
            method = escape(match.group(1))
            path = escape(match.group(2))
            if dim_all:
                parts = f"[dim]{method} ({path})[/dim]"
            else:
                parts = f"[test_name]{method}[/test_name] [dim]({path})[/dim]"
        else:
            if dim_all:
                parts = f"[dim]{escape(test_str)}[/dim]"
            else:
                parts = f"[test_name]{escape(test_str)}[/test_name]"

        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            desc = escape(doc_first_line)
            if dim_all:
                parts += f" [dim]-- {desc}[/dim]"
            else:
                parts += f" [dim italic]-- {desc}[/dim italic]"

        return parts

    @staticmethod
    def _parse_test_id(test: unittest.TestCase) -> tuple[list[str], str, str]:
        """Split ``str(test)`` into ``(module_parts, class_name, method_name)``."""
        test_str = str(test)
        match = re.match(r"^(\S+)\s+\((.+)\)$", test_str)
        if match:
            method = match.group(1)
            path = match.group(2)
            # Strip a trailing method name if the path redundantly includes it
            # e.g. "test_foo (mod.Class.test_foo)" → path should be "mod.Class"
            if path.endswith(f".{method}"):
                path = path[: -(len(method) + 1)]
            parts = path.rsplit(".", 1)
            if len(parts) == 2:
                module_path, class_name = parts
                return module_path.split("."), class_name, method
            return [path], "", method
        return [test_str], "", ""

    def _stop_live(self) -> None:
        """Stop the live tree display if it's running."""
        with self._live_lock:
            live = self._live
            self._live = None
        # Call stop() outside the lock — stop() joins the refresh thread,
        # which needs _live_lock in __rich__().  Holding the lock here
        # would deadlock.
        if live is not None:
            live.stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startTestRun(self) -> None:
        super().startTestRun()
        self._run_start_time = time.time()
        self.console.print()
        self.console.print("[title]Running tests...[/title]")
        self.console.print("[separator]" + "─" * 60 + "[/separator]")

        if self.showAll:
            renderable = _LiveTreeRenderable(self)
            self._live = Live(
                renderable,
                console=self.console,
                transient=True,
                refresh_per_second=12.5,
            )
            self._live.start()

    def startTest(self, test: unittest.TestCase) -> None:
        # Bypass TextTestResult.startTest() to suppress its default output
        unittest.TestResult.startTest(self, test)
        self._test_start_time = time.time()
        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests[str(test)] = (mod, cls, method)

    def stopTest(self, test: unittest.TestCase) -> None:
        elapsed = time.time() - self._test_start_time
        test_name = self.getDescription(test)
        self.test_timings.append((test_name, elapsed))
        super().stopTest(test)

    def stopTestRun(self) -> None:
        super().stopTestRun()
        total_elapsed = time.time() - self._run_start_time
        # Stop the live display (transient=True auto-clears it)
        self._stop_live()

        if self.showAll and self._test_outcomes:
            render_tree(self._test_outcomes, self.console)
        if self.dots:
            self.console.print()
        self.console.print("[separator]" + "─" * 60 + "[/separator]")

        # Print failures and errors
        if self.failures:
            self.console.print()
            render_error_list(
                "FAIL",
                self.failures,
                highlight_path=self.highlight_path,
                console=self.console,
            )
        if self.errors:
            self.console.print()
            render_error_list(
                "ERROR",
                self.errors,
                highlight_path=self.highlight_path,
                console=self.console,
            )

        timings = [] if self._parallel else self.test_timings
        render_summary(self, total_elapsed, timings, self.console)

    # ------------------------------------------------------------------
    # Result handlers
    # ------------------------------------------------------------------

    def addSuccess(self, test: unittest.TestCase) -> None:
        unittest.TestResult.addSuccess(self, test)
        elapsed = time.time() - self._test_start_time

        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests.pop(str(test), None)
                self._test_outcomes.append((mod, cls, method, "pass", elapsed, ""))
        elif self.dots:
            self.console.print("[pass].[/pass]", end="")

    def addError(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addError(self, test, err)

        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests.pop(str(test), None)
                self._test_outcomes.append((mod, cls, method, "error", 0.0, ""))
        elif self.dots:
            self.console.print("[error]E[/error]", end="")

    def addFailure(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addFailure(self, test, err)

        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests.pop(str(test), None)
                self._test_outcomes.append((mod, cls, method, "fail", 0.0, ""))
        elif self.dots:
            self.console.print("[fail]F[/fail]", end="")

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        unittest.TestResult.addSkip(self, test, reason)

        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests.pop(str(test), None)
                self._test_outcomes.append((mod, cls, method, "skip", 0.0, f"SKIP: {reason}"))
        elif self.dots:
            self.console.print("[dim]s[/dim]", end="")

    def addExpectedFailure(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addExpectedFailure(self, test, err)

        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests.pop(str(test), None)
                self._test_outcomes.append((mod, cls, method, "expected_failure", 0.0, "expected failure"))
        elif self.dots:
            self.console.print("[expected_fail]x[/expected_fail]", end="")

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        unittest.TestResult.addUnexpectedSuccess(self, test)

        if self.showAll:
            mod, cls, method = self._parse_test_id(test)
            with self._live_lock:
                self._running_tests.pop(str(test), None)
                self._test_outcomes.append((mod, cls, method, "unexpected_success", 0.0, "unexpected success"))
        elif self.dots:
            self.console.print("[unexpected_success]u[/unexpected_success]", end="")

    # ------------------------------------------------------------------
    # Override printErrors to suppress default output (we do it in stopTestRun)
    # ------------------------------------------------------------------

    def printErrors(self) -> None:
        pass

    def getDescription(self, test: unittest.TestCase) -> str:
        """Return a concise test description."""
        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            return f"{test} -- {doc_first_line}"
        return str(test)
