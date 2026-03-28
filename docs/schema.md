# Configuration Schema Reference

FlowBoard configuration is validated against a JSON Schema (draft-07). This document describes the validation rules and constraints.

## Table of Contents

- [Schema File](#schema-file)
- [Validation](#validation)
- [Required Fields](#required-fields)
- [Type Constraints](#type-constraints)
- [Default Values](#default-values)
- [Validation Behavior](#validation-behavior)

## Schema File

Located at `config.schema.json` in the project root.

The schema defines every accepted configuration key, its type, allowed values, and defaults. It is the authoritative source for configuration structure.

## Validation

- Run: `flowboard validate-config --config config.json`
- Schema uses `additionalProperties: false` — unknown keys are rejected
- Validation powered by the `jsonschema` library

```bash
# Validate a configuration file
flowboard validate-config --config config.json

# Example output on success:
# ✓ Configuration is valid
# Active settings summary printed as table
```

## Required Fields

Only one field is strictly required:

- **`jira.base_url`** — Jira instance URL (e.g., `https://yourcompany.atlassian.net`)

All other fields have sensible defaults. A minimal valid configuration:

```json
{
  "jira": {
    "base_url": "https://yourcompany.atlassian.net"
  }
}
```

## Type Constraints

### Enumerations

| Field                               | Allowed Values                                        |
| ----------------------------------- | ----------------------------------------------------- |
| `jira.server_type`                  | `cloud`, `server`, `datacenter`                       |
| `jira.auth_method`                  | `basic`, `pat`, `oauth`                               |
| `dashboard.theme`                   | `light`, `dark`, `midnight`, `slate`, `system`        |
| `dashboard.layout.density`          | `compact`, `comfortable`, `spacious`                  |
| `dashboard.timeline.default_mode`   | `assignee`, `team`, `epic`, `conflict`, `executive`   |
| `dashboard.tables.sort_direction`   | `asc`, `desc`                                         |
| `locale`                            | `en`, `pl`                                            |

### Numeric Ranges

| Field                              | Minimum | Description                          |
| ---------------------------------- | ------- | ------------------------------------ |
| `jira.max_results`                 | 1       | Max issues per API page              |
| `thresholds.overload_points`       | 1       | SP threshold for overload warning    |
| `thresholds.overload_issues`       | 1       | Issue count threshold for overload   |
| `thresholds.wip_limit`            | 1       | Work-in-progress limit per person    |
| `thresholds.aging_days`           | 1       | Days before issue is considered stale|
| `thresholds.capacity_per_person`   | 1       | Expected SP capacity per sprint      |
| `pi.sprints_per_pi`               | 1       | Number of sprints in a PI            |
| `pi.sprint_length_days`           | 1       | Duration of each sprint in days      |

### String Formats

| Field                  | Format                    | Example                              |
| ---------------------- | ------------------------- | ------------------------------------ |
| `jira.base_url`        | URI format                | `https://yourcompany.atlassian.net`  |
| `output.primary_color` | Hex color `^#[0-9a-fA-F]{6}$` | `#FF6B35`                       |
| `pi.start_date`        | ISO date format           | `2024-01-15`                         |

## Default Values

Refer to [`docs/configuration.md`](configuration.md) for the complete list of default values for all configuration fields.

Key defaults:

| Field                | Default Value  |
| -------------------- | -------------- |
| `jira.server_type`   | `cloud`        |
| `jira.auth_method`   | `basic`        |
| `jira.max_results`   | `100`          |
| `dashboard.theme`    | `light`        |
| `locale`             | `en`           |

## Validation Behavior

### CLI Validation

`validate-config` performs full schema validation and prints a summary table of active settings:

```bash
flowboard validate-config --config config.json
```

On success, displays a formatted table showing all configured values and their sources (config file, environment variable, or default).

### Import Validation

The dashboard import function checks:
- File contains valid JSON (parseable)
- Parsed value is a JSON object (arrays, strings, numbers, and `null` are rejected)
- Invalid JSON shows an error toast notification in the dashboard

### Locale Validation

- Unsupported locale values fall back to `"en"` with a logged warning
- Only `"en"` and `"pl"` are currently supported

### Theme Validation

- Unknown theme values fall back to `"light"`
- The `"system"` theme follows the OS preference via `prefers-color-scheme` media query
