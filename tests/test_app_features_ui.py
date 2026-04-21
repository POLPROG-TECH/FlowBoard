"""Application UI feature tests - tables, print CSS, WCAG, color blind palettes, lazy charts, clipboard, CI, docs."""

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
    """Tests for x l s x export."""

    """GIVEN x l s x export and the scenario: export no data"""
    def test_export_no_data(self):
        """WHEN the code under test is exercised for: export no data"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/api/export/xlsx")
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: export no data"""
        assert resp.status_code == 400

    """GIVEN x l s x export and the scenario: export csv fallback"""
    def test_export_csv_fallback(self):
        """WHEN the code under test is exercised for: export csv fallback"""
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

        """THEN the expected behaviour holds: export csv fallback"""
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
    """Tests for schedule command."""

    """GIVEN schedule command and the scenario: schedule command exists"""
    def test_schedule_command_exists(self):
        """WHEN the code under test is exercised for: schedule command exists"""
        from typer.testing import CliRunner

        from flowboard.cli.main import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["schedule", "--help"])

        """THEN the expected behaviour holds: schedule command exists"""
        assert result.exit_code == 0
        assert "schedule" in result.output.lower() or "interval" in result.output.lower()


# ===========================================================================
# Webhook Notifications
# ===========================================================================


class TestWebhookNotifications:
    """Tests for webhook notifications."""

    """GIVEN webhook notifications and the scenario: slack format"""
    def test_slack_format(self):
        """WHEN the code under test is exercised for: slack format"""
        from flowboard.cli.main import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_resp

        """THEN the expected behaviour holds: slack format"""
        with patch.dict("sys.modules", {"requests": mock_requests}):
            _send_webhook("https://hooks.slack.com/services/xxx", "Test message")

            mock_requests.post.assert_called_once()
            call_args = mock_requests.post.call_args
            payload = call_args[1].get("json") or call_args[0][1]
            assert "text" in payload
            assert "✅" in payload["text"]

    """GIVEN webhook notifications and the scenario: teams format"""
    def test_teams_format(self):
        """WHEN the code under test is exercised for: teams format"""
        from flowboard.cli.main import _send_webhook

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests = MagicMock()
        mock_requests.post.return_value = mock_resp

        """THEN the expected behaviour holds: teams format"""
        with patch.dict("sys.modules", {"requests": mock_requests}):
            _send_webhook("https://webhook.office.com/xx", "Error!", error=True)

            call_args = mock_requests.post.call_args
            payload = call_args[1].get("json") or call_args[0][1]
            assert "@type" in payload
            assert "🔴" in payload["text"]


# ===========================================================================
# Improvements #4, #5, #28 - Table Features (Search, Sort, Pagination)
# ===========================================================================


class TestTableFeatures:
    """Tests for table features."""

    """GIVEN table features and the scenario: filter issues function"""
    def test_filter_issues_function(self):
        """WHEN the code under test is exercised for: filter issues function"""
        content = _read_template("_scripts_core.html")

        """THEN the expected behaviour holds: filter issues function"""
        assert "function filterIssues()" in content

    """GIVEN table features and the scenario: table sort engine"""
    def test_table_sort_engine(self):
        """WHEN the code under test is exercised for: table sort engine"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: table sort engine"""
        assert "data-sort-type" in content
        assert "sortRows" in content

    """GIVEN table features and the scenario: pagination controls"""
    def test_pagination_controls(self):
        """WHEN the code under test is exercised for: pagination controls"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: pagination controls"""
        assert "PAGE_SIZES" in content
        assert "fb-table-controls" in content

    """GIVEN table features and the scenario: table container class"""
    def test_table_container_class(self):
        """WHEN the code under test is exercised for: table container class"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: table container class"""
        assert "fb-table-container" in content


# ===========================================================================
# Enhanced Print CSS
# ===========================================================================


