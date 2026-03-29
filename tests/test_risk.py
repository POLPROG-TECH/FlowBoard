"""Tests for risk detection engine."""

from __future__ import annotations

from datetime import UTC, date, datetime

from flowboard.domain.models import RoadmapItem
from flowboard.domain.risk import detect_all_risks
from flowboard.infrastructure.config.loader import Thresholds
from flowboard.shared.types import (
    RiskCategory,
    StatusCategory,
)


class TestOverloadRisks:
    def test_sp_overload_detected(self, alice, make_issue) -> None:
        # GIVEN Alice assigned 25 SP (threshold=15)
        issues = [
            make_issue(
                "T-1", assignee=alice, story_points=25, status_category=StatusCategory.IN_PROGRESS
            )
        ]
        thresholds = Thresholds(overload_points=15)
        from flowboard.domain.workload import compute_workload_records

        records = compute_workload_records(issues, thresholds)

        # WHEN
        risks = detect_all_risks(issues, records, [], [], thresholds, today=date(2026, 3, 15))

        # THEN
        overload = [r for r in risks if r.category == RiskCategory.OVERLOAD]
        assert len(overload) >= 1
        assert "Alice" in overload[0].title


class TestAgingRisks:
    def test_aging_issue_flagged(self, make_issue) -> None:
        old_issue = make_issue(
            "OLD-1",
            status_category=StatusCategory.TODO,
            created=datetime(2026, 1, 1, tzinfo=UTC),
        )
        thresholds = Thresholds(aging_days=10)
        risks = detect_all_risks([old_issue], [], [], [], thresholds, today=date(2026, 3, 15))
        aging = [r for r in risks if r.category == RiskCategory.AGING]
        assert len(aging) >= 1


class TestRoadmapRisks:
    def test_overdue_epic_flagged(self) -> None:
        item = RoadmapItem(
            key="E-1",
            title="Late Epic",
            target_date=date(2026, 3, 1),
            progress_pct=40.0,
            status=StatusCategory.IN_PROGRESS,
        )
        thresholds = Thresholds()
        risks = detect_all_risks([], [], [], [item], thresholds, today=date(2026, 3, 15))
        scope = [r for r in risks if r.category == RiskCategory.SCOPE_CREEP]
        assert len(scope) >= 1
        assert "overdue" in scope[0].title.lower()
