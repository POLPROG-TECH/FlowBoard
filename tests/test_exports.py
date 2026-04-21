"""Tests for export functionality."""

from __future__ import annotations

import json
from datetime import date

from flowboard.application.orchestrator import analyse_raw_payload
from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.presentation.export.csv_export import (
    export_issues_csv,
    export_risks_csv,
    export_workload_csv,
)
from flowboard.presentation.export.json_export import export_json


class TestJsonExport:
    """GIVEN json export and the scenario: valid json output"""
    def test_valid_json_output(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: valid json output"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        result = export_json(snapshot)
        parsed = json.loads(result)

        """THEN the expected behaviour holds: valid json output"""
        assert parsed["summary"]["total_issues"] == 20
        assert "risk_signals" in parsed

    """GIVEN json export and the scenario: no secrets in json"""
    def test_no_secrets_in_json(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: no secrets in json"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        result = export_json(snapshot)

        """THEN the expected behaviour holds: no secrets in json"""
        assert "tok-123" not in result


class TestCsvExport:
    """GIVEN csv export and the scenario: workload csv has headers"""
    def test_workload_csv_has_headers(
        self, mock_jira_payload: dict, config: FlowBoardConfig
    ) -> None:
        """WHEN the code under test is exercised for: workload csv has headers"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        csv_str = export_workload_csv(snapshot)

        """THEN the expected behaviour holds: workload csv has headers"""
        assert "Person,Team,Issues,Story Points" in csv_str
        assert len(csv_str.strip().split("\n")) > 1

    """GIVEN csv export and the scenario: issues csv"""
    def test_issues_csv(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: issues csv"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        csv_str = export_issues_csv(snapshot)

        """THEN the expected behaviour holds: issues csv"""
        assert "PROJ-1" in csv_str

    """GIVEN csv export and the scenario: risks csv"""
    def test_risks_csv(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        """WHEN the code under test is exercised for: risks csv"""
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        csv_str = export_risks_csv(snapshot)

        """THEN the expected behaviour holds: risks csv"""
        assert "Severity" in csv_str