class TestPrintCSS:
    """Tests for print c s s."""

    """GIVEN print c s s and the scenario: print media query"""
    def test_print_media_query(self):
        """WHEN the code under test is exercised for: print media query"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: print media query"""
        assert "@media print" in content

    """GIVEN print c s s and the scenario: print hides controls"""
    def test_print_hides_controls(self):
        """WHEN the code under test is exercised for: print hides controls"""
        content = _read_template("_styles_features.html")
        # Check that navigation/settings are hidden in print

        """THEN the expected behaviour holds: print hides controls"""
        assert "tab-nav" in content
        assert "display: none" in content

    """GIVEN print c s s and the scenario: print shows link urls"""
    def test_print_shows_link_urls(self):
        """WHEN the code under test is exercised for: print shows link urls"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: print shows link urls"""
        assert 'content: " (" attr(href) ")"' in content

    """GIVEN print c s s and the scenario: print page break control"""
    def test_print_page_break_control(self):
        """WHEN the code under test is exercised for: print page break control"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: print page break control"""
        assert "page-break-inside: avoid" in content or "break-inside: avoid" in content


# ===========================================================================
# WCAG Improvements
# ===========================================================================


class TestWCAG:
    """Tests for w c a g."""

    """GIVEN w c a g and the scenario: focus visible styles"""
    def test_focus_visible_styles(self):
        """WHEN the code under test is exercised for: focus visible styles"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: focus visible styles"""
        assert "focus-visible" in content

    """GIVEN w c a g and the scenario: skip link styles"""
    def test_skip_link_styles(self):
        """WHEN the code under test is exercised for: skip link styles"""
        content = _read_template("_styles_base.html")

        """THEN the expected behaviour holds: skip link styles"""
        assert "skip-link" in content

    """GIVEN w c a g and the scenario: aria tab role"""
    def test_aria_tab_role(self):
        """WHEN the code under test is exercised for: aria tab role"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: aria tab role"""
        assert '[role="tab"]' in content


# ===========================================================================
# Color-blind Palette
# ===========================================================================


class TestColorBlindPalette:
    """Tests for color blind palette."""

    """GIVEN color blind palette and the scenario: css palette"""
    def test_css_palette(self):
        """WHEN the code under test is exercised for: css palette"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: css palette"""
        assert "[data-color-blind" in content
        assert "#0077BB" in content  # Blue
        assert "#EE7733" in content  # Orange

    """GIVEN color blind palette and the scenario: js palette"""
    def test_js_palette(self):
        """WHEN the code under test is exercised for: js palette"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: js palette"""
        assert "_cbPalette" in content
        assert "colorBlind" in content


# ===========================================================================
# Lazy Chart.js Loading
# ===========================================================================


class TestLazyCharts:
    """Tests for lazy charts."""

    """GIVEN lazy charts and the scenario: intersection observer"""
    def test_intersection_observer(self):
        """WHEN the code under test is exercised for: intersection observer"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: intersection observer"""
        assert "IntersectionObserver" in content

    """GIVEN lazy charts and the scenario: chart container observed"""
    def test_chart_container_observed(self):
        """WHEN the code under test is exercised for: chart container observed"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: chart container observed"""
        assert "chart-card" in content
        assert "observer.observe" in content


# ===========================================================================
# Copy to Clipboard
# ===========================================================================


class TestCopyToClipboard:
    """Tests for copy to clipboard."""

    """GIVEN copy to clipboard and the scenario: copy function"""
    def test_copy_function(self):
        """WHEN the code under test is exercised for: copy function"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: copy function"""
        assert "function copyToClipboard" in content
        assert "navigator.clipboard" in content

    """GIVEN copy to clipboard and the scenario: fallback copy"""
    def test_fallback_copy(self):
        """WHEN the code under test is exercised for: fallback copy"""
        content = _read_template("_scripts_features.html")

        """THEN the expected behaviour holds: fallback copy"""
        assert "execCommand" in content

    """GIVEN copy to clipboard and the scenario: copy button styles"""
    def test_copy_button_styles(self):
        """WHEN the code under test is exercised for: copy button styles"""
        content = _read_template("_styles_features.html")

        """THEN the expected behaviour holds: copy button styles"""
        assert ".copy-btn" in content
        assert ".copied" in content


