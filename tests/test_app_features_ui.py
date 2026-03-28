"""Application UI feature tests — tables, print CSS, WCAG, color blind palettes, lazy charts, clipboard, CI, docs."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

_CSRF = {"X-Requested-With": "FlowBoard"}


# ===========================================================================
# Helpers
# ===========================================================================

_TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "flowboard"
    / "presentation"
    / "html"
    / "templates"
)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


# ===========================================================================
# Dockerfile
# ===========================================================================


class TestXLSXExport:
    """Test XLSX export endpoint (falls back to CSV)."""

    def test_export_no_data(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/export/xlsx")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 400

    def test_export_csv_fallback(self):
        """With mock snapshot, export should work as CSV (openpyxl not installed)."""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        # Create mock snapshot
        issue = MagicMock()
        issue.key = "TEST-1"
        issue.summary = "Test issue"
        issue.status = MagicMock(value="To Do")
        issue.priority = MagicMock(value="High")
        issue.assignee = "alice"
        issue.epic_name = "Epic 1"
        issue.story_points = 5
        issue.sprint_name = "Sprint 1"

        snapshot = MagicMock()
        snapshot.issues = [issue]
        app.state._flowboard_state._last_snapshot = snapshot

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/export/xlsx")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 200
        # Should be CSV fallback (openpyxl likely not installed)
        content_type = resp.headers.get("content-type", "")
        assert "csv" in content_type or "spreadsheet" in content_type

        if "csv" in content_type:
            reader = csv.reader(io.StringIO(resp.text))
            rows = list(reader)
            assert rows[0][0] == "Key"
            assert rows[1][0] == "TEST-1"


# ===========================================================================
# Schedule Command (CLI)
# ===========================================================================


class TestScheduleCommand:
    """Test the schedule CLI command structure."""

    def test_schedule_command_exists(self):
        from typer.testing import CliRunner

        from flowboard.cli.main import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["schedule", "--help"])
        assert result.exit_code == 0
        assert "schedule" in result.output.lower() or "interval" in result.output.lower()


# ===========================================================================
# Webhook Notifications
# ===========================================================================


class TestWebhookNotifications:
    """Test _send_webhook helper."""

    def test_slack_format(self):
        from flowboard.cli.main import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_resp

        with patch.dict("sys.modules", {"requests": mock_requests}):
            _send_webhook("https://hooks.slack.com/services/xxx", "Test message")

            mock_requests.post.assert_called_once()
            call_args = mock_requests.post.call_args
            payload = call_args[1].get("json") or call_args[0][1]
            assert "text" in payload
            assert "✅" in payload["text"]

    def test_teams_format(self):
        from flowboard.cli.main import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_resp

        with patch.dict("sys.modules", {"requests": mock_requests}):
            _send_webhook("https://webhook.office.com/xx", "Error!", error=True)

            call_args = mock_requests.post.call_args
            payload = call_args[1].get("json") or call_args[0][1]
            assert "@type" in payload
            assert "🔴" in payload["text"]


# ===========================================================================
# Improvements #4, #5, #28 — Table Features (Search, Sort, Pagination)
# ===========================================================================


class TestTableFeatures:
    """Verify table engine is present in templates."""

    def test_filter_issues_function(self):
        content = _read_template("_scripts_core.html")
        assert "function filterIssues()" in content

    def test_table_sort_engine(self):
        content = _read_template("_scripts_features.html")
        assert "data-sort-type" in content
        assert "sortRows" in content

    def test_pagination_controls(self):
        content = _read_template("_scripts_features.html")
        assert "PAGE_SIZES" in content
        assert "fb-table-controls" in content

    def test_table_container_class(self):
        content = _read_template("_scripts_features.html")
        assert "fb-table-container" in content


# ===========================================================================
# Enhanced Print CSS
# ===========================================================================


class TestPrintCSS:
    """Verify print stylesheet in templates."""

    def test_print_media_query(self):
        content = _read_template("_styles_features.html")
        assert "@media print" in content

    def test_print_hides_controls(self):
        content = _read_template("_styles_features.html")
        # Check that navigation/settings are hidden in print
        assert "tab-nav" in content
        assert "display: none" in content

    def test_print_shows_link_urls(self):
        """Print should show URLs after links."""
        content = _read_template("_styles_features.html")
        assert 'content: " (" attr(href) ")"' in content

    def test_print_page_break_control(self):
        content = _read_template("_styles_features.html")
        assert "page-break-inside: avoid" in content or "break-inside: avoid" in content


# ===========================================================================
# WCAG Improvements
# ===========================================================================


class TestWCAG:
    """Verify WCAG/accessibility features."""

    def test_focus_visible_styles(self):
        content = _read_template("_styles_features.html")
        assert "focus-visible" in content

    def test_skip_link_styles(self):
        """Skip-link is defined in _styles_base.html (single canonical definition)."""
        content = _read_template("_styles_base.html")
        assert "skip-link" in content

    def test_aria_tab_role(self):
        content = _read_template("_styles_features.html")
        assert '[role="tab"]' in content


# ===========================================================================
# Color-blind Palette
# ===========================================================================


class TestColorBlindPalette:
    """Verify color-blind friendly palette."""

    def test_css_palette(self):
        content = _read_template("_styles_features.html")
        assert "[data-color-blind" in content
        assert "#0077BB" in content  # Blue
        assert "#EE7733" in content  # Orange

    def test_js_palette(self):
        content = _read_template("_scripts_features.html")
        assert "_cbPalette" in content
        assert "colorBlind" in content


# ===========================================================================
# Lazy Chart.js Loading
# ===========================================================================


class TestLazyCharts:
    """Verify lazy chart initialization."""

    def test_intersection_observer(self):
        content = _read_template("_scripts_features.html")
        assert "IntersectionObserver" in content

    def test_chart_container_observed(self):
        content = _read_template("_scripts_features.html")
        assert "chart-card" in content
        assert "observer.observe" in content


# ===========================================================================
# Copy to Clipboard
# ===========================================================================


class TestCopyToClipboard:
    """Verify copy-to-clipboard functionality."""

    def test_copy_function(self):
        content = _read_template("_scripts_features.html")
        assert "function copyToClipboard" in content
        assert "navigator.clipboard" in content

    def test_fallback_copy(self):
        content = _read_template("_scripts_features.html")
        assert "execCommand" in content

    def test_copy_button_styles(self):
        content = _read_template("_styles_features.html")
        assert ".copy-btn" in content
        assert ".copied" in content


# ===========================================================================
# GitHub Actions CI
# ===========================================================================


class TestCIWorkflow:
    """Verify CI workflow configuration."""

    def test_ci_file_exists(self):
        assert (_REPO_ROOT / ".github" / "workflows" / "ci.yml").exists()

    def test_ci_has_test_job(self):
        content = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "pytest" in content

    def test_ci_has_docker_job(self):
        content = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        assert "docker" in content.lower()


# ===========================================================================
# FAQ / Troubleshooting
# ===========================================================================


class TestDocumentation:
    """Verify documentation improvements."""

    def test_troubleshooting_faq(self):
        content = (_REPO_ROOT / "docs" / "troubleshooting.md").read_text()
        assert "Frequently Asked Questions" in content or "FAQ" in content

    def test_changelog_exists(self):
        assert (_REPO_ROOT / "CHANGELOG.md").exists()
        content = (_REPO_ROOT / "CHANGELOG.md").read_text()
        assert "[1.0.0]" in content

    def test_field_mapping_guide(self):
        assert (_REPO_ROOT / "docs" / "field-mapping.md").exists()


# ===========================================================================
# Config Schema Validation
# ===========================================================================


class TestConfigSchema:
    """Verify config.schema.json is valid and complete."""

    def test_schema_valid_json(self):
        data = json.loads((_REPO_ROOT / "config.schema.json").read_text())
        assert "$schema" in data or "type" in data

    def test_team_thresholds_in_schema(self):
        data = json.loads((_REPO_ROOT / "config.schema.json").read_text())
        team_props = data["properties"]["teams"]["items"]["properties"]
        assert "thresholds" in team_props
        assert team_props["thresholds"]["type"] == "object"


# ===========================================================================
# Integration: End-to-end API health
# ===========================================================================


class TestAPIIntegration:
    """Integration tests across multiple improvement endpoints."""

    def test_health_with_correlation_id(self):
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/health/live", headers={"X-Request-ID": "integration-test"})
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "integration-test"

    def test_webhook_then_events(self):
        """Send a webhook, then verify it appears in events."""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                # Send webhook
                await ac.post(
                    "/api/webhooks/jira",
                    json={
                        "webhookEvent": "jira:issue_created",
                        "issue": {"key": "INT-1"},
                    },
                    headers=_CSRF,
                )
                # Fetch events
                r = await ac.get("/api/webhooks/jira/events")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())
        data = resp.json()
        assert data["count"] >= 1
        assert any(e["issue_key"] == "INT-1" for e in data["events"])
