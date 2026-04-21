"""Tests for overlap and conflict detection."""

from __future__ import annotations

from datetime import date

from flowboard.domain.models import RoadmapItem
from flowboard.domain.overlap import detect_all_conflicts
from flowboard.infrastructure.config.loader import Thresholds
from flowboard.shared.types import Priority, StatusCategory


class TestResourceContention:
    """Tests for resource contention."""

    """GIVEN resource contention and the scenario: wip over limit flagged"""
    def test_wip_over_limit_flagged(self, alice, make_issue, active_sprint) -> None:
        """WHEN the code under test is exercised for: wip over limit flagged"""
        issues = [
            make_issue(
                f"T-{i}",
                f"Task {i}",
                assignee=alice,
                status_category=StatusCategory.IN_PROGRESS,
                story_points=2,
                sprint=active_sprint,
            )
            for i in range(6)
        ]
        thresholds = Thresholds(wip_limit=5, overload_points=50)
        from flowboard.domain.workload import compute_workload_records

        records = compute_workload_records(issues, thresholds)

        conflicts = detect_all_conflicts(issues, records, [], thresholds)

        contention = [c for c in conflicts if c.category == "resource_contention"]

        """THEN the expected behaviour holds: wip over limit flagged"""
        assert len(contention) >= 1
        assert "Alice" in contention[0].description


class TestPriorityPileUp:
    """GIVEN priority pile up and the scenario: too many high priority items"""
    def test_too_many_high_priority_items(self, alice, make_issue) -> None:
        """WHEN the code under test is exercised for: too many high priority items"""
        issues = [
            make_issue(
                f"T-{i}",
                f"Urgent {i}",
                assignee=alice,
                priority=Priority.HIGHEST,
                status_category=StatusCategory.TODO,
            )
            for i in range(5)
        ]
        thresholds = Thresholds()
        from flowboard.domain.workload import compute_workload_records

        records = compute_workload_records(issues, thresholds)

        conflicts = detect_all_conflicts(issues, records, [], thresholds)
        pile_ups = [c for c in conflicts if c.category == "priority_pile_up"]

        """THEN the expected behaviour holds: too many high priority items"""
        assert len(pile_ups) == 1


class TestTimelineOverlap:
    """GIVEN timeline overlap and the scenario: overlapping epics for same owner"""
    def test_overlapping_epics_for_same_owner(self, alice) -> None:
        """WHEN the code under test is exercised for: overlapping epics for same owner"""
        items = [
            RoadmapItem(
                key="E-1",
                title="Epic A",
                owner=alice,
                start_date=date(2026, 3, 1),
                target_date=date(2026, 3, 20),
                status=StatusCategory.IN_PROGRESS,
            ),
            RoadmapItem(
                key="E-2",
                title="Epic B",
                owner=alice,
                start_date=date(2026, 3, 10),
                target_date=date(2026, 4, 5),
                status=StatusCategory.IN_PROGRESS,
            ),
        ]
        thresholds = Thresholds()
        conflicts = detect_all_conflicts([], [], items, thresholds, today=date(2026, 3, 15))
        overlaps = [c for c in conflicts if c.category == "timeline_overlap"]

        """THEN the expected behaviour holds: overlapping epics for same owner"""
        assert len(overlaps) == 1
        assert "E-1" in overlaps[0].affected_keys
        assert "E-2" in overlaps[0].affected_keys
