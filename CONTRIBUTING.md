# Contributing to FlowBoard

Thank you for your interest in contributing to FlowBoard! This guide covers everything you need to get started.

## Development Setup

```bash
git clone https://github.com/polprog-tech/FlowBoard.git
cd FlowBoard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the installation:

```bash
flowboard version
```

### Pre-commit hook

```bash
cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## Running Tests

```bash
pytest                                    # all tests
pytest -v                                 # verbose
pytest tests/test_security.py             # specific file
pytest tests/test_security.py::TestCSP    # specific class
```

Tests follow the **GIVEN/WHEN/THEN** docstring pattern (see existing tests for examples).

## Code Quality

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/flowboard/
```

## Architecture

FlowBoard follows a clean layered architecture. See [`docs/architecture.md`](docs/architecture.md) for details.

```
src/flowboard/
├── cli/              # Typer CLI (generate, validate, verify, demo, version)
├── application/      # Orchestration pipeline, services
├── domain/           # Models, analytics, risk, workload, overlap, dependencies,
│                     #   timeline, scrum, simulation, pi
├── infrastructure/   # Jira client/connector/normalizer, config loader/validator
├── i18n/             # Translator engine, en.json, pl.json
├── presentation/     # HTML renderer, Jinja2 templates, components, charts, export
└── shared/           # Types, enums, utilities
```

Key rules:

- Domain layer has **zero** infrastructure imports
- Presentation layer depends on domain, never on Jira client directly
- Config is loaded once and passed down - no global singletons
- All Jira API access goes through `infrastructure/jira/`

## How to Contribute

### Reporting Bugs

Include: expected vs actual behavior, `config.json` / `flowboard.yaml` (redacted), Python/OS version, steps to reproduce.

### Pull Requests

1. Branch from `main`
2. Make changes + add tests
3. Run `pytest` and `ruff check src/ tests/`
4. Open PR with clear description

## Commit Convention

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

## Internationalization (i18n)

FlowBoard supports multiple languages. Currently supported locales: **English (en)** and **Polish (pl)**.

Translation files live in `src/flowboard/i18n/`:

- `en.json` - English (reference/source)
- `pl.json` - Polish

When adding or updating translations:

1. Add the new key to **both** `en.json` and `pl.json`.
2. Use flat dot-notation keys (e.g. `"section.overview": "Overview"`).
3. For interpolation, use `{variable}` placeholders.
4. For plurals, provide separate keys: `plural.day.one`, `plural.day.few`, `plural.day.many`, `plural.day.other`.
5. Run `pytest tests/test_i18n.py` to verify key parity and placeholder consistency.

To add a new language:

1. Copy `en.json` to `<code>.json` (e.g. `de.json`) and translate all values.
2. Update `_meta.locale` to the new code.
3. Add the locale code to the `"locale"` enum in `config.schema.json`.
4. Add the locale code to the Pydantic config model's locale field.
5. Add plural rules in `translator.py` if the language has complex pluralization.
6. Run `pytest tests/test_i18n.py` to verify.

## License

See [LICENSE](LICENSE).
