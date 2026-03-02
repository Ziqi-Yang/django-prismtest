# Repository Guidelines

## What This Project Is

django-prismtest is a drop-in replacement for Django's `DiscoverRunner` that provides colorful test output with real-time Braille-dot spinners, syntax-highlighted tracebacks, and Rich-formatted summary panels. Users configure it via `TEST_RUNNER = "django_prismtest.runner.PrismDiscoverRunner"` in their Django settings.

## Commands

```bash
uv sync --group dev       # Install all deps including dev tools (pytest, ruff, pytest-cov)
uv run python -m pytest tests/              # Run full test suite
uv run python -m pytest tests/test_formatter.py  # Run a single test file
uv run python -m pytest tests/test_formatter.py::test_status_icon_pass -v  # Run a single test
uv run python main.py     # Run the visual demo of output formatting
```

## Architecture

The package lives in `django_prismtest/` with three modules in a clear pipeline:

- **`runner.py`** — `PrismDiscoverRunner` (subclasses Django's `DiscoverRunner`) and `PrismTestRunner` (subclasses `unittest.TextTestRunner`). Entry point for Django integration. Delegates to `PrismTestResult` as the result class.
- **`result.py`** — `PrismTestResult` (subclasses `unittest.TextTestResult`). Owns the test lifecycle: starts/stops a background `_Spinner` thread per test, records per-test timings, and calls formatter functions on `stopTestRun`. Bypasses `TextTestResult`'s default output by calling `unittest.TestResult` methods directly.
- **`formatter.py`** — Pure rendering functions (`format_traceback`, `render_summary`, `render_error_list`, `status_icon`) and constants (`PRISM_THEME`, `SPINNER_FRAMES`). Uses Rich for all styled output. No test-runner state—takes data in, returns/prints Rich objects.

`main.py` is a standalone demo script (not part of the package) that exercises the formatter visually.

## Testing

Tests use **pytest** (not unittest discover). Django settings are configured in `tests/conftest.py` via `pytest_configure()` using an in-memory SQLite database—no `manage.py` or Django project scaffold exists.

## Style

PEP 8, 4-space indent, type hints on public functions. Ruff is in dev dependencies but no config is set in `pyproject.toml` yet.
