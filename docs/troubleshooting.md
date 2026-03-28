# Troubleshooting Guide

Common issues and solutions when using FlowBoard.

## Table of Contents

- [Corporate Network / SSL Issues](#corporate-network--ssl-issues)
- [Jira Connection Issues](#jira-connection-issues)
- [Custom Field Issues](#custom-field-issues)
- [Configuration Issues](#configuration-issues)
- [Dashboard Issues](#dashboard-issues)
- [Performance](#performance)

## Corporate Network / SSL Issues

### SSL certificate errors (`CERTIFICATE_VERIFY_FAILED`)

**Symptom:** FlowBoard fails with `SSL: CERTIFICATE_VERIFY_FAILED` or `requests.exceptions.SSLError` when connecting to Jira.

**Cause:** Corporate proxy (Zscaler, Netskope, etc.) intercepts HTTPS and uses its own CA certificate that Python/requests doesn't trust.

**Fix — find and export your corporate CA bundle:**

<details>
<summary><b>macOS / Linux</b></summary>

```bash
# macOS — export system certificates (includes Zscaler CA)
security find-certificate -a -p \
  /Library/Keychains/System.keychain \
  /System/Library/Keychains/SystemRootCertificates.keychain \
  > ~/combined-ca-bundle.pem

# On Linux, the CA bundle is usually already available:
#   /etc/ssl/certs/ca-certificates.crt          (Debian/Ubuntu)
#   /etc/pki/tls/certs/ca-bundle.crt            (RHEL/Fedora)
# If your proxy adds its own CA, ask your IT department for the .pem file
# and append it: cat corporate-ca.pem >> ~/combined-ca-bundle.pem

# Tell FlowBoard (and requests/pip) to use it (add to ~/.zshrc to persist)
export SSL_CERT_FILE=~/combined-ca-bundle.pem
export REQUESTS_CA_BUNDLE=~/combined-ca-bundle.pem

# Now FlowBoard works
flowboard verify --config flowboard.json
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# 1. Export corporate CA certificate
# Ask your IT department for the corporate CA .pem file, or export it from
# certmgr.msc → Trusted Root Certification Authorities → Certificates
# Right-click → All Tasks → Export → Base-64 encoded X.509 (.CER)
# Save as: %USERPROFILE%\corporate-ca-bundle.pem

# 2. Configure SSL trust (add to your PowerShell profile to persist)
$env:SSL_CERT_FILE = "$env:USERPROFILE\corporate-ca-bundle.pem"
$env:REQUESTS_CA_BUNDLE = "$env:USERPROFILE\corporate-ca-bundle.pem"

# 3. Now FlowBoard works
flowboard verify --config flowboard.json
```

> **Tip:** To make permanent: `[System.Environment]::SetEnvironmentVariable("SSL_CERT_FILE", "$env:USERPROFILE\corporate-ca-bundle.pem", "User")`
</details>

> **How it works:** FlowBoard's SSL resolution order is: `SSL_CERT_FILE` env → `certifi` (bundled with `requests`) → macOS system keychain (automatic) → Python/requests default. In most corporate environments, setting `SSL_CERT_FILE` is the most reliable fix.

### SSL errors during `pip install`

**Symptom:** `pip install -e ".[dev]"` fails with SSL errors.

**Cause:** Same corporate proxy issue — `pip` also needs the CA bundle.

**Fix:** Set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` before running pip (see above).

### Proxy configuration

FlowBoard uses the `requests` library which automatically respects standard proxy environment variables:

```bash
# macOS / Linux
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1,.internal.example.com
```

```powershell
# Windows (PowerShell)
$env:HTTP_PROXY = "http://proxy.example.com:8080"
$env:HTTPS_PROXY = "http://proxy.example.com:8080"
$env:NO_PROXY = "localhost,127.0.0.1,.internal.example.com"
```

No additional FlowBoard configuration is needed — `requests` picks up these env vars automatically.

## Jira Connection Issues

### 401 Unauthorized

**Symptom:** "Authentication failed" error during generate or verify.

**Causes:**
- Invalid or expired API token
- Wrong `auth_method` for your Jira type (use `basic` for Cloud, `pat` for Server/DC)
- Email doesn't match the token owner (Cloud only)

**Solution:**
1. Regenerate your API token:
   - **Cloud:** <https://id.atlassian.com/manage-profile/security/api-tokens>
   - **Server/DC:** Profile → Personal Access Tokens
2. Update your config file or environment variables.
3. Verify with `flowboard verify --config config.json`.

### 403 Forbidden

**Symptom:** Connection succeeds but no data returned, or explicit 403 error.

**Causes:**
- Account lacks **Browse Projects** permission on target projects
- API access restricted by Jira admin (IP allowlist, API token restrictions)

**Solution:**
- Contact your Jira administrator to grant the necessary permissions.
- Ensure API access is enabled for your account type.

### No Issues Returned

**Symptom:** Dashboard generates but shows empty tables and zero counts.

**Causes:**
- Wrong project keys — keys are case-sensitive (`PROJ` not `proj`)
- `jql_filter` is too restrictive
- Issues are outside the configured date range
- Project exists but has no issues matching the query

**Solution:**
1. Run `flowboard verify --config config.json` to test connectivity.
2. Copy the generated JQL and test it directly in Jira's issue search.
3. Check that project keys in your config match exactly.

### Missing Sprint Data

**Symptom:** Sprint Health tab shows empty or sprints are missing.

**Causes:**
- No `boards` configured and auto-discovery found no matching boards
- Board IDs don't match the configured projects
- Boards are Kanban type (sprints require Scrum boards)

**Solution:**
1. Find your board IDs in Jira (the number in the board URL: `/board/123`).
2. Specify board IDs explicitly in `jira.boards`:

```json
{
  "jira": {
    "boards": [123, 456]
  }
}
```

### Connection Timeout

**Symptom:** "Connection timed out" or "Read timed out" errors.

**Causes:**
- Jira server is slow or under heavy load
- Network issues between FlowBoard and Jira
- Large dataset causing slow API responses

**Solution:**
- FlowBoard automatically retries with exponential backoff on transient errors.
- Check network connectivity to your Jira instance.
- Consider narrowing your query with `jql_filter` to reduce data volume.

## Custom Field Issues

### Story Points Not Showing

**Symptom:** All story points show as 0 or are missing.

**Cause:** Your Jira instance uses a different custom field ID for story points than the default (`customfield_10016`).

**Solution:**

1. Find your story points field ID:

   ```bash
   curl -u user@company.com:API_TOKEN \
     https://yourcompany.atlassian.net/rest/api/2/field \
     | python -m json.tool | grep -B2 -A2 "Story Points"
   ```

2. Update your config:

   ```json
   {
     "field_mappings": {
       "story_points": "customfield_10028"
     }
   }
   ```

### Status Categories Wrong

**Symptom:** Issues show wrong status category (e.g., "Done" items appear as "In Progress").

**Cause:** Your Jira instance uses custom workflow status names that are not in the default mapping.

**Solution:** Add custom mappings in `status_mapping`:

```json
{
  "status_mapping": {
    "Ready for QA": "In Progress",
    "Awaiting Deploy": "In Progress",
    "Peer Review": "In Progress",
    "Released": "Done",
    "Won't Do": "Done",
    "Triaged": "To Do"
  }
}
```

### Epic Link Field Not Found

**Symptom:** Issues are not grouped by epic or epic names are missing.

**Cause:** Different Jira instances use different field IDs for the epic link.

**Solution:**

1. Check your epic link field ID via the REST API or issue JSON.
2. Update `field_mappings.epic_link` in your config.

## Configuration Issues

### Schema Validation Errors

**Symptom:** `validate-config` reports one or more errors.

**Common causes and fixes:**

| Error                          | Cause                                  | Fix                                    |
| ------------------------------ | -------------------------------------- | -------------------------------------- |
| Additional properties          | Unknown key in config                  | Remove the unrecognized key            |
| Type error                     | Wrong value type (e.g., string vs int) | Check schema for expected type         |
| Enum validation failed         | Invalid enum value                     | Use one of the allowed values          |
| Format validation failed       | Invalid URL, color, or date format     | Fix the format (e.g., `#FF6B35`)      |
| Minimum value violation        | Number below allowed minimum           | Use a value ≥ the minimum (usually 1) |

### Import Fails

**Symptom:** "Invalid JSON" toast when importing config in the dashboard.

**Cause:** File is not valid JSON or is not a JSON object (arrays, strings, numbers, and `null` are rejected).

**Solution:**
1. Validate your JSON with a linter (e.g., `python -m json.tool config.json`).
2. Ensure the file contains a JSON object `{...}`, not an array or primitive.

### Environment Variables Not Working

**Symptom:** Config values are not being overridden by environment variables.

**Cause:** Wrong variable name or variable not exported.

**Solution:**
- Use the exact names: `FLOWBOARD_JIRA_TOKEN`, `FLOWBOARD_JIRA_EMAIL`, `FLOWBOARD_JIRA_URL`
- Ensure variables are exported: `export FLOWBOARD_JIRA_TOKEN=your-token`

## Dashboard Issues

### Charts Not Loading

**Symptom:** "Chart unavailable" message instead of charts.

**Cause:** Chart.js CDN failed to load — typically due to network restrictions, firewall, or Content Security Policy (CSP).

**Solution:**
- Ensure network access to `cdn.jsdelivr.net`.
- If behind a corporate firewall, whitelist the CDN domain.
- Check browser console for CSP errors.

### Timeline Empty

**Symptom:** Timeline tab shows no bars.

**Cause:** Issues lack start/end dates or sprint dates needed for timeline rendering.

**Solution:**
- Ensure issues have due dates set in Jira.
- Or ensure issues are assigned to sprints with start/end dates.
- Check that the timeline mode matches your data (e.g., "team" mode requires team assignments).

### Theme Not Persisting

**Symptom:** Theme resets on page reload.

**Cause:** `localStorage` is blocked or cleared.

**Solution:**
- Ensure the browser allows `localStorage` for file:// protocol.
- Try opening the dashboard via a local HTTP server instead.

### Tabs Missing

**Symptom:** Some tabs are not visible in the dashboard.

**Cause:** Tabs are toggled off in settings or config.

**Solution:**
- Open the Settings drawer → Layout & Tabs.
- Enable the missing tabs.

## Performance

### Large Datasets

- Default pagination: 100 issues per page, up to 50,000 issues total
- Dashboard rendering scales well to 1,000+ issues
- Timeline performance depends on the number of visible bars
- Consider `jql_filter` to scope data if performance is slow:

```json
{
  "jira": {
    "jql_filter": "updated >= -90d"
  }
}
```

### File Size

- Output HTML is self-contained (typically 200–400 KB)
- Grows with issue count (data embedded as inline JSON)
- Very large datasets (5,000+ issues) may produce files over 1 MB
- Browser performance remains acceptable for most datasets

### Slow Generation

- Generation time is dominated by Jira API calls
- Each API page (100 issues) requires one HTTP request
- Sprint and board discovery adds additional requests
- Use `jql_filter` or limit `projects` to reduce the number of API calls

---

## Frequently Asked Questions

### Why is my team showing zero members?

Your `config.json` team members must match Jira display names or account IDs exactly. Run `flowboard verify` to check connectivity, then look at issue assignees in the API response to find the exact names.

### How do I limit the dashboard to a single sprint?

Add a JQL filter to your config:

```json
{
  "jira": {
    "jql_filter": "sprint = 'Sprint 42'"
  }
}
```

### How do I scope to recent issues only?

```json
{
  "jira": {
    "jql_filter": "updated >= -30d"
  }
}
```

### Can I run FlowBoard without a Jira connection?

Yes — use `flowboard demo` to generate a dashboard with sample data, or `flowboard serve` and click "Try Demo" in the wizard.

### How do I change the dashboard language?

Set `"locale": "pl"` in config.json, or pass `--locale pl` to the CLI. Supported: `en`, `pl`.

### Why are story points all zero?

The field mapping is incorrect. See [Field Mapping Guide](field-mapping.md) to find your instance's custom field ID for story points.

### How do I deploy with Docker?

```bash
# Build
docker build -t flowboard .

# Run (mount your config + set env vars)
docker run -p 8084:8084 \
  -v ./config.json:/app/config.json:ro \
  -e FLOWBOARD_JIRA_TOKEN=your-token \
  -e FLOWBOARD_JIRA_EMAIL=your@email.com \
  flowboard
```

### How do I set up automated dashboard generation?

Use `flowboard schedule` with a cron expression, or add a GitHub Actions workflow — see `.github/workflows/ci.yml` for an example.

### The dashboard is too large / slow in the browser

Reduce the dataset with `jql_filter` or limit `projects` in config. For 5000+ issues, consider splitting into multiple dashboards per team.

### How do I export data programmatically?

When running in server mode (`flowboard serve`), use the API endpoints:
- `GET /api/export/csv` — CSV format
- `GET /api/export/json` — JSON format
- `GET /api/export/html` — Standalone HTML file
