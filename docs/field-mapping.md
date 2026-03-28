# Jira Field Mapping Guide

FlowBoard uses custom field IDs to read story points, epic links, and sprint data from Jira. This guide shows how to find the correct IDs for your instance.

## Quick Start

The Configuration Wizard auto-detects fields for you. Run `flowboard serve` and follow the wizard — it will scan your Jira instance automatically.

## Manual Field Discovery

### Method 1: Jira REST API (Recommended)

Open your browser and go to:

```
https://YOUR-INSTANCE.atlassian.net/rest/api/2/field
```

This returns a JSON array of all fields. Search for:

| FlowBoard Field | Common Jira Names | Example ID |
|---|---|---|
| `story_points` | "Story Points", "Story point estimate" | `customfield_10016` |
| `epic_link` | "Epic Link", "Epic" | `customfield_10014` |
| `sprint` | "Sprint" | `customfield_10020` |

### Method 2: Browser Dev Tools

1. Open any Jira issue in your browser
2. Open Developer Tools (F12) → Network tab
3. Reload the page
4. Find the API call to `/rest/api/2/issue/PROJ-123`
5. In the response JSON, look under `fields` for `customfield_*` entries

### Method 3: Jira Admin Panel (Cloud)

1. Go to **Settings** → **Issues** → **Custom Fields**
2. Click on a field name (e.g., "Story Points")
3. The URL will contain the field ID: `.../customfields/10016`
4. The config value is `customfield_10016`

## Configuration

Add the field IDs to your `config.json`:

```json
{
  "field_mappings": {
    "story_points": "customfield_10016",
    "epic_link": "customfield_10014",
    "sprint": "customfield_10020"
  }
}
```

## Jira Server / Data Center

Server instances often use different field IDs than Cloud. The auto-detect feature in the wizard handles both. Common differences:

| Field | Cloud (typical) | Server (typical) |
|---|---|---|
| Story Points | `customfield_10016` | `customfield_10002` |
| Epic Link | `customfield_10014` | `customfield_10008` |
| Sprint | `customfield_10020` | `customfield_10004` |

> **Tip:** Always verify via the REST API — field IDs are instance-specific.

## Troubleshooting

**"Story points are all 0"** — The field ID is wrong. Use the REST API method above to find the correct ID.

**"Epic column is empty"** — For Jira Cloud with next-gen projects, epic link may be under `parent` instead of a custom field. FlowBoard handles this automatically.

**"Sprint data missing"** — Ensure the Sprint field is a Jira Software field (not a custom text field). It should return an array of sprint objects, not a string.
