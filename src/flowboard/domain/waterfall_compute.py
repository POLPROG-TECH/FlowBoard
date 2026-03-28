"""Waterfall analytics — phases, milestones, critical path.

Computes Waterfall-specific metrics from a list of issues.
Phases are inferred from fix_versions or epic groupings.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from flowboard.domain.models import Issue
from flowboard.domain.waterfall_models import (
    CriticalPathItem,
    Milestone,
    Phase,
    PhaseProgress,
    WaterfallInsights,
)
from flowboard.shared.types import StatusCategory

# ---------------------------------------------------------------------------
# Phase detection — infer phases from fix_versions or epics
# ---------------------------------------------------------------------------


def _infer_phases(issues: list[Issue], today: date) -> list[Phase]:
    """Group issues into phases based on fix_versions (preferred) or epics."""
    by_version: dict[str, list[Issue]] = defaultdict(list)
    by_epic: dict[str, list[Issue]] = defaultdict(list)

    for issue in issues:
        if issue.fix_versions:
            for fv in issue.fix_versions:
                by_version[fv].append(issue)
        elif issue.epic_key:
            by_epic[issue.epic_key].append(issue)

    # Prefer fix_versions; fall back to epics
    groups = by_version if by_version else by_epic
    if not groups:
        return []

    phases: list[Phase] = []
    for key, group_issues in sorted(groups.items()):
        total = len(group_issues)
        done = sum(1 for i in group_issues if i.is_done)
        in_prog = sum(1 for i in group_issues if i.status_category == StatusCategory.IN_PROGRESS)
        blocked = sum(1 for i in group_issues if i.is_blocked)
        progress = (done / total * 100) if total > 0 else 0.0

        # Determine date range
        starts = [i.created.date() for i in group_issues if i.created]
        ends = [i.due_date for i in group_issues if i.due_date]
        start_date = min(starts) if starts else None
        end_date = max(ends) if ends else None

        # Determine status
        if progress >= 100:
            status = "completed"
        elif blocked > total * 0.2 and end_date and end_date < today and progress < 100:
            status = "delayed"
        elif (end_date and end_date < today and progress < 100) or (
            end_date and (end_date - today).days < 7 and progress < 80
        ):
            status = "at_risk"
        else:
            status = "on_track"

        phases.append(
            Phase(
                key=key,
                name=key,
                start_date=start_date,
                end_date=end_date,
                progress_pct=round(progress, 1),
                total_issues=total,
                done_issues=done,
                in_progress_issues=in_prog,
                blocked_issues=blocked,
                status=status,
            )
        )

    return phases


# ---------------------------------------------------------------------------
# Milestone detection — infer from fix_versions with due dates
# ---------------------------------------------------------------------------


def _infer_milestones(
    issues: list[Issue],
    phases: list[Phase],
    today: date,
) -> list[Milestone]:
    """Create milestones from phase end dates."""
    milestones: list[Milestone] = []
    for phase in phases:
        if phase.end_date is None:
            continue

        if phase.status == "completed":
            status = "completed"
        elif phase.end_date < today:
            status = "missed"
        elif phase.end_date < today + timedelta(days=7) and phase.progress_pct < 80:
            status = "at_risk"
        else:
            status = "on_track"

        milestones.append(
            Milestone(
                key=f"MS-{phase.key}",
                name=f"{phase.name} Complete",
                target_date=phase.end_date,
                status=status,
                blocking_issues=phase.blocked_issues,
            )
        )

    return milestones


# ---------------------------------------------------------------------------
# Critical path — simplified: longest chain of blocked/dependent items
# ---------------------------------------------------------------------------


def _compute_critical_path(
    issues: list[Issue],
    phases: list[Phase],
) -> list[CriticalPathItem]:
    """Identify items on the critical path (blocked or long-duration items)."""
    critical: list[CriticalPathItem] = []

    # Items that are blocked or have the longest remaining duration
    in_flight = [i for i in issues if not i.is_done]
    # Sort by due date (soonest first), blocked items first
    in_flight.sort(key=lambda i: (not i.is_blocked, i.due_date or date.max))

    for issue in in_flight[:15]:
        phase_name = ""
        for p in phases:
            if issue.fix_versions and p.key in issue.fix_versions:
                phase_name = p.name
                break

        critical.append(
            CriticalPathItem(
                key=issue.key,
                summary=issue.summary,
                phase=phase_name,
                start_date=issue.created.date() if issue.created else None,
                end_date=issue.due_date,
                slack_days=max(0, (issue.due_date - date.today()).days) if issue.due_date else 0,
                is_critical=issue.is_blocked
                or (issue.due_date is not None and issue.due_date < date.today()),
                assignee=issue.assignee.display_name if issue.assignee else "",
            )
        )

    return critical


# ---------------------------------------------------------------------------
# Phase progress summary
# ---------------------------------------------------------------------------


def _compute_phase_progress(phases: list[Phase]) -> PhaseProgress:
    """Aggregate phase progress into a summary."""
    if not phases:
        return PhaseProgress()

    completed = sum(1 for p in phases if p.status == "completed")
    on_track = sum(1 for p in phases if p.status == "on_track")
    at_risk = sum(1 for p in phases if p.status == "at_risk")
    delayed = sum(1 for p in phases if p.status == "delayed")

    overall = sum(p.progress_pct for p in phases) / len(phases) if phases else 0.0

    # Current phase = first non-completed phase
    current = ""
    for p in phases:
        if p.status != "completed":
            current = p.name
            break

    return PhaseProgress(
        total_phases=len(phases),
        completed_phases=completed,
        current_phase=current,
        overall_progress_pct=round(overall, 1),
        on_track=on_track,
        at_risk=at_risk,
        delayed=delayed,
    )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def compute_waterfall_insights(
    issues: list[Issue],
    *,
    today: date | None = None,
) -> WaterfallInsights:
    """Compute all Waterfall analytics from a list of issues."""
    today = today or date.today()

    phases = _infer_phases(issues, today)
    milestones = _infer_milestones(issues, phases, today)
    critical_path = _compute_critical_path(issues, phases)
    phase_progress = _compute_phase_progress(phases)

    return WaterfallInsights(
        phases=phases,
        milestones=milestones,
        critical_path=critical_path,
        phase_progress=phase_progress,
    )
