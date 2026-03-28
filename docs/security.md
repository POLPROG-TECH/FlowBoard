# Security Guide

## Overview

FlowBoard is an internal tool that accesses Jira via API tokens. This document describes how secrets are handled and protected.

## Authentication Model

FlowBoard supports two authentication modes:

1. **Basic Auth** (Jira Cloud): `email + API token`
2. **Bearer Token** (Jira Data Center): `PAT`

These are configured via environment variables — never hardcoded.

## Secret Handling Rules

### ✅ Do
- Store tokens in environment variables (`FLOWBOARD_JIRA_TOKEN`, `FLOWBOARD_JIRA_EMAIL`)
- Use the example config (`examples/config.example.json`) as a template — it contains only placeholders
- Validate config before running: `flowboard validate-config`

### ❌ Don't
- Commit real tokens in `config.json`
- Share generated HTML dashboards externally (they may contain internal project data)
- Log full API responses in production

## How Secrets Are Protected

### Environment Variables
Config file values for `auth_token` and `auth_email` are overridden by environment variables when set. This allows the config file to be committed without secrets.

### Log Masking
Auth tokens are masked in all log output using `mask_secret()`:
```
Jira auth configured (token=…***k123)
```

### HTML Output
Generated HTML dashboards contain **no authentication data**. This is verified by automated tests.

### Schema Validation
The JSON Schema rejects unknown configuration keys. This prevents accidental inclusion of sensitive data in unexpected fields.

### .gitignore
The default `.gitignore` excludes:
- `config.json` (but not `examples/config.example.json`)
- `.env` files
- Output HTML files

## Recommendations

1. **Use a `.env` file** for local development (not committed):
   ```bash
   # .env
   FLOWBOARD_JIRA_TOKEN=your-token-here
   FLOWBOARD_JIRA_EMAIL=you@company.com
   ```

2. **In CI/CD**, use secret management:
   ```yaml
   env:
     FLOWBOARD_JIRA_TOKEN: ${{ secrets.JIRA_TOKEN }}
     FLOWBOARD_JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
   ```

3. **Rotate tokens** periodically as per your company's security policy.

4. **Use read-only tokens** — FlowBoard only needs read access to Jira.

## Content Security Policy (CSP)

FlowBoard generates self-contained HTML dashboards with **inline styles and scripts**. If you serve the dashboard through a web server with Content Security Policy headers, you need to configure CSP to allow inline content.

### Minimum CSP Requirements

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  connect-src 'none';
  font-src 'self';
```

### Key Points

- **`script-src 'unsafe-inline'`** is required because the dashboard embeds JavaScript directly in the HTML file.
- **`https://cdn.jsdelivr.net`** is required for the Chart.js library loaded from CDN.
- **`style-src 'unsafe-inline'`** is required because all CSS is embedded in the HTML file.
- **`connect-src 'none'`** is safe — the dashboard makes no network requests after loading.

### Nonce-Based CSP (Future)

For stricter CSP policies, a future version of FlowBoard may support nonce-based script/style tags. Until then, `'unsafe-inline'` is required for both scripts and styles.

### Serving Dashboards Locally

When opening the HTML file directly in a browser (`file://` protocol), CSP headers do not apply. This is the most common usage pattern and requires no additional configuration.
