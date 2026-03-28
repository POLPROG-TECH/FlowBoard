"""Workload and capacity analysis.

Computes per-person and per-team workload metrics from the normalized
issue set and configuration thresholds.
"""

from __future__ import annotations

from collections import defaultdict

from flowboard.domain.models import (
    CapacityRecord,
    Issue,
    Person,
    Team,
    TeamWorkload,
    WorkloadRecord,
)
from flowboard.infrastructure.config.loader import Thresholds
from flowboard.shared.types import IssueType, Priority, StatusCategory


def compute_workload_records(
    issues: list[Issue],
    thresholds: Thresholds,
) -> list[WorkloadRecord]:
    """Build one :class:`WorkloadRecord` per unique assignee."""
    by_person: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        if issue.assignee:
            by_person[issue.assignee.account_id].append(issue)

    records: list[WorkloadRecord] = []
    person_map: dict[str, Person] = {
        i.assignee.account_id: i.assignee for i in issues if i.assignee
    }
    for aid, person_issues in by_person.items():
        person = person_map[aid]
        by_type: dict[IssueType, int] = defaultdict(int)
        by_status: dict[StatusCategory, int] = defaultdict(int)
        by_priority: dict[Priority, int] = defaultdict(int)
        sp = 0.0
        in_progress = 0
        blocked = 0
        for iss in person_issues:
            by_type[iss.issue_type] += 1
            by_status[iss.status_category] += 1
            by_priority[iss.priority] += 1
            sp += iss.story_points
            if iss.is_in_progress:
                in_progress += 1
            if iss.is_blocked:
                blocked += 1
        records.append(
            WorkloadRecord(
                person=person,
                team=person.team,
                issue_count=len(person_issues),
                story_points=sp,
                by_type=dict(by_type),
                by_status=dict(by_status),
                by_priority=dict(by_priority),
                in_progress_count=in_progress,
                blocked_count=blocked,
            )
        )
    records.sort(key=lambda r: r.story_points, reverse=True)
    return records


def compute_team_workloads(
    workload_records: list[WorkloadRecord],
    teams: list[Team],
) -> list[TeamWorkload]:
    """Aggregate individual workloads into per-team summaries."""
    by_team: dict[str, list[WorkloadRecord]] = defaultdict(list)
    for wr in workload_records:
        key = wr.team or "Unassigned"
        by_team[key].append(wr)

    team_map = {t.key: t for t in teams}
    results: list[TeamWorkload] = []
    for key, members in by_team.items():
        team = team_map.get(key, Team(key=key, name=key))
        total_issues = sum(m.issue_count for m in members)
        total_sp = sum(m.story_points for m in members)
        merged_status: dict[StatusCategory, int] = defaultdict(int)
        wip = 0
        for m in members:
            for cat, cnt in m.by_status.items():
                merged_status[cat] += cnt
            wip += m.in_progress_count
        results.append(
            TeamWorkload(
                team=team,
                total_issues=total_issues,
                total_story_points=total_sp,
                member_workloads=members,
                by_status=dict(merged_status),
                wip_count=wip,
            )
        )
    results.sort(key=lambda tw: tw.total_story_points, reverse=True)
    return results


def compute_capacity_records(
    workload_records: list[WorkloadRecord],
    issues: list[Issue],
    capacity_per_person: float,
) -> list[CapacityRecord]:
    """Compute capacity utilisation per person."""
    completed_by_person: dict[str, float] = defaultdict(float)
    for issue in issues:
        if issue.assignee and issue.is_done:
            completed_by_person[issue.assignee.account_id] += issue.story_points

    records: list[CapacityRecord] = []
    for wr in workload_records:
        aid = wr.person.account_id
        done_sp = completed_by_person.get(aid, 0.0)
        records.append(
            CapacityRecord(
                person=wr.person,
                team=wr.team,
                allocated_points=wr.story_points,
                completed_points=done_sp,
                remaining_points=max(0.0, wr.story_points - done_sp),
            )
        )
    return records
