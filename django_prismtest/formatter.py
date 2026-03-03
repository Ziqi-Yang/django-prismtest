"""Output formatting utilities for prismtest.

Handles colored text rendering, traceback syntax highlighting,
and the final test summary panel using Rich.
"""

from __future__ import annotations

import re
import textwrap
import time
from typing import TYPE_CHECKING

from collections import OrderedDict

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.tree import Tree

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
# Tree-structured output
# ---------------------------------------------------------------------------


def _method_label(
    method_name: str,
    outcome: str,
    elapsed: float,
    reason: str,
    spinner_char: str | None = None,
) -> str:
    """Build a Rich-markup leaf label for a single test method."""
    if outcome == "_running" and spinner_char:
        return f"[bold cyan]{spinner_char}[/bold cyan] {method_name}"
    icon = status_icon(outcome)
    label = f"{icon} {method_name} [timing]({elapsed:.3f}s)[/timing]"
    if reason:
        label += f"  [dim]{escape(reason)}[/dim]"
    return label


_TrieNode = dict  # {"children": OrderedDict[str, _TrieNode], "methods": list}


def _new_trie_node() -> _TrieNode:
    return {"children": OrderedDict(), "methods": []}


def _collapse_trie(node: _TrieNode) -> None:
    """Merge single-child chains so ``a → b → c`` becomes ``a.b.c``."""
    for child in node["children"].values():
        _collapse_trie(child)

    collapsed: OrderedDict[str, _TrieNode] = OrderedDict()
    for name, child in node["children"].items():
        cname = name
        while len(child["children"]) == 1 and not child["methods"]:
            sub_name, grandchild = next(iter(child["children"].items()))
            cname = f"{cname}.{sub_name}"
            child = grandchild
        collapsed[cname] = child
    node["children"] = collapsed


def _format_node_label(name: str, is_leaf_class: bool) -> str:
    """Style a trie node label based on its role in the hierarchy.

    Module-path segments are dimmed, class names are bold + cyan.
    """
    if "." not in name:
        # Single segment: either a package part or a class name
        if is_leaf_class:
            return f"[bold cyan]{name}[/bold cyan]"
        return f"[dim]{name}[/dim]"

    # Collapsed dotted path — dim everything except the last segment,
    # which is the class name for leaf nodes.
    parts = name.rsplit(".", 1)
    prefix, last = parts[0], parts[1]
    if is_leaf_class:
        return f"[dim]{prefix}.[/dim][bold cyan]{last}[/bold cyan]"
    return f"[dim]{name}[/dim]"


def _render_trie(
    node: _TrieNode, tree: Tree, spinner_char: str | None = None,
) -> None:
    """Recursively render a trie into a ``rich.tree.Tree``."""
    for name, child in node["children"].items():
        # Leaf class node (has methods, no sub-children)
        if not child["children"] and child["methods"]:
            if len(child["methods"]) == 1:
                # Single method — show class and method on one line
                method_name, outcome, elapsed, reason = child["methods"][0]
                # Avoid duplicating the method name when _collapse_trie
                # has already merged the class node with its only child.
                if name == method_name or name.endswith(f".{method_name}"):
                    label = _format_node_label(name, is_leaf_class=True)
                else:
                    styled_name = _format_node_label(name, is_leaf_class=True)
                    label = f"{styled_name} › {method_name}"
                tree.add(_method_label(
                    label, outcome, elapsed, reason,
                    spinner_char=spinner_char,
                ))
            else:
                branch = tree.add(_format_node_label(name, is_leaf_class=True))
                for method_name, outcome, elapsed, reason in child["methods"]:
                    branch.add(_method_label(
                        method_name, outcome, elapsed, reason,
                        spinner_char=spinner_char,
                    ))
        else:
            # Intermediate node (may also carry methods in unusual layouts)
            branch = tree.add(_format_node_label(name, is_leaf_class=False))
            for method_name, outcome, elapsed, reason in child["methods"]:
                branch.add(_method_label(
                    method_name, outcome, elapsed, reason,
                    spinner_char=spinner_char,
                ))
            _render_trie(child, branch, spinner_char=spinner_char)


