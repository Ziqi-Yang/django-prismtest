"""Custom test result class with live spinner and colored output."""

from __future__ import annotations

import sys
import threading
import time
import unittest

from rich.live import Live
from rich.markup import escape
from rich.spinner import Spinner
from rich.text import Text

from django_prismtest.formatter import (
    make_console,
    render_error_list,
    render_summary,
)

# Only show the spinner if a test runs longer than this (seconds).
# Avoids visual noise for fast tests and parallel-mode event replays.
_SPINNER_DELAY = 0.15


class PrismTestResult(unittest.TextTestResult):
    """A test result class that provides rich, colorful output with spinners.

    Features:
    - Real-time Braille-dot spinner while each test runs
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
        self._spinner_timer: threading.Timer | None = None
        self._test_start_time: float = 0.0
        self.test_timings: list[tuple[str, float]] = []
        self._run_start_time: float = 0.0
        self.highlight_path: str | None = None
        self._configure_highlight_path()

    def _configure_highlight_path(self) -> None:
        """Read highlight path from Django settings, if available."""
        try:
            from django.conf import settings

            self.highlight_path = getattr(settings, "PRISMTEST_HIGHLIGHT_PATH", None)
        except Exception:
            pass

    def _start_spinner(self, test_name: str) -> None:
        """Start the live spinner display (called from timer thread)."""
        with self._live_lock:
            if self._spinner_timer is None:
                # Timer was cancelled before we got here
                return
            spinner = Spinner("dots", text=Text(test_name, style="dim"))
            self._live = Live(
                spinner,
                console=self.console,
                transient=True,
                refresh_per_second=12.5,
            )
            self._live.start()

    def _stop_live(self) -> None:
        """Stop the live spinner display if it's running."""
        with self._live_lock:
            if self._spinner_timer is not None:
                self._spinner_timer.cancel()
                self._spinner_timer = None
            if self._live is not None:
                self._live.stop()
                self._live = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startTestRun(self) -> None:
        super().startTestRun()
        self._run_start_time = time.time()
        self.console.print()
        self.console.print("[title]Running tests...[/title]")
        self.console.print("[separator]" + "─" * 60 + "[/separator]")

    def startTest(self, test: unittest.TestCase) -> None:
        # Bypass TextTestResult.startTest() to suppress its default output
        # (it writes the test name + " ... " to the stream).
        unittest.TestResult.startTest(self, test)
        self._test_start_time = time.time()
        # Clean up any leftover spinner from a previous test
        self._stop_live()
        test_name = self.getDescription(test)
        if self.showAll or self.dots:
            timer = threading.Timer(
                _SPINNER_DELAY, self._start_spinner, args=(test_name,)
            )
            timer.daemon = True
            self._spinner_timer = timer
            timer.start()

    def stopTest(self, test: unittest.TestCase) -> None:
        elapsed = time.time() - self._test_start_time
        test_name = self.getDescription(test)
        self.test_timings.append((test_name, elapsed))
        self._stop_live()
        super().stopTest(test)

    def stopTestRun(self) -> None:
        super().stopTestRun()
        total_elapsed = time.time() - self._run_start_time
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

        render_summary(self, total_elapsed, self.test_timings, self.console)

    # ------------------------------------------------------------------
    # Result handlers
    # ------------------------------------------------------------------

    def addSuccess(self, test: unittest.TestCase) -> None:
        # Skip the TextTestResult output; we handle it ourselves
        unittest.TestResult.addSuccess(self, test)
        elapsed = time.time() - self._test_start_time
        test_name = self.getDescription(test)
        self._stop_live()

        if self.showAll:
            self.console.print(
                f"  [pass]✔[/pass] {escape(test_name)} [timing]({elapsed:.3f}s)[/timing]"
            )
        elif self.dots:
            self.console.print("[pass].[/pass]", end="")

    def addError(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addError(self, test, err)
        test_name = self.getDescription(test)
        self._stop_live()

        if self.showAll:
            self.console.print(
                f"  [error]✘[/error] {escape(test_name)}  [error]ERROR[/error]"
            )
        elif self.dots:
            self.console.print("[error]E[/error]", end="")

    def addFailure(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addFailure(self, test, err)
        test_name = self.getDescription(test)
        self._stop_live()

        if self.showAll:
            self.console.print(
                f"  [fail]✘[/fail] {escape(test_name)}  [fail]FAIL[/fail]"
            )
        elif self.dots:
            self.console.print("[fail]F[/fail]", end="")

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        unittest.TestResult.addSkip(self, test, reason)
        test_name = self.getDescription(test)
        self._stop_live()

        if self.showAll:
            self.console.print(
                f"  [skip]⊘[/skip] {escape(test_name)}  [skip]SKIP: {escape(reason)}[/skip]"
            )
        elif self.dots:
            self.console.print("[skip]s[/skip]", end="")

    def addExpectedFailure(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addExpectedFailure(self, test, err)
        test_name = self.getDescription(test)
        self._stop_live()

        if self.showAll:
            self.console.print(
                f"  [expected_fail]✔[/expected_fail] {escape(test_name)}"
                " [timing]expected failure[/timing]"
            )
        elif self.dots:
            self.console.print("[expected_fail]x[/expected_fail]", end="")

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        unittest.TestResult.addUnexpectedSuccess(self, test)
        test_name = self.getDescription(test)
        self._stop_live()

        if self.showAll:
            self.console.print(
                f"  [unexpected_success]⚠[/unexpected_success] {escape(test_name)}"
                " [unexpected_success]unexpected success[/unexpected_success]"
            )
        elif self.dots:
            self.console.print("[unexpected_success]u[/unexpected_success]", end="")

    # ------------------------------------------------------------------
    # Override printErrors to suppress default output (we do it in stopTestRun)
    # ------------------------------------------------------------------

    def printErrors(self) -> None:
        # Handled in stopTestRun via render_error_list / render_summary
        pass

    def getDescription(self, test: unittest.TestCase) -> str:
        """Return a concise test description."""
        doc_first_line = test.shortDescription()
        if self.descriptions and doc_first_line:
            return f"{test} -- {doc_first_line}"
        return str(test)
