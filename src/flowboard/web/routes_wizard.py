"""Wizard API routes for guided FlowBoard configuration setup.

Provides endpoints for Jira connection testing, project/board discovery,
field auto-detection, and server-side config persistence.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from flowboard.web.logging import get_logger

_log = get_logger("wizard")

router = APIRouter(prefix="/api/wizard", tags=["wizard"])

_JIRA_TIMEOUT = 15  # seconds for all external Jira API calls


def _get_state(request: Request):
    """Retrieve AppState from the app instance."""
    return request.app.state._flowboard_state


def _get_first_run(request: Request) -> bool:
    return getattr(request.app.state, "_flowboard_first_run", False)


def _error_response(
    error: str, *, status_code: int = 400, error_type: str = "validation_error"
) -> JSONResponse:
    """Standardized error response (Fix #13)."""
    return JSONResponse(
        {"ok": False, "error": error, "error_type": error_type},
        status_code=status_code,
    )


def _validate_content_type(request: Request) -> JSONResponse | None:
    """Reject non-JSON content types (Fix #14)."""
    ct = request.headers.get("content-type", "")
    if "application/json" not in ct:
        return _error_response(
            "Content-Type must be application/json.", error_type="invalid_content_type"
        )
    return None


def _validate_url(url: str) -> str | None:
    """Validate Jira URL format. Returns error message or None."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return "Invalid URL format."
    if parsed.scheme not in ("http", "https"):
        return "URL must start with http:// or https://."
    if not parsed.hostname:
        return "URL must include a hostname."
    return None


def _make_jira_config(
    base_url: str,
    auth_email: str,
    auth_token: str,
    *,
    server_type: str = "cloud",
    max_results: int = 1,
):
    """Build a temporary JiraConfig for wizard operations."""
    from flowboard.infrastructure.config.loader import JiraConfig

    return JiraConfig(
        base_url=base_url,
        auth_token=auth_token,
        auth_email=auth_email,
        server_type=server_type,
        auth_method="basic" if auth_email else "pat",
        api_version="2",
        projects=[],
        boards=[],
        max_results=max_results,
        jql_filter="",
    )


def _extract_jira_params(body: dict) -> tuple[str, str, str, JSONResponse | None]:
    """Extract and validate common Jira params from request body."""
    base_url = (body.get("base_url") or "").strip().rstrip("/")
    if not base_url:
        return "", "", "", _error_response("base_url is required.")
    url_err = _validate_url(base_url)
    if url_err:
        return "", "", "", _error_response(url_err, error_type="invalid_url")
    auth_email = (body.get("auth_email") or "").strip()
    auth_token = (body.get("auth_token") or "").strip()
    return base_url, auth_email, auth_token, None


# ---------------------------------------------------------------------------
# Verify Jira connection
# ---------------------------------------------------------------------------


@router.post("/verify")
async def wizard_verify(request: Request) -> JSONResponse:
    """Test Jira connectivity with provided credentials."""
    import asyncio

    ct_err = _validate_content_type(request)
    if ct_err:
        return ct_err

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error_response("Invalid JSON body.", error_type="parse_error")

    base_url, auth_email, auth_token, err = _extract_jira_params(body)
    if err:
        return err

    def _test_connection():
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = _make_jira_config(base_url, auth_email, auth_token)
        with JiraClient(cfg) as client:
            client.session.timeout = _JIRA_TIMEOUT
            info = client._get_json(f"{base_url}/rest/api/2/serverInfo")
            # Fix #5: detect Cloud vs Server from deploymentType
            deployment = info.get("deploymentType", "").capitalize() or "Unknown"
            return {
                "server_title": info.get("serverTitle", ""),
                "version": info.get("version", ""),
                "base_url": info.get("baseUrl", base_url),
                "deployment_type": deployment,
                "server_type": "server" if deployment.lower() == "server" else "cloud",
            }

    try:
        info = await asyncio.to_thread(_test_connection)
        return JSONResponse({"ok": True, "info": info})
    except Exception as exc:
        _log.warning("Wizard verify failed: %s", type(exc).__name__)
        error_msg = str(exc)
        if "401" in error_msg or "403" in error_msg:
            return _error_response(
                "Authentication failed. Check your email and API token.",
                error_type="auth_error",
            )
        elif "ConnectionError" in error_msg or "resolve" in error_msg.lower():
            return _error_response(
                "Cannot connect to the Jira URL. Check the URL and network.",
                error_type="connection_error",
            )
        elif "Timeout" in error_msg or "timed out" in error_msg.lower():
            return _error_response(
                "Connection timed out. The Jira server may be slow or unreachable.",
                error_type="timeout_error",
            )
        return _error_response(error_msg, error_type="unknown_error")


# ---------------------------------------------------------------------------
# Discover projects from Jira (Fix #19: pagination support)
# ---------------------------------------------------------------------------


@router.post("/projects")
async def wizard_projects(request: Request) -> JSONResponse:
    """Fetch available projects from verified Jira connection."""
    import asyncio

    ct_err = _validate_content_type(request)
    if ct_err:
        return ct_err

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error_response("Invalid JSON body.", error_type="parse_error")

    base_url, auth_email, auth_token, err = _extract_jira_params(body)
    if err:
        return err

    offset = max(0, int(body.get("offset", 0)))
    limit = min(100, max(1, int(body.get("limit", 50))))

    def _fetch_projects():
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = _make_jira_config(base_url, auth_email, auth_token, max_results=limit)
        with JiraClient(cfg) as client:
            client.session.timeout = _JIRA_TIMEOUT
            data = client._get_json(
                f"{base_url}/rest/api/2/project",
                params={"startAt": offset, "maxResults": limit},
            )
            projects = []
            for p in data if isinstance(data, list) else []:
                projects.append(
                    {
                        "key": p.get("key", ""),
                        "name": p.get("name", ""),
                        "lead": p.get("lead", {}).get("displayName", ""),
                        "style": p.get("style", ""),
                    }
                )
            return projects

    try:
        projects = await asyncio.to_thread(_fetch_projects)
        return JSONResponse(
            {
                "ok": True,
                "projects": projects,
                "offset": offset,
                "limit": limit,
                "has_more": len(projects) == limit,
            }
        )
    except Exception as exc:
        _log.warning("Project fetch failed: %s", type(exc).__name__)
        return _error_response("Failed to fetch projects.", error_type="fetch_error")


# ---------------------------------------------------------------------------
# Discover boards
# ---------------------------------------------------------------------------


@router.post("/boards")
async def wizard_boards(request: Request) -> JSONResponse:
    """Fetch available boards from verified Jira connection."""
    import asyncio

    ct_err = _validate_content_type(request)
    if ct_err:
        return ct_err

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error_response("Invalid JSON body.", error_type="parse_error")

    base_url, auth_email, auth_token, err = _extract_jira_params(body)
    if err:
        return err

    def _fetch_boards():
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = _make_jira_config(base_url, auth_email, auth_token, max_results=50)
        with JiraClient(cfg) as client:
            client.session.timeout = _JIRA_TIMEOUT
            boards = client.get_boards()
            return [
                {
                    "id": b.get("id"),
                    "name": b.get("name", ""),
                    "type": b.get("type", ""),
                    "project_key": b.get("location", {}).get("projectKey", ""),
                }
                for b in boards
                if b.get("id") is not None
            ][:50]

    try:
        boards = await asyncio.to_thread(_fetch_boards)
        return JSONResponse({"ok": True, "boards": boards})
    except Exception as exc:
        _log.warning("Board fetch failed: %s", type(exc).__name__)
        return _error_response("Failed to fetch boards.", error_type="fetch_error")


# ---------------------------------------------------------------------------
# Auto-detect field mappings
# ---------------------------------------------------------------------------


@router.post("/fields")
async def wizard_fields(request: Request) -> JSONResponse:
    """Auto-detect custom field IDs for story points, epic link, sprint."""
    import asyncio

    ct_err = _validate_content_type(request)
    if ct_err:
        return ct_err

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error_response("Invalid JSON body.", error_type="parse_error")

    base_url, auth_email, auth_token, err = _extract_jira_params(body)
    if err:
        return err

    field_hints = {
        "story_points": ["story points", "story point", "story_points", "storypoints", "sp"],
        "epic_link": ["epic link", "epic_link", "epic"],
        "sprint": ["sprint"],
    }

    def _detect_fields():
        from flowboard.infrastructure.jira.client import JiraClient

        cfg = _make_jira_config(base_url, auth_email, auth_token)
        with JiraClient(cfg) as client:
            client.session.timeout = _JIRA_TIMEOUT
            fields = client._get_json(f"{base_url}/rest/api/2/field")

        detected: dict[str, dict[str, str]] = {}
        for target, hints in field_hints.items():
            for f in fields if isinstance(fields, list) else []:
                name = (f.get("name") or "").lower()
                fid = f.get("id", "")
                if any(h in name for h in hints) and fid.startswith("customfield_"):
                    detected[target] = {"id": fid, "name": f.get("name", "")}
                    break
        return detected

    try:
        detected = await asyncio.to_thread(_detect_fields)
        return JSONResponse({"ok": True, "fields": detected})
    except Exception as exc:
        _log.warning("Field detection failed: %s", type(exc).__name__)
        return _error_response("Failed to detect fields.", error_type="fetch_error")


# ---------------------------------------------------------------------------
# Save config to disk
# ---------------------------------------------------------------------------


@router.post("/save")
async def wizard_save(request: Request) -> JSONResponse:
    """Validate and write configuration to disk."""
    state = _get_state(request)

    ct_err = _validate_content_type(request)
    if ct_err:
        return ct_err

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error_response("Invalid JSON body.", error_type="parse_error")

    config_data = body.get("config")
    if not isinstance(config_data, dict):
        return _error_response("config must be a JSON object.")

    # Validate
    try:
        from flowboard.infrastructure.config.validator import validate_config_dict

        validate_config_dict(config_data)
    except Exception as exc:
        return _error_response(f"Validation failed: {exc}", error_type="schema_error")

    # Determine save path
    save_path = Path(body.get("path", "config.json"))
    if save_path.is_absolute():
        return _error_response("Config path must be relative.", error_type="path_error")

    # Security: ensure within CWD
    resolved = (Path.cwd() / save_path).resolve()
    try:
        resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        return _error_response("Path traversal not allowed.", error_type="path_error")

    # Strip credentials before saving (use env vars instead)
    jira = config_data.get("jira", {})
    creds_found = []
    for key in ("auth_token", "pat", "password"):
        if jira.get(key):
            creds_found.append(key)
            del jira[key]

    # Atomic write: .tmp → rename
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(resolved.parent), suffix=".tmp", prefix=".flowboard_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp_path, str(resolved))
            with contextlib.suppress(OSError):
                os.chmod(str(resolved), 0o600)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
    except OSError:
        _log.exception("Config save failed")
        return _error_response(
            "Failed to save config file.", status_code=500, error_type="io_error"
        )

    # Update app state
    state.config_path = resolved

    warning = ""
    if creds_found:
        warning = (
            f"Credentials ({', '.join(creds_found)}) were removed from the saved file. "
            "Set FLOWBOARD_JIRA_TOKEN and FLOWBOARD_JIRA_EMAIL environment variables instead."
        )

    _log.info("Config saved to %s", resolved)
    return JSONResponse(
        {
            "ok": True,
            "path": str(save_path),
            "warning": warning,
        }
    )


# ---------------------------------------------------------------------------
# Get current config (Fix #12)
# ---------------------------------------------------------------------------


@router.get("/config")
async def wizard_get_config(request: Request) -> JSONResponse:
    """Return the current config file contents, or null if none exists."""
    state = _get_state(request)
    first_run = _get_first_run(request)
    config_path = getattr(state, "config_path", None)
    if not config_path:
        # In first_run mode (no config_path set), only probe CWD if not explicitly first_run
        if not first_run:
            default = Path.cwd() / "config.json"
            if default.exists():
                config_path = default
        if not config_path:
            return JSONResponse({"ok": True, "config": None, "exists": False})

    try:
        with open(config_path, encoding="utf-8") as f:
            config_data = json.load(f)
        # Strip credentials from response
        jira = config_data.get("jira", {})
        for key in ("auth_token", "pat", "password"):
            if key in jira:
                jira[key] = "***"
        return JSONResponse(
            {
                "ok": True,
                "config": config_data,
                "exists": True,
                "path": str(config_path),
            }
        )
    except FileNotFoundError:
        return JSONResponse({"ok": True, "config": None, "exists": False})
    except Exception as exc:
        _log.warning("Failed to read config: %s", type(exc).__name__)
        return _error_response("Failed to read config file.", error_type="io_error")


# ---------------------------------------------------------------------------
# Import pasted JSON config
# ---------------------------------------------------------------------------


@router.post("/import")
async def wizard_import(request: Request) -> JSONResponse:
    """Validate pasted JSON and save as config file."""
    ct_err = _validate_content_type(request)
    if ct_err:
        return ct_err

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return _error_response("Invalid JSON body.", error_type="parse_error")

    raw_json = body.get("json_str", "")
    if not raw_json:
        return _error_response("json_str is required.")

    try:
        config_data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return _error_response(f"Invalid JSON: {exc}", error_type="parse_error")

    if not isinstance(config_data, dict) or "jira" not in config_data:
        return _error_response('Config must have a "jira" key.', error_type="schema_error")

    # Validate against schema
    try:
        from flowboard.infrastructure.config.validator import validate_config_dict

        validate_config_dict(config_data)
    except Exception as exc:
        return _error_response(f"Validation failed: {exc}", error_type="schema_error")

    # Delegate to save endpoint by constructing a clean inner body
    request._body = json.dumps({"config": config_data, "path": "config.json"}).encode()
    # Clear cached JSON so wizard_save re-parses from _body
    if hasattr(request, "_json"):
        del request._json
    return await wizard_save(request)
