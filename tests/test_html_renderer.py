"""Tests for HTML rendering - ensuring the dashboard generates valid output."""

from __future__ import annotations

from datetime import date

import pytest

from flowboard.application.orchestrator import analyse_raw_payload
from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.presentation.html.renderer import render_dashboard


class TestRenderDashboard:
    """Tests for render dashboard."""

    @pytest.fixture()
    def rendered_html(self, mock_jira_payload: dict, config: FlowBoardConfig) -> str:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        return render_dashboard(snapshot, config)

    """GIVEN render dashboard and the scenario: html is not empty"""
    def test_html_is_not_empty(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: html is not empty"""
        assert len(rendered_html) > 1000

    """GIVEN render dashboard and the scenario: contains doctype"""
    def test_contains_doctype(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains doctype"""
        assert "<!DOCTYPE html>" in rendered_html

    """GIVEN render dashboard and the scenario: contains title"""
    def test_contains_title(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains title"""
        assert "Test Board" in rendered_html

    """GIVEN render dashboard and the scenario: contains summary cards"""
    def test_contains_summary_cards(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains summary cards"""
        assert "summary-card" in rendered_html
        assert "Total Issues" in rendered_html

    """GIVEN render dashboard and the scenario: contains chart canvases"""
    def test_contains_chart_canvases(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains chart canvases"""
        assert "chartStatus" in rendered_html
        assert "chartWorkload" in rendered_html

    """GIVEN render dashboard and the scenario: contains workload table"""
    def test_contains_workload_table(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains workload table"""
        assert "Story Points" in rendered_html

    """GIVEN render dashboard and the scenario: contains risk section"""
    def test_contains_risk_section(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains risk section"""
        assert "Risk Signals" in rendered_html

    """GIVEN render dashboard and the scenario: contains navigation tabs"""
    def test_contains_navigation_tabs(self, rendered_html: str) -> None:
        """THEN the expected behaviour holds: contains navigation tabs"""
        assert "tab-btn" in rendered_html
        assert "Overview" in rendered_html
        assert "Workload" in rendered_html
        assert "Sprints" in rendered_html

    """GIVEN render dashboard and the scenario: no secrets in output"""
    def test_no_secrets_in_output(self, rendered_html: str, config: FlowBoardConfig) -> None:
        """THEN the expected behaviour holds: no secrets in output"""
        if config.jira.auth_token:
            assert config.jira.auth_token not in rendered_html
