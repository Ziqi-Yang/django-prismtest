"""Quick demo of django-prismtest output formatting."""

import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from django_prismtest.formatter import (
    SPINNER_FRAMES,
    format_traceback,
    make_console,
    render_summary,
    status_icon,
)


def demo_spinner() -> None:
    """Show the spinner animation briefly."""
    console = make_console()
    console.print("\n[title]Spinner demo:[/title]")
    for i in range(20):
        frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
        sys.stderr.write(f"\r\033[36m{frame}\033[0m Running test_example...")
        sys.stderr.flush()
        time.sleep(0.08)
    sys.stderr.write("\r\033[K")
    sys.stderr.write("\033[32m  ✔ \033[0mtest_example\033[2m (0.123s)\033[0m\n")
    sys.stderr.flush()


def demo_icons() -> None:
    """Show all status icons."""
    console = make_console()
    console.print("\n[title]Status icons:[/title]")
    for outcome in ("pass", "fail", "error", "skip", "expected_failure", "unexpected_success"):
        console.print(f"  {status_icon(outcome)}  {outcome}")


def demo_traceback() -> None:
    """Show a syntax-highlighted traceback."""
    console = make_console()
    console.print("\n[title]Traceback formatting:[/title]")
    sample = (
        "Traceback (most recent call last):\n"
        '  File "/home/user/myproject/tests/test_views.py", line 42, in test_index\n'
        "    response = self.client.get('/')\n"
        '  File "/home/user/.venv/lib/python3.13/site-packages/django/test/client.py",'
        " line 1007, in get\n"
        "    return self.generic('GET', path, **r)\n"
        "AssertionError: 200 != 404"
    )
    text = format_traceback(sample, highlight_path="/home/user/myproject/")
    panel = Panel(text, title="[bold red]FAIL[/bold red]: test_index", border_style="red")
    console.print(panel)


def demo_summary() -> None:
    """Show a mock summary panel."""
    from unittest.mock import MagicMock

    result = MagicMock()
    result.testsRun = 12
    result.failures = [None, None]
    result.errors = [None]
    result.skipped = [None]
    result.expectedFailures = []
    result.unexpectedSuccesses = []
    result.wasSuccessful.return_value = False

    timings = [
        ("test_heavy_query (tests.test_db.DBTest)", 1.234),
        ("test_index (tests.test_views.ViewTest)", 0.456),
        ("test_login (tests.test_auth.AuthTest)", 0.321),
    ]

    console = make_console()
    render_summary(result, 4.56, timings, console=console)


def main() -> None:
    console = make_console()
    console.print(
        Panel(
            "[bold cyan]django-prismtest[/bold cyan] demo",
            subtitle="A modern, colorful Django test runner",
            border_style="cyan",
        )
    )

    demo_icons()
    demo_spinner()
    demo_traceback()
    demo_summary()

    console.print()
    console.print("[dim]To use in your Django project:[/dim]")
    console.print('[bold]  TEST_RUNNER = "django_prismtest.runner.PrismDiscoverRunner"[/bold]')
    console.print()


if __name__ == "__main__":
    main()
