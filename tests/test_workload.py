"""Tests for workload and capacity calculations."""

from __future__ import annotations

from flowboard.domain.models import Issue, Team
from flowboard.domain.workload import (
    compute_capacity_records,
    compute_team_workloads,
    compute_workload_records,
)


class TestComputeWorkloadRecords:
    """Tests for compute workload records."""

    """GIVEN compute workload records and the scenario: story points aggregated per person"""
    def test_story_points_aggregated_per_person(self, sample_issues: list[Issue], config) -> None:
        """WHEN the code under test is exercised for: story points aggregated per person"""
        records = compute_workload_records(sample_issues, config.thresholds)
        alice_rec = next(r for r in records if r.person.display_name == "Alice")
        # Alice has P-1 (epic, 0sp), P-2 (8), P-4 (3), P-8 (3) = 14

        """THEN the expected behaviour holds: story points aggregated per person"""
        assert alice_rec.story_points == 14.0
        assert alice_rec.issue_count == 4

    """GIVEN compute workload records and the scenario: blocked count"""
    def test_blocked_count(self, sample_issues: list[Issue], config) -> None:
        """WHEN the code under test is exercised for: blocked count"""
        records = compute_workload_records(sample_issues, config.thresholds)
        bob_rec = next(r for r in records if r.person.display_name == "Bob")
        # Bob has P-3 which is blocked

        """THEN the expected behaviour holds: blocked count"""
        assert bob_rec.blocked_count == 1

    """GIVEN compute workload records and the scenario: in progress count"""
    def test_in_progress_count(self, sample_issues: list[Issue], config) -> None:
        """WHEN the code under test is exercised for: in progress count"""
        records = compute_workload_records(sample_issues, config.thresholds)
        alice_rec = next(r for r in records if r.person.display_name == "Alice")
        # Alice: P-1 (in_prog), P-2 (in_prog), P-8 (in_prog) = 3

        """THEN the expected behaviour holds: in progress count"""
        assert alice_rec.in_progress_count == 3

    """GIVEN compute workload records and the scenario: empty issues returns empty"""
    def test_empty_issues_returns_empty(self, config) -> None:
        """THEN the expected behaviour holds: empty issues returns empty"""
        assert compute_workload_records([], config.thresholds) == []


class TestComputeTeamWorkloads:
    """GIVEN compute team workloads and the scenario: team aggregation"""
    def test_team_aggregation(
        self, sample_issues: list[Issue], config, team_alpha: Team, team_beta: Team
    ) -> None:
        """WHEN the code under test is exercised for: team aggregation"""
        records = compute_workload_records(sample_issues, config.thresholds)
        teams = compute_team_workloads(records, [team_alpha, team_beta])
        alpha = next(tw for tw in teams if tw.team.key == "alpha")
        # Alpha has Alice + Bob

        """THEN the expected behaviour holds: team aggregation"""
        assert alpha.total_issues == 6  # P-1,P-2,P-3,P-4,P-6,P-8
        assert alpha.total_story_points == 32.0  # 14 (alice) + 18 (bob)


class TestCapacityRecords:
    """GIVEN capacity records and the scenario: completed points tracked"""
    def test_completed_points_tracked(self, sample_issues: list[Issue], config) -> None:
        """WHEN the code under test is exercised for: completed points tracked"""
        records = compute_workload_records(sample_issues, config.thresholds)
        caps = compute_capacity_records(records, sample_issues, 13.0)
        alice_cap = next(c for c in caps if c.person.display_name == "Alice")
        # Alice completed P-4 (3sp Done)

        """THEN the expected behaviour holds: completed points tracked"""
        assert alice_cap.completed_points == 3.0
        assert alice_cap.remaining_points == 14.0 - 3.0
