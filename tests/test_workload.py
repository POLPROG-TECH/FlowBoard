"""Tests for workload and capacity calculations."""

from __future__ import annotations

from flowboard.domain.models import Issue, Team
from flowboard.domain.workload import (
    compute_capacity_records,
    compute_team_workloads,
    compute_workload_records,
)


class TestComputeWorkloadRecords:
    """GIVEN a set of issues, WHEN workload is computed, THEN per-person metrics are correct."""

    def test_story_points_aggregated_per_person(self, sample_issues: list[Issue], config) -> None:
        # GIVEN issues assigned to alice (P-2: 8sp, P-4: 3sp, P-8: 3sp) = 14 total
        records = compute_workload_records(sample_issues, config.thresholds)
        alice_rec = next(r for r in records if r.person.display_name == "Alice")
        # Alice has P-1 (epic, 0sp), P-2 (8), P-4 (3), P-8 (3) = 14
        assert alice_rec.story_points == 14.0
        assert alice_rec.issue_count == 4

    def test_blocked_count(self, sample_issues: list[Issue], config) -> None:
        records = compute_workload_records(sample_issues, config.thresholds)
        bob_rec = next(r for r in records if r.person.display_name == "Bob")
        # Bob has P-3 which is blocked
        assert bob_rec.blocked_count == 1

    def test_in_progress_count(self, sample_issues: list[Issue], config) -> None:
        records = compute_workload_records(sample_issues, config.thresholds)
        alice_rec = next(r for r in records if r.person.display_name == "Alice")
        # Alice: P-1 (in_prog), P-2 (in_prog), P-8 (in_prog) = 3
        assert alice_rec.in_progress_count == 3

    def test_empty_issues_returns_empty(self, config) -> None:
        assert compute_workload_records([], config.thresholds) == []


class TestComputeTeamWorkloads:
    def test_team_aggregation(
        self, sample_issues: list[Issue], config, team_alpha: Team, team_beta: Team
    ) -> None:
        records = compute_workload_records(sample_issues, config.thresholds)
        teams = compute_team_workloads(records, [team_alpha, team_beta])
        alpha = next(tw for tw in teams if tw.team.key == "alpha")
        # Alpha has Alice + Bob
        assert alpha.total_issues == 6  # P-1,P-2,P-3,P-4,P-6,P-8
        assert alpha.total_story_points == 32.0  # 14 (alice) + 18 (bob)


class TestCapacityRecords:
    def test_completed_points_tracked(self, sample_issues: list[Issue], config) -> None:
        records = compute_workload_records(sample_issues, config.thresholds)
        caps = compute_capacity_records(records, sample_issues, 13.0)
        alice_cap = next(c for c in caps if c.person.display_name == "Alice")
        # Alice completed P-4 (3sp Done)
        assert alice_cap.completed_points == 3.0
        assert alice_cap.remaining_points == 14.0 - 3.0
