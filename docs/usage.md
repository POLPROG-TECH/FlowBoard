# Usage Guide

## CLI Commands

### `flowboard generate`

Fetches data from Jira and generates the HTML dashboard.

```bash
flowboard generate --config config.json
flowboard generate --config config.json --output reports/sprint-12.html
flowboard generate -c config.json -v  # verbose logging
```

### `flowboard validate-config`

Validates a config file without connecting to Jira.

```bash
flowboard validate-config --config config.json
```

### `flowboard verify`

Tests Jira connectivity and authentication.

```bash
flowboard verify --config config.json
```

### `flowboard demo`

Generates a demo dashboard from built-in mock data — no Jira needed.

```bash
flowboard demo
flowboard demo --output output/my-demo.html
```

### `flowboard version`

Prints the installed FlowBoard version.

## Common Workflows

### First-time Setup

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Create config
cp examples/config.example.json config.json
# Edit config.json with your Jira URL and projects

# 3. Set credentials
export FLOWBOARD_JIRA_EMAIL="you@company.com"
export FLOWBOARD_JIRA_TOKEN="your-token"

# 4. Validate
flowboard validate-config

# 5. Test connectivity
flowboard verify

# 6. Generate dashboard
flowboard generate
```

### Recurring Sprint Reports

```bash
# Generate a timestamped report
flowboard generate --output "reports/sprint-$(date +%Y%m%d).html"
```

### Team-specific Dashboards

Create separate config files per team:
```bash
flowboard generate --config config-platform.json --output output/platform.html
flowboard generate --config config-frontend.json --output output/frontend.html
```

### Programmatic Use

```python
from flowboard.infrastructure.config.loader import load_config_from_dict
from flowboard.application.orchestrator import Orchestrator

config = load_config_from_dict({
    "jira": {"base_url": "https://co.atlassian.net", "projects": ["PROJ"]},
    "output": {"path": "output/report.html"},
})

orch = Orchestrator(config)
path = orch.run()
print(f"Dashboard at: {path}")
```

### Export Data

```python
from flowboard.application.orchestrator import Orchestrator
from flowboard.presentation.export.json_export import export_json
from flowboard.presentation.export.csv_export import export_workload_csv

# After getting a snapshot
snapshot = orch.snapshot_from_payload(raw_data)

# JSON export
json_str = export_json(snapshot)

# CSV export
csv_str = export_workload_csv(snapshot)
```

## Dashboard Features

### Settings Panel

The dashboard includes a **Configure Dashboard** button (top-right). This opens a
settings panel where you can:

- Toggle tab visibility
- Change branding (title, subtitle, accent color)
- Adjust layout density
- Enable/disable individual charts
- Set risk and capacity thresholds
- Configure roadmap display options
- Export your current config as JSON
- Import a config JSON file
- Reset all settings to defaults

Changes are applied live and can be exported for reuse.

### PI (Program Increment) View

When PI mode is enabled in config, a dedicated **PI View** tab shows:

- PI name and overall progress bar
- 5 sprints with start/end dates and boundary markers
- Current sprint highlight
- Working days remaining in current sprint and PI
- "Today" position marker
- Zoom controls for scaling the timeline

Enable PI view by adding to your config:

```json
{
  "pi": {
    "enabled": true,
    "name": "PI 2026.1",
    "start_date": "2026-03-02"
  }
}
```

### Zoom and Navigation

Timeline views (Roadmap, PI) include floating controls:

- **+** / **-**: Zoom in/out
- **Reset**: Return to 100%
- **Fit**: Scale to fit window
- **Today**: Jump to current date

These work with horizontal scrolling for navigating wide timelines.

### Capacity Simulation

The Simulation mode is accessed via the Timeline tab's mode selector. It provides what-if capacity planning:

1. **Select a scenario** — preset scenarios are auto-generated per team (+1 resource, balanced expansion, focus top teams)
2. **Compare metrics** — before/after table shows collisions, overload, utilization, and more
3. **Review team impact** — per-team breakdown identifies where hiring would have the most impact
4. **Read recommendations** — actionable suggestions with severity and priority

Enable simulation in config:
```json
{
  "simulation": { "enabled": true }
}
```

### Scrum Analytics

The Sprints, Workload, and Insights tabs include dedicated Scrum analytics views:

- **Sprint Health** — completion rates, velocity, carry-over, aging issues
- **Sprint Goals** — goal tracking with item-level completion status
- **Scope Changes** — added/removed items, story point churn percentage
- **Capacity vs. Commitment** — allocated vs. completed points per sprint
- **Backlog Quality** — estimation coverage, size distribution, type balance
- **Sprint Readiness** — checklist of readiness criteria with pass/fail indicators
- **Blocker Aging** — blocked items with duration tracking and escalation severity
- **Delivery Forecast** — epic-level risk scoring with contributing factors
- **Dependency Heatmap** — cross-team dependency density matrix

### Internationalization

FlowBoard supports English and Polish (927 translation keys per locale).

Set the locale via:
- Config: `"locale": "pl"`
- CLI: `--locale pl`
- Environment: `FLOWBOARD_LOCALE=pl`
- Dashboard: Language buttons in Settings drawer

The dashboard language switch updates localStorage and is applied on the next regeneration.
