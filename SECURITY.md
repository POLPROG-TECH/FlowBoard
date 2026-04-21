# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | ✅ Current release |

## Reporting a Vulnerability

If you discover a security vulnerability in FlowBoard, please report it responsibly.

**Do not open a public issue.**

Instead, please email **contact@polprog.pl** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge your report within **48 hours** and aim to provide a fix or mitigation within **7 days** for critical issues.

## Scope

Security concerns relevant to FlowBoard include:

- **Credential handling** - leakage of Jira tokens, PATs, or session cookies in logs, HTML output, or error pages
- **Output safety** - XSS or HTML injection in rendered dashboards or wizard pages
- **CSRF attacks** - bypassing the double-submit cookie protection in the web/wizard routes
- **Path traversal** in config file resolution, output paths, or artifact serving
- **JQL injection** via the wizard or CLI into Jira API calls
- **Sensitive data leakage** - internal paths, tokens, or config values exposed in UI or logs
- **Dependency vulnerabilities** in third-party packages

## Disclosure Policy

We follow coordinated disclosure:

1. Report the issue privately via the contact above.
2. We confirm receipt and begin investigation.
3. Once a fix is released, we publicly acknowledge the reporter (with their consent).
