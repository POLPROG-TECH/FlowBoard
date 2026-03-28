# FlowBoard Architecture

## Overview

FlowBoard follows a **clean layered architecture** where each layer has a single responsibility and dependencies flow inward — presentation depends on domain, never the reverse.

```
┌─────────────────────────────────────────────┐
│                   CLI                       │  Entry point (Typer)
├─────────────────────────────────────────────┤
│              Application                    │  Orchestrator, services
├──────────────────┬──────────────────────────┤
│     Domain       │     Presentation         │
│  Models          │  HTML Renderer           │
│  Analytics       │  Components / Charts     │
│  Risk Engine     │  Export (JSON/CSV)        │
│  Workload        │                          │
│  Overlap         │                          │
│  Dependencies    │                          │
│  Timeline        │                          │
│  Scrum           │                          │
│  Simulation      │                          │
│  PI              │                          │
├──────────────────┴──────────────────────────┤
│              Infrastructure                 │
│  Jira Client / Connector / Normalizer       │
│  Config Loader / Validator                  │
├─────────────────────────────────────────────┤
│            i18n (Translator)                │
│  Locale detection, fallback, formatting     │
├─────────────────────────────────────────────┤
│               Shared                        │
│  Types, Enums, Utilities                    │
└─────────────────────────────────────────────┘
```

## Layer Responsibilities

### CLI (`cli/`)
- Typer-based command interface
- Parses arguments, loads config, invokes orchestrator
- Commands: `generate`, `validate-config`, `verify`, `demo`, `version`

### Application (`application/`)
- **Orchestrator**: Pipeline controller — fetch → normalise → analyse → render
- **Services**: Thin helpers for Jira connectivity verification and config description

### Domain (`domain/`)
- **Models** (`models.py`): Core domain objects — `Issue`, `Person`, `Team`, `Sprint`, `WorkloadRecord`, `RiskSignal`, `BoardSnapshot`, etc.
- **Analytics** (`analytics.py`): Facade that coordinates all analytical engines
- **Workload** (`workload.py`): Per-person and per-team workload/capacity computation
- **Risk** (`risk.py`): Risk signal detection — overload, aging, blocked, WIP, sprint, roadmap
- **Dependencies** (`dependencies.py`): Blocked issue finder, dependency chain builder, sprint health
- **Overlap** (`overlap.py`): Resource contention, priority pile-ups, timeline overlaps, cross-team friction
- **Timeline** (`timeline.py`): Gantt-style timeline data builder — 5 view modes (assignee, team, epic, conflict, executive), swimlane construction, overlap/collision detection with severity grading
- **Scrum** (`scrum.py`): Sprint analytics — health tracking, goal completion, scope changes, capacity vs. commitment, backlog quality, sprint readiness, blocker aging, delivery risk forecast, dependency heatmap, ceremony tracking
- **Simulation** (`simulation.py`): Capacity what-if planning — scenario modeling (add/remove resources), workload redistribution, collision prediction, team impact scoring, staffing recommendations
- **PI** (`pi.py`): Program Increment domain logic — sprint boundary computation, business-day arithmetic, PI snapshot generation

### Infrastructure (`infrastructure/`)
- **Jira Client** (`jira/client.py`): Low-level HTTP, auth, pagination, retry, rate-limit handling
- **Jira Connector** (`jira/connector.py`): High-level data fetching orchestration
- **Jira Normalizer** (`jira/normalizer.py`): The **sole translation boundary** — converts raw Jira JSON to domain objects
- **Config Loader** (`config/loader.py`): JSON loading, env var overrides, typed config objects including `DashboardConfig` (12 sub-configs incl. `TimelineDisplayConfig`) and `PIConfig`
- **Config Validator** (`config/validator.py`): JSON Schema validation

