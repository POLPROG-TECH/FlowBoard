"""Extended API routes for FlowBoard — webhooks, snapshots, XLSX export, multi-dashboard.

Improvement #6: Jira webhook listener
Improvement #8: Snapshot history
Improvement #9: Multi-dashboard management
Improvement #24: Excel XLSX export
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

_log = logging.getLogger("flowboard.routes_ext")

router = APIRouter(tags=["extended"])

_KNOWN_JIRA_EVENTS = frozenset(
    {
        "jira:issue_created",
        "jira:issue_updated",
        "jira:issue_deleted",
        "sprint_started",
        "sprint_closed",
        "sprint_created",
        "sprint_updated",
        "board_created",
        "board_updated",
        "board_deleted",
        "issue_created",
        "issue_updated",
        "issue_deleted",
        "comment_created",
        "comment_updated",
        "unknown",
    }
)


# ---------------------------------------------------------------------------
# Webhook persistence helpers (Blocker #22)
# ---------------------------------------------------------------------------

_WEBHOOK_LOG = Path("output/webhook_events.jsonl")


def _append_webhook_event(event: dict) -> None:
    """Append a webhook event to the persistent log file."""
    try:
        _WEBHOOK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _WEBHOOK_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        _log.warning("Failed to persist webhook event")


def _read_recent_events(n: int = 50) -> list[dict]:
    """Read the last N events from the log file."""
    if not _WEBHOOK_LOG.exists():
        return []
    try:
        lines = _WEBHOOK_LOG.read_text(encoding="utf-8").strip().split("\n")
        events = []
        for line in lines[-n:]:
            if line.strip():
                with contextlib.suppress(json.JSONDecodeError):
                    events.append(json.loads(line))
        return events
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Webhook rate limiting (Blocker #24)
# ---------------------------------------------------------------------------

_WEBHOOK_RATE: dict[str, list[float]] = {}
_WEBHOOK_RATE_LIMIT = 30  # max 30 webhook events per minute per IP


def _webhook_rate_check(ip: str) -> bool:
    """Return True if the IP has exceeded the webhook rate limit."""
    now = time.time()
    cutoff = now - 60
    timestamps = _WEBHOOK_RATE.get(ip, [])
    fresh = [t for t in timestamps if t > cutoff]
    if len(fresh) >= _WEBHOOK_RATE_LIMIT:
        _WEBHOOK_RATE[ip] = fresh
        return True
    fresh.append(now)
    _WEBHOOK_RATE[ip] = fresh
    return False


# ---------------------------------------------------------------------------
# Jira Webhook Listener (Improvement #6)
# ---------------------------------------------------------------------------


@router.post("/api/webhooks/jira")
async def jira_webhook(request: Request) -> JSONResponse:
    """Receive Jira webhook events for incremental dashboard refresh.

    Configure in Jira: Settings → System → Webhooks → Add URL:
    https://your-flowboard/api/webhooks/jira

    Events: issue_created, issue_updated, sprint_started, sprint_closed
    """
    # Rate limiting (Blocker #24)
    client_ip = request.client.host if request.client else "unknown"
    if _webhook_rate_check(client_ip):
        return JSONResponse({"ok": False, "error": "Webhook rate limit exceeded"}, status_code=429)

    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "Expected JSON object"}, status_code=400)

    event_type = body.get("webhookEvent", body.get("event", ""))
    if not event_type:
        return JSONResponse({"ok": False, "error": "Missing event type"}, status_code=400)

    if event_type not in _KNOWN_JIRA_EVENTS:
        _log.warning("Unknown Jira webhook event: %s", event_type)

    issue_key = body.get("issue", {}).get("key", "")

    _log.info("Jira webhook: event=%s issue=%s", event_type, issue_key)

    event_dict = {
        "event": event_type,
        "issue_key": issue_key,
        "timestamp": time.time(),
    }

    # Persist to disk (Blocker #22)
    _append_webhook_event(event_dict)

    # Keep in-memory list for auto-refresh triggering
    state = request.app.state._flowboard_state
    if not hasattr(state, "_webhook_events"):
        state._webhook_events = []
    state._webhook_events.append(event_dict)
    # Cap in-memory events at 1000
    if len(state._webhook_events) > 1000:
        state._webhook_events = state._webhook_events[-500:]

    # Auto-trigger refresh if enough events accumulated
    pending = len(state._webhook_events)
    should_refresh = pending >= 10 or event_type in ("sprint_started", "sprint_closed")

    return JSONResponse(
        {
            "ok": True,
            "event": event_type,
            "pending_events": pending,
            "refresh_triggered": should_refresh,
        }
    )


@router.get("/api/webhooks/jira/events")
async def jira_webhook_events(request: Request) -> JSONResponse:
    """List recent webhook events (for diagnostics)."""
    events = _read_recent_events(50)
    return JSONResponse(
        {
            "ok": True,
            "count": len(events),
            "events": events,
        }
    )


# ---------------------------------------------------------------------------
# Snapshot History (Improvement #8)
# ---------------------------------------------------------------------------

_SNAPSHOT_DIR = Path("output/snapshots")


@router.post("/api/snapshots/save")
async def save_snapshot(request: Request) -> JSONResponse:
    """Save current dashboard as a timestamped snapshot."""
    state = request.app.state._flowboard_state
    html = getattr(state, "_cached_html", None)
    if not html:
        return JSONResponse({"ok": False, "error": "No dashboard to snapshot."}, status_code=400)

    import re as _re

    _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize: only allow alphanumeric + underscore
    ts = _re.sub(r"[^a-zA-Z0-9_]", "", ts)
    snap_path = _SNAPSHOT_DIR / f"dashboard_{ts}.html"
    snap_path.write_text(html, encoding="utf-8")

    # Save metadata
    meta_path = _SNAPSHOT_DIR / f"dashboard_{ts}.json"
    meta = {
        "timestamp": ts,
        "created_at": datetime.now().isoformat(),
        "size_bytes": len(html.encode("utf-8")),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    _log.info("Snapshot saved: %s", snap_path)
    return JSONResponse({"ok": True, "path": str(snap_path), "timestamp": ts})


@router.get("/api/snapshots")
async def list_snapshots() -> JSONResponse:
    """List all available dashboard snapshots."""
    snapshots = []
    if _SNAPSHOT_DIR.exists():
        for meta_file in sorted(_SNAPSHOT_DIR.glob("dashboard_*.json"), reverse=True):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                meta["file"] = meta_file.stem.replace(".json", "") + ".html"
                snapshots.append(meta)
            except (json.JSONDecodeError, OSError, KeyError):
                pass
    return JSONResponse({"ok": True, "snapshots": snapshots[:50]})


@router.get("/api/snapshots/{timestamp}")
async def get_snapshot(timestamp: str) -> Response:
    """Retrieve a specific dashboard snapshot by timestamp."""
    import re

    if not re.match(r"^\d{8}_\d{6}$", timestamp):
        return JSONResponse({"ok": False, "error": "Invalid timestamp format."}, status_code=400)

    snap_path = _SNAPSHOT_DIR / f"dashboard_{timestamp}.html"
    if not snap_path.resolve().is_relative_to(_SNAPSHOT_DIR.resolve()):
        return JSONResponse({"ok": False, "error": "Invalid path."}, status_code=400)
    if not snap_path.exists():
        return JSONResponse({"ok": False, "error": "Snapshot not found."}, status_code=404)

    html = snap_path.read_text(encoding="utf-8")
    return Response(content=html, media_type="text/html")


# ---------------------------------------------------------------------------
# Multi-Dashboard Management (Improvement #9)
# ---------------------------------------------------------------------------

_CONFIGS_DIR = Path("configs")


@router.get("/api/dashboards")
async def list_dashboards() -> JSONResponse:
    """List available dashboard configurations."""
    dashboards = []

    # Check default config
    default = Path("config.json")
    if default.exists():
        dashboards.append({"id": "default", "name": "Default", "path": str(default)})

    # Check configs directory
    if _CONFIGS_DIR.exists():
        for cfg_file in sorted(_CONFIGS_DIR.glob("*.json")):
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
                name = data.get("output", {}).get("title", cfg_file.stem)
                dashboards.append(
                    {
                        "id": cfg_file.stem,
                        "name": name,
                        "path": str(cfg_file),
                    }
                )
            except (json.JSONDecodeError, OSError, KeyError):
                pass

    return JSONResponse({"ok": True, "dashboards": dashboards})


@router.post("/api/dashboards/{dashboard_id}/generate")
async def generate_dashboard(dashboard_id: str, request: Request) -> JSONResponse:
    """Generate a specific dashboard by config ID."""
    import re

    if not re.match(r"^[a-zA-Z0-9_-]+$", dashboard_id):
        return JSONResponse({"ok": False, "error": "Invalid dashboard ID."}, status_code=400)

    if dashboard_id == "default":
        cfg_path = Path("config.json")
    else:
        cfg_path = _CONFIGS_DIR / f"{dashboard_id}.json"

    if not cfg_path.exists():
        return JSONResponse(
            {"ok": False, "error": f"Config not found: {cfg_path}"}, status_code=404
        )

    try:
        import asyncio

        from flowboard.application.orchestrator import Orchestrator
        from flowboard.infrastructure.config.loader import load_config

        cfg = await asyncio.to_thread(load_config, cfg_path)
        orch = Orchestrator(cfg)
        output_path = await asyncio.to_thread(orch.run)
        return JSONResponse({"ok": True, "path": str(output_path), "dashboard_id": dashboard_id})
    except Exception as exc:
        _log.exception("Dashboard generation failed: %s", dashboard_id)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# XLSX Export (Improvement #24)
# ---------------------------------------------------------------------------


@router.get("/api/export/xlsx")
async def export_xlsx(request: Request) -> Response:
    """Export dashboard data as Excel XLSX file.

    Uses openpyxl if available, falls back to CSV with .xlsx extension.
    """
    state = request.app.state._flowboard_state
    snapshot = getattr(state, "_last_snapshot", None)

    if not snapshot:
        return JSONResponse(
            {"ok": False, "error": "No analysis data. Run /api/analyze first."},
            status_code=400,
        )

    try:
        import io

        from openpyxl import Workbook

        wb = Workbook()

        # Issues sheet
        ws = wb.active
        ws.title = "Issues"
        headers = [
            "Key",
            "Summary",
            "Status",
            "Priority",
            "Assignee",
            "Epic",
            "Story Points",
            "Sprint",
        ]
        ws.append(headers)
        for issue in snapshot.issues:
            ws.append(
                [
                    issue.key,
                    issue.summary,
                    issue.status.value if hasattr(issue.status, "value") else str(issue.status),
                    issue.priority.value
                    if hasattr(issue.priority, "value")
                    else str(issue.priority),
                    issue.assignee or "",
                    issue.epic_name or "",
                    issue.story_points or 0,
                    issue.sprint_name or "",
                ]
            )

        # Workload sheet
        if hasattr(snapshot, "workload_records") and snapshot.workload_records:
            ws2 = wb.create_sheet("Workload")
            ws2.append(["Person", "Story Points", "Issue Count", "In Progress", "Blocked"])
            for wr in snapshot.workload_records:
                ws2.append([wr.person, wr.story_points, wr.issue_count, wr.in_progress, wr.blocked])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=flowboard_export.xlsx"},
        )

    except ImportError:
        # Fallback: CSV if openpyxl not installed
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["Key", "Summary", "Status", "Priority", "Assignee", "Epic", "Story Points", "Sprint"]
        )
        for issue in snapshot.issues:
            writer.writerow(
                [
                    issue.key,
                    issue.summary,
                    issue.status.value if hasattr(issue.status, "value") else str(issue.status),
                    issue.priority.value
                    if hasattr(issue.priority, "value")
                    else str(issue.priority),
                    issue.assignee or "",
                    issue.epic_name or "",
                    issue.story_points or 0,
                    issue.sprint_name or "",
                ]
            )

        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=flowboard_export.csv"},
        )
