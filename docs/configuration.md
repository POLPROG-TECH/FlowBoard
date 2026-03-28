# Configuration Reference

Complete reference for FlowBoard configuration. All fields, defaults, validation rules, and examples.

## Table of Contents

- [Configuration File](#configuration-file)
- [Environment Variable Overrides](#environment-variable-overrides)
- [Top-Level Fields](#top-level-fields)
- [Jira Configuration (`jira`)](#jira-configuration-jira)
- [Field Mappings (`field_mappings`)](#field-mappings-field_mappings)
- [Status Mapping (`status_mapping`)](#status-mapping-status_mapping)
- [Teams (`teams`)](#teams-teams)
- [Thresholds (`thresholds`)](#thresholds-thresholds)
- [Output (`output`)](#output-output)
- [Dashboard Configuration (`dashboard`)](#dashboard-configuration-dashboard)
  - [Theme](#theme)
  - [Branding](#branding)
  - [Layout](#layout)
  - [Tabs](#tabs)
  - [Summary Cards](#summary-cards)
  - [Charts](#charts)
  - [Tables](#tables)
  - [Filters](#filters)
  - [Risk Display](#risk-display)
  - [Roadmap](#roadmap)
  - [Timeline](#timeline)
  - [Sections Collapsed](#sections-collapsed)
  - [Refresh Metadata](#refresh-metadata)
- [PI Configuration (`pi`)](#pi-configuration-pi)
- [Simulation (`simulation`)](#simulation-simulation)
- [Locale (`locale`)](#locale-locale)
- [Blocked Link Types (`blocked_link_types`)](#blocked-link-types-blocked_link_types)
- [In-Dashboard Settings](#in-dashboard-settings)
- [Validation](#validation)
- [Examples](#examples)

---

## Configuration File

FlowBoard reads a JSON configuration file validated against `config.schema.json`.

- **Default location:** `config.json` in the current working directory.
- **Format:** JSON, validated against JSON Schema draft-07.
- **CLI override:**

```bash
flowboard generate --config /path/to/config.json
# or
flowboard generate -c /path/to/config.json
```

---

## Environment Variable Overrides

Environment variables always take precedence over values in the config file.

| Variable | Overrides | Example |
|----------|-----------|---------|
| `FLOWBOARD_JIRA_TOKEN` | `jira.auth_token` | `export FLOWBOARD_JIRA_TOKEN=your-token` |
| `FLOWBOARD_JIRA_EMAIL` | `jira.auth_email` | `export FLOWBOARD_JIRA_EMAIL=user@company.com` |
| `FLOWBOARD_JIRA_URL` | `jira.base_url` | `export FLOWBOARD_JIRA_URL=https://jira.company.com` |
| `FLOWBOARD_LOCALE` | `locale` | `export FLOWBOARD_LOCALE=pl` |

---

## Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `jira` | object | **yes** | — | Jira connection and query settings |
| `field_mappings` | object | no | `{}` | Custom field ID mappings |
| `status_mapping` | object | no | `{}` | Jira status → category mapping |
| `teams` | array | no | `[]` | Team definitions for grouping |
| `thresholds` | object | no | see below | Workload and risk thresholds |
| `output` | object | no | see below | Output file settings |
| `dashboard` | object | no | see below | Dashboard presentation settings |
| `pi` | object | no | see below | Program Increment configuration |
| `simulation` | object | no | `{"enabled": true}` | Simulation toggle |
| `locale` | string | no | `"en"` | UI language (`"en"`, `"pl"`) |
| `blocked_link_types` | array | no | `["Blocks", "is blocked by"]` | Link types indicating blockers |

---

## Jira Configuration (`jira`)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `base_url` | string | **yes** | `""` | Jira instance URL (must start with `http://` or `https://`) |
| `auth_token` | string | no | `""` | API token or PAT. Prefer `FLOWBOARD_JIRA_TOKEN` env var |
| `auth_email` | string | no | `""` | Email for basic auth. Prefer `FLOWBOARD_JIRA_EMAIL` env var |
| `server_type` | string | no | `"cloud"` | Jira deployment type: `"cloud"`, `"server"`, `"datacenter"` |
| `auth_method` | string | no | `"basic"` | Authentication method: `"basic"`, `"pat"` |
| `api_version` | string | no | `"2"` | Jira REST API version |
| `projects` | string[] | no | `[]` | Project keys to include (e.g. `["PROJ", "TEAM"]`) |
| `boards` | int[] | no | `[]` | Board IDs for sprint data |
| `max_results` | integer | no | `100` | Issues per API page (range: 1–1000) |
| `jql_filter` | string | no | `""` | Additional JQL filter appended to queries |

---

## Field Mappings (`field_mappings`)

Maps FlowBoard concepts to Jira custom field IDs.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `story_points` | string | `"customfield_10016"` | Custom field ID for story points |
| `epic_link` | string | `"customfield_10014"` | Custom field ID for epic link |
| `sprint` | string | `"customfield_10020"` | Custom field ID for sprint |
| *(extra)* | dict | `{}` | Additional custom field mappings as key-value string pairs |

The schema allows `additionalProperties` of type `string` for extra field mappings.

---

## Status Mapping (`status_mapping`)

Maps Jira status names to FlowBoard categories. Keys are your Jira status names (arbitrary strings), values must be one of: `"To Do"`, `"In Progress"`, `"Done"`.

```json
{
  "status_mapping": {
    "Open": "To Do",
    "Backlog": "To Do",
    "In Development": "In Progress",
    "Code Review": "In Progress",
    "Testing": "In Progress",
    "Closed": "Done",
    "Released": "Done"
  }
}
```

Built-in defaults cover common statuses: To Do, Open, Backlog, New, Reopened, In Progress, In Development, In Review, In QA, Code Review, Testing, Blocked, Done, Closed, Resolved, Released.

---

## Teams (`teams`)

Array of team definitions for grouping people in workload and timeline views.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `key` | string | **yes** | — | Unique team identifier |
| `name` | string | **yes** | — | Display name |
| `members` | string[] | no | `[]` | Jira account IDs or display names |

```json
{
  "teams": [
    {
      "key": "platform",
      "name": "Platform Team",
      "members": ["account-id-1", "account-id-2"]
    }
  ]
}
```

---

## Thresholds (`thresholds`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `overload_points` | number | `20` | Story points above which a person is overloaded |
| `overload_issues` | integer | `8` | Issue count above which a person is overloaded |
| `wip_limit` | integer | `5` | Max in-progress items per person |
| `aging_days` | integer | `14` | Days after which an open issue is flagged as aging |
| `capacity_per_person` | number | `13` | Default SP capacity per person per sprint |

---

## Output (`output`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `"output/dashboard.html"` | Output file path |
| `title` | string | `"FlowBoard Dashboard"` | Dashboard title |
| `primary_color` | string | `"#fb6400"` | Primary accent colour (CSS hex) |
| `company_name` | string | `""` | Company name shown in footer |

---

## Dashboard Configuration (`dashboard`)

The `dashboard` section controls all presentation aspects of the generated HTML dashboard. It contains a `theme` field and multiple nested configuration objects.

### Theme

`dashboard.theme` — global colour scheme.

| Value | Description |
|-------|-------------|
| `"light"` | Light background, dark text |
| `"dark"` | Dark background, light text |
| `"midnight"` | Deep dark theme |
| `"slate"` | Grey-toned dark theme |
| `"system"` | Follows OS preference (default) |

Default: `"system"`. Invalid values fall back to `"light"`.

### Branding

`dashboard.branding` — header and identity.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | string | `"FlowBoard Dashboard"` | Main dashboard title (falls back to `output.title`) |
| `subtitle` | string | `"Jira-Based Delivery & Workload Intelligence"` | Subtitle below the title |
| `primary_color` | string | `"#fb6400"` | Primary accent colour (falls back to `output.primary_color`) |
| `secondary_color` | string | `"#002754e6"` | Secondary colour |
| `tertiary_color` | string | `"#666666"` | Tertiary colour |
| `company_name` | string | `""` | Company name (falls back to `output.company_name`) |

### Layout

`dashboard.layout` — spacing and width.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `density` | string | `"comfortable"` | `"compact"`, `"comfortable"`, or `"spacious"` |
| `max_width` | string | `"1440px"` | Maximum dashboard width (CSS value) |

### Tabs

`dashboard.tabs` — tab visibility and ordering.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `visible` | string[] | all 8 tabs | Which tabs to display |
| `order` | string[] | same as visible | Display order of tabs |
| `default_tab` | string | `"overview"` | Tab shown on initial load |

**Valid tab IDs:** `overview`, `workload`, `sprints`, `timeline`, `pi`, `insights`, `dependencies`, `issues`

### Summary Cards

`dashboard.summary_cards` — executive summary bar.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `visible` | string[] | all 9 cards | Which summary cards to show |

**Valid card IDs:** `total_issues`, `open_issues`, `blocked`, `story_points`, `completed_sp`, `critical_risks`, `high_risks`, `overloaded`, `conflicts`

### Charts

`dashboard.charts` — chart toggles.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Master toggle for all charts |
| `status_distribution` | boolean | `true` | Status distribution pie chart |
| `type_distribution` | boolean | `true` | Issue type distribution chart |
| `risk_severity` | boolean | `true` | Risk severity bar chart |
| `team_workload` | boolean | `true` | Team workload comparison chart |
| `sprint_progress` | boolean | `true` | Sprint progress chart |
| `workload_per_person` | boolean | `true` | Per-person workload chart |

### Tables

`dashboard.tables` — issues table configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `issues_columns` | string[] | `["key", "summary", "type", "status", "assignee", "sp", "priority", "sprint", "age"]` | Columns in the issues table |
| `max_rows` | integer | `200` | Maximum rows displayed (range: 1–5000) |
| `default_sort` | string | `"key"` | Default sort column |
| `sort_direction` | string | `"asc"` | Sort direction: `"asc"` or `"desc"` |

### Filters

`dashboard.filters` — default filter values applied on load.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_teams` | string[] | `[]` | Pre-selected team filters |
| `default_sprints` | string[] | `[]` | Pre-selected sprint filters |
| `default_statuses` | string[] | `[]` | Pre-selected status filters |
| `default_types` | string[] | `[]` | Pre-selected issue type filters |
| `default_priorities` | string[] | `[]` | Pre-selected priority filters |

### Risk Display

`dashboard.risk_display` — risk presentation options.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `show_severity_badges` | boolean | `true` | Show severity badge chips on risks |
| `show_recommendations` | boolean | `true` | Show actionable recommendations |
| `highlight_blocked` | boolean | `true` | Visually highlight blocked issues |

### Roadmap

`dashboard.roadmap` — roadmap view settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `time_window_months` | integer | `3` | Visible time window (range: 1–24) |
| `default_zoom` | integer | `100` | Default zoom percentage (range: 25–400) |
| `show_dependencies` | boolean | `true` | Show dependency lines between items |
| `show_risk_badges` | boolean | `true` | Show risk badges on roadmap items |

### Timeline

`dashboard.timeline` — interactive Gantt-style timeline with overlap detection.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_mode` | string | `"assignee"` | Initial view mode (see below) |
| `default_zoom` | integer | `100` | Default zoom percentage (range: 25–400) |
| `max_swimlanes` | integer | `30` | Maximum swimlane count (range: 1–100) |
| `show_overlaps` | boolean | `true` | Highlight overlapping work items |
| `show_sprint_boundaries` | boolean | `true` | Show sprint boundary markers |
| `show_today_marker` | boolean | `true` | Vertical "today" indicator line |
| `compact_bar_height` | boolean | `false` | Use compact bar height for density |

**Timeline modes (`default_mode`):**

| Mode | Description |
|------|-------------|
| `assignee` | Swimlanes per person — shows parallel work, overload |
| `team` | Swimlanes per team — shows cross-team pressure |
| `epic` | Swimlanes per epic — shows roadmap execution |
| `conflict` | Highlights overlapping items only — collision focus |
| `executive` | Compact leadership view capped at 15 swimlanes |

Each mode supports filtering by team, project, assignee, priority, and search text. Overlap severity is colour-coded: medium (2 items), high (3), critical (4+).

### Sections Collapsed

`dashboard.sections_collapsed` — array of section IDs to start collapsed on load.

Default: `[]` (all sections expanded).

### Refresh Metadata

`dashboard.refresh_metadata` — boolean, default `true`.

When enabled, the dashboard shows a "generated at" timestamp in the header.

---

## PI Configuration (`pi`)

The `pi` section configures the Program Increment timeline view.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable the PI view tab |
| `name` | string | `""` | PI display name (e.g. `"PI 2026.1"`) |
| `start_date` | string | `""` | PI start date in ISO format (`YYYY-MM-DD`) |
| `sprints_per_pi` | integer | `5` | Number of sprints in the PI (range: 1–20) |
| `sprint_length_days` | integer | `10` | Working days per sprint (range: 1–40) |
| `working_days` | int[] | `[1, 2, 3, 4, 5]` | ISO weekday numbers (1=Mon … 7=Sun) |
| `show_weekends` | boolean | `false` | Show weekend columns in the timeline |
| `date_format` | string | `"%b %d"` | Python strftime format for date labels |
| `show_today_marker` | boolean | `true` | Show vertical "today" line |
| `show_sprint_boundaries` | boolean | `true` | Show sprint boundary markers |
| `show_progress_indicator` | boolean | `true` | Show PI progress bar |
| `show_remaining_days` | boolean | `true` | Show days remaining counters |

**Sprint date calculation rules:**

1. Sprint 1 starts on the PI `start_date` (or next working day if it falls on a weekend).
2. Each sprint spans exactly `sprint_length_days` working days.
3. Sprint N+1 starts on the next working day after sprint N ends.
4. Non-working days (weekends) are skipped in day counting.
5. The "today" marker shows the current position in the PI.
6. The current sprint is highlighted.

---

## Simulation (`simulation`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable workload simulation |

---

## Locale (`locale`)

UI language setting.

- **Type:** string
- **Default:** `"en"`
- **Valid values:** `"en"`, `"pl"`

Can be overridden with the `FLOWBOARD_LOCALE` environment variable.

---

## Blocked Link Types (`blocked_link_types`)

Array of Jira issue link type names that indicate blocking relationships.

- **Type:** string[]
- **Default:** `["Blocks", "is blocked by"]`

---

## In-Dashboard Settings

The generated HTML dashboard includes a settings drawer accessible via the gear icon in the header. The drawer contains **5 configuration cards** with a total of **36 controls**:

| Card | Controls |
|------|----------|
| **Theme & Language** | Theme selector, locale selector |
| **Branding** | Title, subtitle, colours, company name |
| **Layout & Tabs** | Density, tab visibility toggles, default tab |
| **Thresholds** | Overload points, overload issues, WIP limit, aging days, capacity |
| **Charts & Display** | Chart toggles, risk display toggles, roadmap settings |

**Actions available:**

- **Apply** — apply changes to the current view.
- **Reset to Defaults** — restore all settings to defaults.
- **Export JSON** — download the current configuration (secrets are stripped).
- **Import JSON** — upload a JSON config file to apply.

Changes made in the settings drawer are applied locally to the current session. To persist changes across regenerations, export the JSON and save it as your `config.json`.

---

## Validation

Validate your configuration without running the full pipeline:

```bash
flowboard validate-config --config config.json
```

Validation rules:

- **Schema validation** — JSON Schema draft-07 with `additionalProperties: false`. Any typo or unknown field produces a clear error.
- **Import validation** — imported config must be a valid JSON object.
- **Locale validation** — invalid locale values fall back to `"en"`.
- **Theme validation** — invalid theme values fall back to `"light"`.

---

## Examples

- [`examples/config.minimal.json`](../examples/config.minimal.json) — minimal configuration (Jira URL, projects, output path).
- [`examples/config.example.json`](../examples/config.example.json) — full configuration with all sections populated.
