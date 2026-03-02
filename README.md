# django-prismtest

A modern, colorful Django test runner with real-time spinners, syntax-highlighted output, and beautifully formatted test results.

## Features

- Real-time Braille-dot spinner while each test runs
- Colored pass/fail/error/skip indicators with Unicode icons
- Per-test timing and "slowest tests" report
- Rich-formatted summary panel with pass/fail counts
- Syntax-highlighted tracebacks with project code emphasis
- Drop-in replacement for Django's `DiscoverRunner`

## Requirements

- Python 3.13+
- Django 6.0+
- Rich 14.0+

## Installation

```bash
pip install django-prismtest
```

Or with uv:

```bash
uv add django-prismtest
```

## Usage

Add to your Django settings:

```python
TEST_RUNNER = "django_prismtest.runner.PrismDiscoverRunner"
```

Then run tests as usual:

```bash
python manage.py test
```

## Configuration

### `PRISMTEST_HIGHLIGHT_PATH`

Set this in your Django settings to highlight your project's code in tracebacks:

```python
PRISMTEST_HIGHLIGHT_PATH = "/path/to/your/project/"
```

Lines from this path will appear in bold yellow, making it easy to spot your code in stack traces.

## Demo

Run the demo to preview the output formatting:

```bash
uv run python main.py
```

## Development

```bash
# Install dependencies
uv sync --group dev

# Run tests
uv run python -m pytest tests/

# Run the demo
uv run python main.py
```