def _build_trie(
    outcomes: list[tuple[list[str], str, str, str, float, str]],
    running: list[tuple[list[str], str, str]] | None = None,
) -> _TrieNode:
    """Build a collapsed trie from completed outcomes and optionally running tests.

    *running* entries are ``(module_parts, class_name, method_name)`` and are
    inserted with outcome ``"_running"`` (elapsed=0, reason="").
    """
    trie = _new_trie_node()
    for module_parts, class_name, method_name, outcome, elapsed, reason in outcomes:
        node = trie
        for part in module_parts:
            if part not in node["children"]:
                node["children"][part] = _new_trie_node()
            node = node["children"][part]
        if class_name not in node["children"]:
            node["children"][class_name] = _new_trie_node()
        node["children"][class_name]["methods"].append(
            (method_name, outcome, elapsed, reason)
        )

    if running:
        for module_parts, class_name, method_name in running:
            node = trie
            for part in module_parts:
                if part not in node["children"]:
                    node["children"][part] = _new_trie_node()
                node = node["children"][part]
            if class_name not in node["children"]:
                node["children"][class_name] = _new_trie_node()
            node["children"][class_name]["methods"].append(
                (method_name, "_running", 0.0, "")
            )

    _collapse_trie(trie)
    return trie


def render_tree(
    outcomes: list[tuple[list[str], str, str, str, float, str]],
    console: Console | None = None,
) -> None:
    """Render test outcomes as a module > class > method tree.

    Each *outcome* tuple contains:
    ``(module_parts, class_name, method_name, outcome, elapsed, reason)``.

    Single-child chains are collapsed (e.g. ``apps → api → tests`` becomes
    ``apps.api.tests``) and classes with only one test method are rendered as
    a single leaf line.
    """
    if console is None:
        console = make_console()

    trie = _build_trie(outcomes)
    root = Tree("[title]Test Results[/title]", guide_style="dim")
    _render_trie(trie, root)
    console.print(root)


def build_live_tree(
    running: list[tuple[list[str], str, str]],
    spinner_char: str,
) -> Tree:
    """Build a Rich Tree for the live display (does NOT print).

    Only shows currently *running* tests with a spinning Braille-dot
    indicator.  Completed tests are not included — they appear in the
    final static tree printed after ``stopTestRun()``.
    """
    trie = _build_trie([], running)
    root = Tree("[title]Test Results[/title]", guide_style="dim")
    _render_trie(trie, root, spinner_char=spinner_char)
    return root


def build_status_line(
    total: int,
    completed: int,
    passed: int,
    failed: int,
    errors: int,
    skipped: int,
    running_count: int,
    spinner_char: str,
    elapsed: float,
) -> Text:
    """Build a Rich Text status line for the live display.

    Returns something like: ``⠋ 15/42 │ ✔ 12 │ ✘ 2 failed │ ⊘ 1 │ 3 running │ 1.2s``
    """
    parts: list[tuple[str, str]] = []
    parts.append((f"{spinner_char} ", "bold cyan"))
    parts.append((f"{completed}/{total}", "bold"))
    parts.append((" │ ", "dim"))
    parts.append(("✔ ", "bold green"))
    parts.append((str(passed), "bold green"))
    if failed:
        parts.append((" │ ", "dim"))
        parts.append(("✘ ", "bold red"))
        parts.append((f"{failed} failed", "bold red"))
    if errors:
        parts.append((" │ ", "dim"))
        parts.append(("✘ ", "bold red"))
        parts.append((f"{errors} error{'s' if errors != 1 else ''}", "bold red"))
    if skipped:
        parts.append((" │ ", "dim"))
        parts.append(("⊘ ", "bold yellow"))
        parts.append((str(skipped), "bold yellow"))
    if running_count:
        parts.append((" │ ", "dim"))
        parts.append((f"{running_count} running", "bold cyan"))
    parts.append((" │ ", "dim"))
    parts.append((f"{elapsed:.1f}s", "dim"))

    text = Text()
    for content, style in parts:
        text.append(content, style=style)
    return text


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
