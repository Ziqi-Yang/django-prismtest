"""Custom test result class with live spinner and colored output."""

from __future__ import annotations

import sys
import threading
import time
import unittest

from django_prismtest.formatter import (
    SPINNER_FRAMES,
    SPINNER_INTERVAL,
    format_traceback,
    make_console,
    render_error_list,
    render_summary,
    status_icon,
)


class _Spinner:
    """A lightweight terminal spinner that runs in a background thread.

    Writes directly to stderr so it doesn't interfere with the test
    runner's stdout stream.
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._text = ""
        self._lock = threading.Lock()

    def start(self, text: str) -> None:
        self._text = text
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
            with self._lock:
                text = self._text
            line = f"\r\033[36m{frame}\033[0m {text}"
            sys.stderr.write(line)
            sys.stderr.flush()
            idx += 1
            self._stop_event.wait(SPINNER_INTERVAL)

    def stop(self, final_text: str = "") -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        # Clear the spinner line
        sys.stderr.write("\r\033[K")
        if final_text:
            sys.stderr.write(final_text + "\n")
        sys.stderr.flush()

    def update(self, text: str) -> None:
        with self._lock:
            self._text = text


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
        self._spinner = _Spinner()
        self._test_start_time: float = 0.0
        self.test_timings: list[tuple[str, float]] = []
        self._run_start_time: float = 0.0
        self.highlight_path: str | None = None
        self._configure_highlight_path()

    def _configure_highlight_path(self) -> None:
        """Read highlight path from Django settings, if available."""
        try:
            from django.conf import settings
            self.highlight_path = getattr(
                settings, "PRISMTEST_HIGHLIGHT_PATH", None
            )
        except Exception:
            pass

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
        super().startTest(test)
        self._test_start_time = time.time()
        test_name = self.getDescription(test)
        if self.showAll:
            self._spinner.start(f"[dim]{test_name}[/dim]")
        elif self.dots:
            self._spinner.start(f"[dim]{test_name}[/dim]")

    def stopTest(self, test: unittest.TestCase) -> None:
        elapsed = time.time() - self._test_start_time
        test_name = self.getDescription(test)
        self.test_timings.append((test_name, elapsed))
        super().stopTest(test)

    def stopTestRun(self) -> None:
        super().stopTestRun()
        total_elapsed = time.time() - self._run_start_time
        self.console.print("[separator]" + "─" * 60 + "[/separator]")

        # Print failures and errors
        if self.failures:
            self.console.print()
            render_error_list(
                "FAIL", self.failures,
                highlight_path=self.highlight_path,
                console=self.console,
            )
        if self.errors:
            self.console.print()
            render_error_list(
                "ERROR", self.errors,
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

        if self.showAll:
            self._spinner.stop(
                f"\033[32m  ✔ \033[0m{test_name}\033[2m ({elapsed:.3f}s)\033[0m"
            )
        elif self.dots:
            self._spinner.stop()
            sys.stderr.write("\033[32m.\033[0m")
            sys.stderr.flush()

    def addError(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addError(self, test, err)
        test_name = self.getDescription(test)

        if self.showAll:
            self._spinner.stop(
                f"\033[31m  ✘ \033[0m{test_name}\033[31m  ERROR\033[0m"
            )
        elif self.dots:
            self._spinner.stop()
            sys.stderr.write("\033[31mE\033[0m")
            sys.stderr.flush()

    def addFailure(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addFailure(self, test, err)
        test_name = self.getDescription(test)

        if self.showAll:
            self._spinner.stop(
                f"\033[31m  ✘ \033[0m{test_name}\033[31m  FAIL\033[0m"
            )
        elif self.dots:
            self._spinner.stop()
            sys.stderr.write("\033[31mF\033[0m")
            sys.stderr.flush()

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        unittest.TestResult.addSkip(self, test, reason)
        test_name = self.getDescription(test)

        if self.showAll:
            self._spinner.stop(
                f"\033[33m  ⊘ \033[0m{test_name}\033[33m  SKIP: {reason}\033[0m"
            )
        elif self.dots:
            self._spinner.stop()
            sys.stderr.write("\033[33ms\033[0m")
            sys.stderr.flush()

    def addExpectedFailure(self, test: unittest.TestCase, err) -> None:
        unittest.TestResult.addExpectedFailure(self, test, err)
        test_name = self.getDescription(test)

        if self.showAll:
            self._spinner.stop(
                f"\033[2;32m  ✔ \033[0m{test_name}\033[2m  expected failure\033[0m"
            )
        elif self.dots:
            self._spinner.stop()
            sys.stderr.write("\033[2;32mx\033[0m")
            sys.stderr.flush()

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        unittest.TestResult.addUnexpectedSuccess(self, test)
        test_name = self.getDescription(test)

        if self.showAll:
            self._spinner.stop(
                f"\033[35m  ⚠ \033[0m{test_name}\033[35m  unexpected success\033[0m"
            )
        elif self.dots:
            self._spinner.stop()
            sys.stderr.write("\033[35mu\033[0m")
            sys.stderr.flush()

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
