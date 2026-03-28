# Jira Enterprise Integration Guide

Comprehensive guide for connecting FlowBoard to Jira Cloud, Server, and Data Center environments.

## Table of Contents

- [Supported Jira Environments](#supported-jira-environments)
- [Authentication](#authentication)
- [Required Permissions](#required-permissions)
- [Data Fetching](#data-fetching)
- [Custom Field Mapping](#custom-field-mapping)
- [Status Mapping](#status-mapping)
- [Rate Limiting & Resilience](#rate-limiting--resilience)
- [Troubleshooting](#troubleshooting)

## Supported Jira Environments

| Environment      | `server_type` | Tested Versions |
| ---------------- | ------------- | --------------- |
| Jira Cloud       | `cloud`       | Current         |
| Jira Server      | `server`      | 8.x, 9.x       |
| Jira Data Center | `datacenter`  | 8.x, 9.x       |

## Authentication

### Jira Cloud (Basic Auth)

- Email + API token
- Generate at: <https://id.atlassian.com/manage-profile/security/api-tokens>
- Config: `auth_method: "basic"`, `auth_email`, `auth_token`
- Or env vars: `FLOWBOARD_JIRA_EMAIL`, `FLOWBOARD_JIRA_TOKEN`

```json
{
  "jira": {
    "base_url": "https://yourcompany.atlassian.net",
    "server_type": "cloud",
    "auth_method": "basic",
    "auth_email": "user@company.com",
    "auth_token": "your-api-token"
  }
}
```

### Jira Server / Data Center (PAT)

- Personal Access Token
- Generate in: **Profile → Personal Access Tokens**
- Config: `auth_method: "pat"`, `auth_token` only
- Or env var: `FLOWBOARD_JIRA_TOKEN`

```json
{
  "jira": {
    "base_url": "https://jira.company.com",
    "server_type": "server",
    "auth_method": "pat",
    "auth_token": "your-personal-access-token"
  }
}
```

### Environment Variable Overrides

| Variable               | Overrides Config Key |
| ---------------------- | -------------------- |
| `FLOWBOARD_JIRA_TOKEN` | `jira.auth_token`    |
| `FLOWBOARD_JIRA_EMAIL` | `jira.auth_email`    |
| `FLOWBOARD_JIRA_URL`   | `jira.base_url`      |

- Environment variables **always** override config file values.
- Recommended for CI/CD pipelines and shared configurations.
- Keeps secrets out of version-controlled config files.

## Required Permissions

- **Browse Projects** on target projects
- **Read access** to boards and sprints (Jira Agile / Jira Software)

FlowBoard uses read-only APIs. No write permissions are needed.

## Data Fetching

### What FlowBoard Fetches

| Data              | API Endpoint                           | Purpose                       |
| ----------------- | -------------------------------------- | ----------------------------- |
| Issues            | `/rest/api/2/search`                   | All issue data via JQL        |
| Sprint data       | `/rest/agile/1.0/board/{id}/sprint`    | Sprint metadata and dates     |
| Board discovery   | `/rest/agile/1.0/board`                | Find boards for projects      |
| Server info       | `/rest/api/2/serverInfo`               | Verify connectivity and type  |

### JQL Construction

- Auto-built from `projects` list: `project in (PROJ1, PROJ2)`
- Combined with optional `jql_filter` using `AND`
- Ordered by `updated DESC`
- Paginated (default 100 per page, safety limit 50,000 issues)

Example with filter:

```
project in (PROJ1, PROJ2) AND status != Closed ORDER BY updated DESC
```

### Sprint Discovery

- Fetched from configured `boards` array
- Or auto-discovered from boards matching configured projects
- Deduplicated by sprint ID
- Includes active, closed, and future sprints

## Custom Field Mapping

| Purpose      | Config Key                       | Jira Default        | How to Find                         |
| ------------ | -------------------------------- | ------------------- | ----------------------------------- |
| Story Points | `field_mappings.story_points`    | `customfield_10016` | Jira Admin → Custom Fields          |
| Epic Link    | `field_mappings.epic_link`       | `customfield_10014` | Issue JSON → `fields` object        |
| Sprint       | `field_mappings.sprint`          | `customfield_10020` | Usually auto-detected               |

### Finding Custom Field IDs

1. **Via REST API:**

   ```bash
   curl -u user@company.com:API_TOKEN \
     https://yourcompany.atlassian.net/rest/api/2/field \
     | python -m json.tool | grep -A2 "Story Points"
   ```

2. **Via Issue JSON:**
   - Open any issue in the browser
   - Append `.json` to the URL (Server) or use the REST API
   - Search the `fields` object for the value you expect

3. **Via Jira Admin:**
   - Navigate to **Jira Administration → Issues → Custom Fields**
   - Find the field and note its ID from the URL

### Extra Field Mappings

Use the `field_mappings.extra` dictionary to map arbitrary custom fields:

```json
{
  "field_mappings": {
    "story_points": "customfield_10016",
    "epic_link": "customfield_10014",
    "sprint": "customfield_10020",
    "extra": {
      "team": "customfield_10001",
      "risk_level": "customfield_10050"
    }
  }
}
```

## Status Mapping

The default mapping covers 16 common Jira statuses across three categories:

| Category      | Default Statuses                                                          |
| ------------- | ------------------------------------------------------------------------- |
| **To Do**     | Open, To Do, Backlog, New, Reopened, Created                              |
| **In Progress** | In Progress, In Review, In QA, Code Review, Testing, In Development     |
| **Done**      | Done, Closed, Resolved, Released                                          |

### Custom Mapping

Override or extend the defaults with `status_mapping`:

```json
{
  "status_mapping": {
    "Ready for QA": "In Progress",
    "Awaiting Deploy": "In Progress",
    "Peer Review": "In Progress",
    "Released to Staging": "In Progress",
    "Released to Production": "Done",
    "Won't Do": "Done",
    "Triaged": "To Do"
  }
}
```

Unmapped statuses fall back to Jira's built-in status category.

## Rate Limiting & Resilience

- **Automatic retry** with exponential backoff on HTTP 429, 502, 503, 504
- **Max 3 retries** per request
- **Max 30s backoff** between retries
- **Respects `Retry-After` header** from Jira
- **10s connect timeout** / **60s read timeout**
- **Transient network error recovery** (DNS failures, connection resets)

FlowBoard logs all retries and backoff durations for observability.

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check that your API token is valid and not expired.
   - Ensure `auth_method` matches your server type (`basic` for Cloud, `pat` for Server/DC).
   - For Cloud: verify the email matches the token owner.

2. **403 Forbidden**
   - Check that the account has **Browse Projects** permission.
   - Verify API access is not restricted by your Jira administrator.

3. **No issues returned**
   - Check that project keys match exactly (case-sensitive: `PROJ` not `proj`).
   - Test your JQL in Jira's issue search to verify results.
   - Check that `jql_filter` is not too restrictive.

4. **Missing sprints**
   - Check that `boards` are configured with correct board IDs.
   - Ensure the boards contain the target projects.
   - Auto-discovery only finds Scrum boards.

5. **Missing story points**
   - Check that `field_mappings.story_points` matches your Jira instance.
   - Use the REST API to find the correct custom field ID.

6. **Custom fields not mapped**
   - Add the field to `field_mappings.extra` with its custom field ID.

7. **Status categories wrong**
   - Add custom mappings to `status_mapping` for your workflow statuses.

### Verification

Run the verify command to test connectivity and permissions:

```bash
flowboard verify --config config.json
```

This checks:
- Server reachability
- Authentication validity
- Project accessibility
- Board and sprint access
