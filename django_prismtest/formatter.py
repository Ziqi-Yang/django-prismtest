"""Output formatting utilities for prismtest.

Handles colored text rendering, traceback syntax highlighting,
and the final test summary panel using Rich.
"""

from __future__ import annotations

import re
import textwrap
import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

if TYPE_CHECKING:
    from unittest import TestResult

PRISM_THEME = Theme(
    {
        "pass": "bold green",
        "fail": "bold red",
        "error": "bold red",
        "skip": "bold yellow",
        "expected_fail": "dim green",
        "unexpected_success": "bold magenta",
        "title": "bold cyan",
        "timing": "dim white",
        "separator": "dim white",
        "path": "underline cyan",
        "test_name": "bold white",
    }
)


def make_console(file=None, **kwargs) -> Console:
    """Create a Rich Console configured with the prism theme."""
    return Console(
        theme=PRISM_THEME,
        file=file,
        force_terminal=True,
        no_color=False,
        highlight=False,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Spinner frames – a compact Braille-dot spinner for real-time feedback
# ---------------------------------------------------------------------------
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.08  # seconds between frames


def status_icon(outcome: str) -> str:
    """Return a colored icon for a test outcome."""
    icons = {
        "pass": "[pass]✔[/pass]",
        "fail": "[fail]✘[/fail]",
        "error": "[error]✘[/error]",
        "skip": "[skip]⊘[/skip]",
        "expected_failure": "[expected_fail]✔[/expected_fail]",
        "unexpected_success": "[unexpected_success]⚠[/unexpected_success]",
    }
    return icons.get(outcome, " ")


# ---------------------------------------------------------------------------
# Traceback formatting
# ---------------------------------------------------------------------------

_FILE_LINE_RE = re.compile(r'^\s*File "(.+?)", line (\d+)')


def format_traceback(err_text: str, highlight_path: str | None = None) -> Text:
    """Turn a traceback string into a Rich Text object with syntax colors.

    Lines matching *highlight_path* (typically the project root) are
    emphasized so developers can quickly spot their own code.
    """
    text = Text()
    lines = err_text.rstrip().split("\n")

    for i, line in enumerate(lines):
        match = _FILE_LINE_RE.match(line)
        if match:
            filepath = match.group(1)
            is_project = highlight_path and highlight_path in filepath
            style = "bold yellow" if is_project else "dim cyan"
            text.append(line + "\n", style=style)
            # Color the next line (source code) with the same emphasis
            if i + 1 < len(lines) and not _FILE_LINE_RE.match(lines[i + 1]):
                continue  # will be handled in the next iteration with context
        elif i > 0 and _FILE_LINE_RE.match(lines[i - 1]):
            prev_match = _FILE_LINE_RE.match(lines[i - 1])
            filepath = prev_match.group(1) if prev_match else ""
            is_project = highlight_path and highlight_path in filepath
            style = "bold yellow" if is_project else "dim cyan"
            text.append(line + "\n", style=style)
        elif line.startswith("Traceback"):
            text.append(line + "\n", style="bold red")
        elif i == len(lines) - 1:
            # Last line is usually the exception message
            text.append(line + "\n", style="bold magenta")
        else:
            text.append(line + "\n", style="")

    return text


# ---------------------------------------------------------------------------
# Summary panel
# ---------------------------------------------------------------------------


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def render_summary(
    result: TestResult,
    elapsed: float,
    test_timings: list[tuple[str, float]],
    console: Console | None = None,
) -> None:
    """Print a beautiful summary panel after the test run."""
    if console is None:
        console = make_console()

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    expected_failures = len(result.expectedFailures)
    unexpected_successes = len(result.unexpectedSuccesses)
    passed = (
        total - failures - errors - skipped - expected_failures - unexpected_successes
    )
    success = result.wasSuccessful()

    # ---- Header ----
    console.print()
    if success:
        header_style = "bold green"
        header_text = "ALL TESTS PASSED"
    else:
        header_style = "bold red"
        header_text = "TESTS FAILED"

    # ---- Stats table ----
    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column("label", style="bold")
    stats.add_column("value", justify="right")

    stats.add_row("[pass]Passed[/pass]", f"[pass]{passed}[/pass]")
    if failures:
        stats.add_row("[fail]Failed[/fail]", f"[fail]{failures}[/fail]")
    if errors:
        stats.add_row("[error]Errors[/error]", f"[error]{errors}[/error]")
    if skipped:
        stats.add_row("[skip]Skipped[/skip]", f"[skip]{skipped}[/skip]")
    if expected_failures:
        stats.add_row(
            "[expected_fail]Expected failures[/expected_fail]",
            f"[expected_fail]{expected_failures}[/expected_fail]",
        )
    if unexpected_successes:
        stats.add_row(
            "[unexpected_success]Unexpected successes[/unexpected_success]",
            f"[unexpected_success]{unexpected_successes}[/unexpected_success]",
        )
    stats.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total}[/bold]",
    )
    stats.add_row(
        "[timing]Duration[/timing]",
        f"[timing]{elapsed:.2f}s[/timing]",
    )

    panel = Panel(
        stats,
        title=f"[{header_style}]{header_text}[/{header_style}]",
        border_style="green" if success else "red",
        padding=(1, 2),
    )
    console.print(panel)

    # ---- Slowest tests ----
    if test_timings:
        slowest = sorted(test_timings, key=lambda t: t[1], reverse=True)[:5]
        if slowest and slowest[0][1] > 0.001:
            console.print()
            console.print("[title]Slowest tests:[/title]")
            timing_table = Table(show_header=True, box=None, padding=(0, 1))
            timing_table.add_column("Test", style="test_name")
            timing_table.add_column("Time", justify="right", style="timing")
            for name, dur in slowest:
                timing_table.add_row(name, f"{dur:.3f}s")
            console.print(timing_table)


# ---------------------------------------------------------------------------
# Error / failure detail blocks
# ---------------------------------------------------------------------------


def render_error_list(
    flavour: str,
    errors: list[tuple],
    highlight_path: str | None = None,
    console: Console | None = None,
) -> None:
    """Render failures/errors as Rich panels with syntax-highlighted tracebacks."""
    if console is None:
        console = make_console()

    style = "red" if flavour in ("FAIL", "ERROR") else "yellow"

    for test, err, *_extra in errors:
        test_id = str(test)
        tb = format_traceback(str(err), highlight_path=highlight_path)

        panel = Panel(
            tb,
            title=f"[bold {style}]{flavour}[/bold {style}]: {escape(test_id)}",
            border_style=style,
            padding=(0, 1),
        )
        console.print(panel)

        # If there's extra info (e.g. SQL debug), print it too
        for extra in _extra:
            if extra:
                console.print(
                    Panel(str(extra), title="SQL Queries", border_style="blue")
                )
