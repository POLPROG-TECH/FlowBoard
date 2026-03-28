# Contributing to FlowBoard

Thank you for your interest in improving FlowBoard! This document provides guidelines for contributing.

## Development Setup

```bash
git clone https://github.com/POLPROG-TECH/FlowBoard.git
cd FlowBoard
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Code Standards

- **Python 3.12+** with full type hints on all public APIs
- **Ruff** for linting and formatting: `ruff check src/ tests/`
- **mypy** for type checking: `mypy src/flowboard/`
- **pytest** for testing: `pytest`

## Architecture

FlowBoard follows a clean layered architecture. See `docs/architecture.md` for details.

```
src/flowboard/
├── cli/              # Typer CLI (generate, validate, verify, demo, version)
├── application/      # Orchestration pipeline, services
├── domain/           # Models, analytics, risk, workload, overlap, dependencies,
│                     #   timeline, scrum, simulation, pi
├── infrastructure/   # Jira client/connector/normalizer, config loader/validator
├── i18n/             # Translator engine, en.json, pl.json (927 keys)
├── presentation/     # HTML renderer, Jinja2 templates, components, charts, export
└── shared/           # Types, enums, utilities
```

Key rules:
- Domain layer has **zero** infrastructure imports
- Presentation layer depends on domain, never on Jira client directly
- Config is loaded once and passed down — no global singletons
- All Jira API access goes through `infrastructure/jira/`

## Making Changes

1. Create a feature branch from `main`
2. Write or update tests for your changes
3. Ensure all tests pass: `pytest`
4. Ensure linting passes: `ruff check src/ tests/`
5. Submit a pull request with a clear description

## Test Guidelines

- Use **GIVEN / WHEN / THEN** style for behavior tests
- Mock Jira API calls — never hit real Jira in tests
- Focus on analytics correctness and edge cases
- Keep tests fast and isolated

## Commit Messages

Use clear, descriptive commit messages:
```
feat: add burndown chart to sprint health view
fix: correct story point aggregation for sub-tasks
docs: update configuration guide for custom fields
```

## Internationalization (i18n)

FlowBoard supports multiple languages. Currently supported locales: **English (en)** and **Polish (pl)**.

### Selecting a Language

Set the locale in your config file:
```json
{ "locale": "pl" }
```

Or via CLI flag:
```bash
flowboard generate --config config.json --locale pl
```

Or via environment variable:
```bash
export FLOWBOARD_LOCALE=pl
```

**Precedence:** CLI flag > environment variable > config file > default (`en`).

### Translation Files

Translation files are JSON files in `src/flowboard/i18n/`:
- `en.json` — English (reference/source)
- `pl.json` — Polish

### Adding or Updating Translations

1. Add the new key to **both** `en.json` and `pl.json`.
2. Use flat dot-notation keys (e.g. `"section.overview": "Overview"`).
3. For interpolation, use `{variable}` placeholders: `"error.auth_failed": "Auth failed ({code})"`.
4. For plurals, provide separate keys: `plural.day.one`, `plural.day.few`, `plural.day.many`, `plural.day.other`.
5. Run `pytest tests/test_i18n.py` to verify key parity and placeholder consistency.

### Using Translations in Code

```python
from flowboard.i18n.translator import Translator

t = Translator("pl")
t("tab.overview")           # "📋 Przegląd"
t("cli.error", error="x")  # "Błąd: x"
t.plural(3, "plural.day.one", "plural.day.few", "plural.day.many")  # "3 dni"
t.format_date_short(date)   # "18 mar"
t.format_number(1234.5)     # "1 234,5"
```

### Adding a New Language

1. Copy `en.json` to `<code>.json` (e.g. `de.json`).
2. Translate all values.
3. Update `_meta.locale` to the new code.
4. Add the locale code to the `"locale"` enum in `config.schema.json`.
5. Add the locale code to the Pydantic config model's locale field.
6. Add plural rules in `translator.py` if the language has complex pluralization.
7. Run `pytest tests/test_i18n.py` to verify.

## Questions?

Open an issue or reach out to the FlowBoard team internally.
