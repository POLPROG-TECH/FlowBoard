"""Tests for HTML rendering — ensuring the dashboard generates valid output."""

from __future__ import annotations

from datetime import date

import pytest

from flowboard.application.orchestrator import analyse_raw_payload
from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.presentation.html.renderer import render_dashboard


class TestRenderDashboard:
    """GIVEN a fully analysed snapshot, WHEN rendered, THEN valid HTML is produced."""

    @pytest.fixture()
    def rendered_html(self, mock_jira_payload: dict, config: FlowBoardConfig) -> str:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        return render_dashboard(snapshot, config)

    def test_html_is_not_empty(self, rendered_html: str) -> None:
        assert len(rendered_html) > 1000

    def test_contains_doctype(self, rendered_html: str) -> None:
        assert "<!DOCTYPE html>" in rendered_html

    def test_contains_title(self, rendered_html: str) -> None:
        assert "Test Board" in rendered_html

    def test_contains_summary_cards(self, rendered_html: str) -> None:
        assert "summary-card" in rendered_html
        assert "Total Issues" in rendered_html

    def test_contains_chart_canvases(self, rendered_html: str) -> None:
        assert "chartStatus" in rendered_html
        assert "chartWorkload" in rendered_html

    def test_contains_workload_table(self, rendered_html: str) -> None:
        assert "Story Points" in rendered_html

    def test_contains_risk_section(self, rendered_html: str) -> None:
        assert "Risk Signals" in rendered_html

    def test_contains_navigation_tabs(self, rendered_html: str) -> None:
        assert "tab-btn" in rendered_html
        assert "Overview" in rendered_html
        assert "Workload" in rendered_html
        assert "Sprints" in rendered_html

    def test_no_secrets_in_output(self, rendered_html: str, config: FlowBoardConfig) -> None:
        # THEN no auth token appears in the HTML
        if config.jira.auth_token:
            assert config.jira.auth_token not in rendered_html