### Presentation (`presentation/`)
- **HTML Renderer** (`html/renderer.py`): Jinja2-based template rendering
- **Components** (`html/components.py`): Reusable HTML fragment builders (cards, tables, badges)
- **Charts** (`html/charts.py`): Chart.js data builders
- **Templates** (`html/templates/`): Jinja2 HTML templates
- **Export** (`export/`): JSON and CSV export

### Shared (`shared/`)
- **Types** (`types.py`): Enumerations (`IssueType`, `StatusCategory`, `RiskSeverity`, etc.)
- **Utils** (`utils.py`): Date parsing, safe division, string utilities, secret masking

### i18n (`i18n/`)
- **Translator** (`translator.py`): Thread-safe translation engine with locale-aware formatting
- **Locale Files** (`en.json`, `pl.json`): 927 translation keys per locale — UI strings, labels, tooltips, validation messages
- Fallback chain: current locale → English → key string
- Pluralization: English (2 forms), Polish (3 forms with morphological rules)
- Date/number formatting: locale-aware month names, decimal separators, thousands grouping

## Key Design Decisions

### 1. Single HTML File Output
The generated dashboard is a self-contained HTML file with embedded CSS and JavaScript. This makes it trivially shareable — via email, Slack, file server — with no server deployment needed.

### 2. Jira Normalisation Boundary
All Jira API JSON parsing happens in `normalizer.py`. No other module touches raw Jira field names. This means Jira API changes or field mapping differences are isolated to one file.

### 3. Pure Domain Analytics
All analytics functions (`workload.py`, `risk.py`, `overlap.py`, `dependencies.py`) are pure functions operating on domain objects. They have no network calls, no I/O, and no config dependencies beyond thresholds passed as arguments. This makes them trivially testable.

### 4. BoardSnapshot as the Presentation Contract
The `BoardSnapshot` dataclass is the single contract between analytics and presentation. The HTML renderer receives a fully-computed snapshot and renders it — it never performs calculations itself.

### 5. Config-Driven Everything
Projects, teams, thresholds, field mappings, status mappings, output settings, dashboard presentation, PI timing — all configurable via JSON validated against a strict JSON Schema. The `DashboardConfig` subsystem contains 11 nested dataclasses (branding, layout, tabs, summary cards, charts, tables, filters, risk display, roadmap display, sections, refresh metadata).

### 6. Dashboard Configuration Round-Trip
Configuration flows bidirectionally: JSON -> Python config -> HTML rendering, and UI edits -> in-memory config -> exported JSON. The `config_to_dict()` function serializes configuration back to JSON-safe dicts (with secrets stripped), enabling import/export from the settings panel.

### 7. PI as Domain Logic
Sprint boundary calculations, business-day arithmetic, and PI progress tracking live in `domain/pi.py` as pure functions — testable without I/O. The PI snapshot is computed during the analytics phase and attached to `BoardSnapshot`.

## Extensibility Points

| Want to add... | Where |
|-------------|-------|
| New analytics | Add function in `domain/`, call from `analytics.py`, add to `BoardSnapshot` |
| New dashboard tab | Add to `_DEFAULT_TABS` in loader, add section in `dashboard.html`, add component in `components.py` |
| New chart | Add data builder in `charts.py`, add `<canvas>` + init in template, add toggle to `ChartsConfig` |
| New risk detector | Add function in `risk.py`, call from `detect_all_risks()` |
| New export format | Add module in `presentation/export/` |
| New Jira fields | Add to `FieldMappings`, parse in `normalizer.py` |
| New data source | Create new connector in `infrastructure/`, normalise to same domain models |
| New dashboard config | Add dataclass in `loader.py`, add to schema, add UI control in settings panel |
| New PI behavior | Extend `PIConfig`, update `domain/pi.py`, update PI template section |
| New scrum analytics | Add function in `domain/scrum.py`, add renderer in `components.py`, add template section |
| New simulation scenario | Add preset in `domain/simulation.py`, scenario is auto-rendered |
| New locale | Add `xx.json` in `i18n/`, add to `_SUPPORTED_LOCALES`, add to schema enum |
