# Repository Guidelines

## Project Structure & Module Organization
This repository is currently a minimal Python project at the root level:
- `main.py`: current executable entry point.
- `pyproject.toml`: project metadata and dependencies (`django`).
- `uv.lock`: locked dependency graph for reproducible installs.
- `README.md`: short project description.

When adding features, prefer grouping Django code into top-level packages (for example, `project/`, `apps/`, `tests/`) instead of expanding root-level scripts.

## Build, Test, and Development Commands
Use `uv` for environment and dependency management.
- `uv sync`: create/update `.venv` from `pyproject.toml` and `uv.lock`.
- `uv run python main.py`: run the current entry script.
- `uv add <package>`: add a dependency and update lockfile.
- `uv run python -m django --version`: verify Django is installed in the environment.

If a Django project scaffold is added later, document and standardize `manage.py` commands here.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions/modules, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep functions focused and side effects explicit.
- Add type hints to new public functions.

No formatter/linter is configured yet in `pyproject.toml`; if one is introduced (for example, Ruff), apply it consistently across the repo.

## Testing Guidelines
A formal test suite is not present yet. Add tests with new behavior changes.
- Place tests under `tests/`.
- Name files `test_<feature>.py` and test functions `test_<behavior>()`.
- Run tests with `uv run python -m unittest discover -s tests` until a dedicated framework is configured.

For future Django apps, prefer framework-native test modules and isolate DB-dependent tests.

## Commit & Pull Request Guidelines
Git history currently contains a single initial commit (`init`), so conventions are not yet established.
Use concise, imperative commit subjects (examples: `add prism output formatter`, `wire django test command`).

For pull requests:
- Summarize what changed and why.
- Link related issues/tasks.
- Include test evidence (command + result).
- Attach terminal screenshots/log snippets when output formatting changes.
