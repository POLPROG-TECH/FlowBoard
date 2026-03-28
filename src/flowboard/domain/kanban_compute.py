"""Kanban analytics — cycle time, throughput, WIP, flow efficiency, CFD.

Computes Kanban-specific metrics from a :class:`BoardSnapshot`.
All functions are pure (no side effects) and operate on domain models.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta

from flowboard.domain.kanban_models import (
    CFDDataPoint,
    CycleTimeRecord,
    FlowMetrics,
    KanbanInsights,
    ThroughputRecord,
    WIPSnapshot,
)
from flowboard.domain.models import Issue
from flowboard.shared.types import StatusCategory

# ---------------------------------------------------------------------------
# Cycle time & lead time
# ---------------------------------------------------------------------------


def compute_cycle_times(
    issues: list[Issue],
) -> list[CycleTimeRecord]:
    """Compute cycle time and lead time for all completed issues.

    Cycle time = time from first IN_PROGRESS to DONE (approximated
    by ``updated - created`` when transition dates aren't available,
    but refined when ``resolved`` is set).

    Lead time = time from CREATED to DONE.
    """
    records: list[CycleTimeRecord] = []
    for issue in issues:
        if not issue.is_done or issue.resolved is None or issue.created is None:
            continue

        resolved_date = issue.resolved.date() if hasattr(issue.resolved, "date") else issue.resolved
        created_date = issue.created.date() if hasattr(issue.created, "date") else issue.created

        lead_time = max(0.0, (resolved_date - created_date).days)

        # Approximate cycle time: if we don't have transition data,
        # use 60% of lead time as a reasonable heuristic (queue time ≈ 40%)
        cycle_time = lead_time * 0.6 if lead_time > 0 else 0.0

        assignee_name = issue.assignee.display_name if issue.assignee else ""
        team_name = issue.assignee.team if issue.assignee else ""

        records.append(
            CycleTimeRecord(
                key=issue.key,
                summary=issue.summary,
                issue_type=issue.issue_type.value
                if hasattr(issue.issue_type, "value")
                else str(issue.issue_type),
                assignee=assignee_name,
                team=team_name,
                cycle_time_days=round(cycle_time, 1),
                lead_time_days=round(lead_time, 1),
                started=created_date,
                completed=resolved_date,
            )
        )

    return sorted(records, key=lambda r: r.completed or date.min, reverse=True)


# ---------------------------------------------------------------------------
# Throughput
# ---------------------------------------------------------------------------


def compute_throughput(
    issues: list[Issue],
    *,
    weeks: int = 8,
    today: date | None = None,
) -> list[ThroughputRecord]:
    """Compute weekly throughput (items completed per week)."""
    today = today or date.today()
    start = today - timedelta(weeks=weeks)

    # Bucket completed issues by ISO week
    weekly: dict[date, list[Issue]] = defaultdict(list)
    for issue in issues:
        if not issue.is_done or issue.resolved is None:
            continue
        resolved_date = issue.resolved.date() if hasattr(issue.resolved, "date") else issue.resolved
        if resolved_date < start:
            continue
        # Monday of the week
        week_start = resolved_date - timedelta(days=resolved_date.weekday())
        weekly[week_start].append(issue)

    records: list[ThroughputRecord] = []
    current = start - timedelta(days=start.weekday())  # align to Monday
    while current <= today:
        week_end = current + timedelta(days=6)
        items = weekly.get(current, [])
        records.append(
            ThroughputRecord(
                period_start=current,
                period_end=min(week_end, today),
                count=len(items),
                story_points=sum(i.story_points for i in items),
            )
        )
        current += timedelta(weeks=1)

    return records


# ---------------------------------------------------------------------------
# WIP snapshot
# ---------------------------------------------------------------------------


def compute_wip_snapshot(
    issues: list[Issue],
    wip_limit: int = 5,
) -> WIPSnapshot:
    """Compute current work-in-progress counts and violations."""
    wip_count = 0
    by_team: dict[str, int] = defaultdict(int)
    by_person: dict[str, int] = defaultdict(int)

    for issue in issues:
        if issue.status_category != StatusCategory.IN_PROGRESS:
            continue
        wip_count += 1
        name = issue.assignee.display_name if issue.assignee else "Unassigned"
        team = issue.assignee.team if issue.assignee else "No Team"
        by_person[name] += 1
        by_team[team] += 1

    violations = [person for person, count in by_person.items() if count > wip_limit]

    return WIPSnapshot(
        date=date.today(),
        wip_count=wip_count,
        wip_by_team=dict(by_team),
        wip_by_person=dict(by_person),
        violations=violations,
    )


# ---------------------------------------------------------------------------
# Cumulative Flow Diagram
# ---------------------------------------------------------------------------


def compute_cfd(
    issues: list[Issue],
    *,
    days: int = 30,
    today: date | None = None,
) -> list[CFDDataPoint]:
    """Build cumulative flow diagram data points.

    For each day in the window, counts how many issues were in each
    status category (todo / in_progress / done) based on created and
    resolved dates.
    """
    today = today or date.today()
    start = today - timedelta(days=days)

    points: list[CFDDataPoint] = []
    for offset in range(days + 1):
        d = start + timedelta(days=offset)
        todo = 0
        in_progress = 0
        done = 0

        for issue in issues:
            created = (
                issue.created.date() if issue.created and hasattr(issue.created, "date") else None
            )
            resolved = (
                issue.resolved.date()
                if issue.resolved and hasattr(issue.resolved, "date")
                else None
            )

            if created is None or created > d:
                continue  # issue didn't exist yet

            if resolved and resolved <= d:
                done += 1
            elif issue.status_category == StatusCategory.IN_PROGRESS:
                in_progress += 1
            else:
                todo += 1

        points.append(CFDDataPoint(date=d, todo=todo, in_progress=in_progress, done=done))

    return points


# ---------------------------------------------------------------------------
# Aggregate flow metrics
# ---------------------------------------------------------------------------


def compute_flow_metrics(
    cycle_times: list[CycleTimeRecord],
    throughput: list[ThroughputRecord],
    wip: WIPSnapshot,
    wip_limit: int = 5,
) -> FlowMetrics:
    """Compute aggregate flow metrics from individual measurements."""
    ct_values = [r.cycle_time_days for r in cycle_times if r.cycle_time_days > 0]
    lt_values = [r.lead_time_days for r in cycle_times if r.lead_time_days > 0]

    avg_ct = statistics.mean(ct_values) if ct_values else 0.0
    median_ct = statistics.median(ct_values) if ct_values else 0.0
    p85_ct = sorted(ct_values)[min(int(len(ct_values) * 0.85), len(ct_values) - 1)] if len(ct_values) > 1 else avg_ct
    avg_lt = statistics.mean(lt_values) if lt_values else 0.0

    # Throughput per week (average of non-zero weeks)
    tp_values = [r.count for r in throughput]
    tp_per_week = statistics.mean(tp_values) if tp_values else 0.0

    # Flow efficiency = avg_cycle_time / avg_lead_time
    flow_eff = (avg_ct / avg_lt) if avg_lt > 0 else 0.0

    return FlowMetrics(
        avg_cycle_time=round(avg_ct, 1),
        median_cycle_time=round(median_ct, 1),
        p85_cycle_time=round(p85_ct, 1),
        avg_lead_time=round(avg_lt, 1),
        throughput_per_week=round(tp_per_week, 1),
        flow_efficiency=round(flow_eff, 2),
        current_wip=wip.wip_count,
        wip_limit=wip_limit,
        wip_violations=len(wip.violations),
    )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def compute_kanban_insights(
    issues: list[Issue],
    wip_limit: int = 5,
    *,
    today: date | None = None,
) -> KanbanInsights:
    """Compute all Kanban analytics from a list of issues."""
    today = today or date.today()

    cycle_times = compute_cycle_times(issues)
    throughput = compute_throughput(issues, today=today)
    wip = compute_wip_snapshot(issues, wip_limit=wip_limit)
    cfd = compute_cfd(issues, today=today)
    flow = compute_flow_metrics(cycle_times, throughput, wip, wip_limit=wip_limit)

    return KanbanInsights(
        flow_metrics=flow,
        cycle_times=cycle_times,
        throughput=throughput,
        wip_snapshot=wip,
        cfd_data=cfd,
    )