# ===========================================================================
# GitHub Actions CI
# ===========================================================================


class TestCIWorkflow:
    """Tests for c i workflow."""

    """GIVEN c i workflow and the scenario: ci file exists"""
    def test_ci_file_exists(self):
        """THEN the expected behaviour holds: ci file exists"""
        assert (_REPO_ROOT / ".github" / "workflows" / "ci.yml").exists()

    """GIVEN c i workflow and the scenario: ci has test job"""
    def test_ci_has_test_job(self):
        """WHEN the code under test is exercised for: ci has test job"""
        content = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()

        """THEN the expected behaviour holds: ci has test job"""
        assert "pytest" in content

    """GIVEN c i workflow and the scenario: ci has docker job"""
    def test_ci_has_docker_job(self):
        """WHEN the code under test is exercised for: ci has docker job"""
        content = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()

        """THEN the expected behaviour holds: ci has docker job"""
        assert "docker" in content.lower()


# ===========================================================================
# FAQ / Troubleshooting
# ===========================================================================


class TestDocumentation:
    """Tests for documentation."""

    """GIVEN documentation and the scenario: troubleshooting faq"""
    def test_troubleshooting_faq(self):
        """WHEN the code under test is exercised for: troubleshooting faq"""
        content = (_REPO_ROOT / "docs" / "troubleshooting.md").read_text()

        """THEN the expected behaviour holds: troubleshooting faq"""
        assert "Frequently Asked Questions" in content or "FAQ" in content

    """GIVEN documentation and the scenario: changelog exists"""
    def test_changelog_exists(self):
        """THEN the expected behaviour holds: changelog exists"""
        assert (_REPO_ROOT / "CHANGELOG.md").exists()
        content = (_REPO_ROOT / "CHANGELOG.md").read_text()
        assert "[1.0.0]" in content

    """GIVEN documentation and the scenario: field mapping guide"""
    def test_field_mapping_guide(self):
        """THEN the expected behaviour holds: field mapping guide"""
        assert (_REPO_ROOT / "docs" / "field-mapping.md").exists()


# ===========================================================================
# Config Schema Validation
# ===========================================================================


class TestConfigSchema:
    """Tests for config schema."""

    """GIVEN config schema and the scenario: schema valid json"""
    def test_schema_valid_json(self):
        """WHEN the code under test is exercised for: schema valid json"""
        data = json.loads((_REPO_ROOT / "config.schema.json").read_text())

        """THEN the expected behaviour holds: schema valid json"""
        assert "$schema" in data or "type" in data

    """GIVEN config schema and the scenario: team thresholds in schema"""
    def test_team_thresholds_in_schema(self):
        """WHEN the code under test is exercised for: team thresholds in schema"""
        data = json.loads((_REPO_ROOT / "config.schema.json").read_text())
        team_props = data["properties"]["teams"]["items"]["properties"]

        """THEN the expected behaviour holds: team thresholds in schema"""
        assert "thresholds" in team_props
        assert team_props["thresholds"]["type"] == "object"


# ===========================================================================
# Integration: End-to-end API health
# ===========================================================================


class TestAPIIntegration:
    """Tests for a p i integration."""

    """GIVEN a p i integration and the scenario: health with correlation id"""
    def test_health_with_correlation_id(self):
        """WHEN the code under test is exercised for: health with correlation id"""
        import asyncio

        from httpx import ASGITransport, AsyncClient

        from flowboard.web.server import create_app

        app = create_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/health/live", headers={"X-Request-ID": "integration-test"})
                return r

        resp = asyncio.get_event_loop().run_until_complete(_run())

        """THEN the expected behaviour holds: health with correlation id"""
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "integration-test"

    """GIVEN a p i integration and the scenario: webhook then events"""
    def test_webhook_then_events(self):
        """WHEN the code under test is exercised for: webhook then events"""
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

        """THEN the expected behaviour holds: webhook then events"""
        assert data["count"] >= 1
        assert any(e["issue_key"] == "INT-1" for e in data["events"])
