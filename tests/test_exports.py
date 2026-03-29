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
    def test_valid_json_output(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        result = export_json(snapshot)
        parsed = json.loads(result)
        assert parsed["summary"]["total_issues"] == 20
        assert "risk_signals" in parsed

    def test_no_secrets_in_json(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        result = export_json(snapshot)
        assert "tok-123" not in result


class TestCsvExport:
    def test_workload_csv_has_headers(
        self, mock_jira_payload: dict, config: FlowBoardConfig
    ) -> None:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        csv_str = export_workload_csv(snapshot)
        assert "Person,Team,Issues,Story Points" in csv_str
        assert len(csv_str.strip().split("\n")) > 1

    def test_issues_csv(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        csv_str = export_issues_csv(snapshot)
        assert "PROJ-1" in csv_str

    def test_risks_csv(self, mock_jira_payload: dict, config: FlowBoardConfig) -> None:
        snapshot = analyse_raw_payload(mock_jira_payload, config, today=date(2026, 3, 15))
        csv_str = export_risks_csv(snapshot)
        assert "Severity" in csv_str
