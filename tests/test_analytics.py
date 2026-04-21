"""Tests for the full analytics pipeline (orchestrator)."""

from __future__ import annotations

from datetime import date

from flowboard.application.orchestrator import analyse_raw_payload
from flowboard.infrastructure.config.loader import FlowBoardConfig


class TestAnalyseRawPayload:
    """Tests for analyse raw payload."""

    """GIVEN analyse raw payload and the scenario: snapshot populated"""
    def test_snapshot_populated(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: snapshot populated"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))

        """THEN the expected behaviour holds: snapshot populated"""
        assert len(snapshot.issues) == 20
        assert len(snapshot.sprints) == 3
        assert len(snapshot.workload_records) > 0
        assert len(snapshot.team_workloads) > 0
        assert len(snapshot.roadmap_items) == 3

    """GIVEN analyse raw payload and the scenario: risk signals generated"""
    def test_risk_signals_generated(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: risk signals generated"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        # With realistic data and low thresholds, there should be risks

        """THEN the expected behaviour holds: risk signals generated"""
        assert len(snapshot.risk_signals) > 0

    """GIVEN analyse raw payload and the scenario: dependencies extracted"""
    def test_dependencies_extracted(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: dependencies extracted"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))

        """THEN the expected behaviour holds: dependencies extracted"""
        assert len(snapshot.dependencies) > 0

    """GIVEN analyse raw payload and the scenario: sprint health computed"""
    def test_sprint_health_computed(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: sprint health computed"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))

        """THEN the expected behaviour holds: sprint health computed"""
        assert len(snapshot.sprint_health) > 0
        active = [sh for sh in snapshot.sprint_health if sh.sprint.name == "Sprint 12"]
        assert len(active) == 1
        assert active[0].total_issues > 0
