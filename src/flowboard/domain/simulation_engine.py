"""Internal computation functions for the capacity simulation engine."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any

from flowboard.domain.models import (
    BoardSnapshot,
    WorkloadRecord,
)
from flowboard.domain.simulation_models import (
    MetricDelta,
    Recommendation,
    SimulationMetrics,
    SimulationScenario,
    TeamImpact,
)
from flowboard.domain.timeline import (
    OverlapMarker,
    TimelineBar,
    TimelineData,
    TimelineMode,
    TimelineSwimlane,
    _compute_range,
    _detect_overlaps,
    _issue_date_range,
    _make_bar,
    _sprint_boundaries,
)
from flowboard.shared.types import RiskSeverity

if TYPE_CHECKING:
    from flowboard.domain.models import Issue, Team
    from flowboard.infrastructure.config.loader import Thresholds


# ---------------------------------------------------------------------------
# Baseline metrics computation
# ---------------------------------------------------------------------------


def compute_baseline_metrics(
    snapshot: BoardSnapshot,
    thresholds: Thresholds,
) -> SimulationMetrics:
    """Extract current-state metrics from the board snapshot."""
    wrs = snapshot.workload_records
    conflicts = snapshot.overlap_conflicts

    overloaded = sum(1 for wr in wrs if wr.story_points > thresholds.overload_points)
    wip_violations = sum(1 for wr in wrs if wr.in_progress_count > thresholds.wip_limit)
    total_sp = sum(wr.story_points for wr in wrs)
    avg_load = total_sp / len(wrs) if wrs else 0.0
    max_load = max((wr.story_points for wr in wrs), default=0.0)

    # Timeline overlap count
    tl_overlaps = 0
    for issue in snapshot.issues:
        if not issue.is_done and issue.assignee:
            rng = _issue_date_range(issue)
            if rng:
                tl_overlaps += 1  # count only as contribution basis
    # Use actual conflict count for timeline overlaps
    tl_overlap_count = sum(
        1 for c in conflicts if c.category in ("resource_contention", "timeline_overlap")
    )

    blocked_count = sum(1 for i in snapshot.issues if i.is_blocked and not i.is_done)
    peak_concurrent = max((wr.in_progress_count for wr in wrs), default=0)

    # Utilization
    cap_records = snapshot.capacity_records
    avg_util = (
        sum(cr.utilization_pct for cr in cap_records) / len(cap_records) if cap_records else 0.0
    )

    # Team risk: teams where average load > overload threshold
    team_loads: dict[str, list[float]] = defaultdict(list)
    for wr in wrs:
        team_loads[wr.team or "unassigned"].append(wr.story_points)
    at_risk = sum(
        1
        for loads in team_loads.values()
        if loads and (sum(loads) / len(loads)) > thresholds.overload_points
    )

    # Balance score: 100 = perfectly balanced, 0 = completely imbalanced
    if wrs and len(wrs) > 1:
        loads = [wr.story_points for wr in wrs]
        mean = sum(loads) / len(loads)
        variance = sum((x - mean) ** 2 for x in loads) / len(loads)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean if mean > 0 else 0
        balance = max(0.0, min(100.0, 100.0 * (1.0 - cv)))
    else:
        balance = 100.0

    return SimulationMetrics(
        total_collisions=len(conflicts),
        overloaded_people=overloaded,
        wip_violations=wip_violations,
        timeline_overlaps=tl_overlap_count,
        avg_load_per_person=round(avg_load, 1),
        max_load_person=round(max_load, 1),
        avg_utilization_pct=round(avg_util, 1),
        peak_concurrent_tasks=peak_concurrent,
        blocked_work_items=blocked_count,
        at_risk_teams=at_risk,
        total_story_points=round(total_sp, 1),
        team_balance_score=round(balance, 1),
    )


# ---------------------------------------------------------------------------
# Simulate workload redistribution
# ---------------------------------------------------------------------------


def _simulate_workloads(
    wrs: list[WorkloadRecord],
    teams: list[Team],
    scenario: SimulationScenario,
    thresholds: Thresholds,
) -> tuple[list[dict[str, object]], SimulationMetrics]:
    """Simulate the effect of resource changes on workload distribution.

    Returns (simulated_workload_summaries, simulated_metrics).
    The simulation redistributes existing work proportionally among
    current + new members within each affected team.
    """
    change_map: dict[str, int] = {}
    for rc in scenario.changes:
        change_map[rc.team_key] = change_map.get(rc.team_key, 0) + rc.delta

    # Group workloads by team
    by_team: dict[str, list[WorkloadRecord]] = defaultdict(list)
    for wr in wrs:
        by_team[wr.team or "unassigned"].append(wr)

    sim_workloads: list[dict[str, object]] = []
    total_sp = 0.0
    all_loads: list[float] = []
    overloaded = 0
    wip_viols = 0
    peak_concurrent = 0
    collision_estimate = 0

    for team_key, members in by_team.items():
        delta = change_map.get(team_key, 0)
        current_count = len(members)
        new_count = max(1, current_count + delta)
        redistribution_factor = current_count / new_count

        team_total_sp = sum(m.story_points for m in members)
        team_total_issues = sum(m.issue_count for m in members)

        for m in members:
            sim_sp = m.story_points * redistribution_factor
            sim_issues = max(1, round(m.issue_count * redistribution_factor))
            sim_wip = max(0, round(m.in_progress_count * redistribution_factor))
            sim_blocked = m.blocked_count

            all_loads.append(sim_sp)
            total_sp += sim_sp
            if sim_sp > thresholds.overload_points:
                overloaded += 1
            if sim_wip > thresholds.wip_limit:
                wip_viols += 1
            peak_concurrent = max(peak_concurrent, sim_wip)
            # Count collisions: people with >1 concurrent in-progress task
            if sim_wip > 1:
                collision_estimate += sim_wip - 1

            sim_workloads.append(
                {
                    "person": m.person.display_name,
                    "team": team_key,
                    "story_points": round(sim_sp, 1),
                    "issue_count": sim_issues,
                    "in_progress": sim_wip,
                    "blocked": sim_blocked,
                    "original_sp": m.story_points,
                    "reduction_pct": round((1 - redistribution_factor) * 100, 1),
                }
            )

        # New team members (simulated placeholders)
        if delta > 0:
            new_person_sp = team_total_sp / new_count
            new_person_issues = max(1, round(team_total_issues / new_count))
            for i in range(delta):
                all_loads.append(new_person_sp)
                total_sp += new_person_sp
                sim_workloads.append(
                    {
                        "person": f"New {team_key.upper()} #{i + 1}",
                        "team": team_key,
                        "story_points": round(new_person_sp, 1),
                        "issue_count": new_person_issues,
                        "in_progress": 0,
                        "blocked": 0,
                        "original_sp": 0.0,
                        "reduction_pct": 0.0,
                        "is_new": True,
                    }
                )

    # Compute simulated aggregate metrics
    n = len(all_loads) or 1
    avg_load = total_sp / n
    max_load = max(all_loads, default=0.0)

    if n > 1:
        mean = sum(all_loads) / n
        variance = sum((x - mean) ** 2 for x in all_loads) / n
        std_dev = math.sqrt(variance)
        cv = std_dev / mean if mean > 0 else 0
        balance = max(0.0, min(100.0, 100.0 * (1.0 - cv)))
    else:
        balance = 100.0

    metrics = SimulationMetrics(
        total_collisions=collision_estimate,
        overloaded_people=overloaded,
        wip_violations=wip_viols,
        timeline_overlaps=0,
        avg_load_per_person=round(avg_load, 1),
        max_load_person=round(max_load, 1),
        avg_utilization_pct=0.0,
        peak_concurrent_tasks=peak_concurrent,
        blocked_work_items=sum(1 for w in sim_workloads if w.get("blocked", 0) > 0),
        at_risk_teams=0,
        total_story_points=round(total_sp, 1),
        team_balance_score=round(balance, 1),
    )

    return sim_workloads, metrics


# ---------------------------------------------------------------------------
# Simulate timeline redistribution
# ---------------------------------------------------------------------------


def _simulate_timeline(
    snapshot: BoardSnapshot,
    scenario: SimulationScenario,
) -> TimelineData:
    """Build a simulated assignee timeline after resource redistribution.

    New resources absorb work proportionally, spreading bars more evenly
    across time and reducing overlap density.
    """
    change_map: dict[str, int] = {}
    for rc in scenario.changes:
        change_map[rc.team_key] = change_map.get(rc.team_key, 0) + rc.delta

    # Build bars grouped by team
    team_bars: dict[str, list[tuple[Issue, date, date]]] = defaultdict(list)
    for issue in snapshot.issues:
        if issue.is_done:
            continue
        rng = _issue_date_range(issue)
        if rng is None:
            continue
        team_key = issue.assignee.team if issue.assignee else "unassigned"
        team_bars[team_key].append((issue, rng[0], rng[1]))

    all_bars: list[TimelineBar] = []
    groups: dict[str, list[TimelineBar]] = defaultdict(list)

    for team_key, items in team_bars.items():
        delta = change_map.get(team_key, 0)
        if delta <= 0:
            # No change — keep original assignment
            for issue, start, end in items:
                bar = _make_bar(issue, start, end)
                assignee_name = bar.assignee
                groups[assignee_name].append(bar)
                all_bars.append(bar)
            continue

        # Distribute items across existing + new members
        existing_assignees: dict[str, list[tuple[Issue, date, date]]] = defaultdict(list)
        for issue, start, end in items:
            name = issue.assignee.display_name if issue.assignee else "Unassigned"
            existing_assignees[name].append((issue, start, end))

        new_names = [f"New {team_key.upper()} #{i + 1}" for i in range(delta)]
        all_assignees = list(existing_assignees.keys()) + new_names
        total_members = len(all_assignees)

        # Redistribute: move items from overloaded to new members
        all_items = [
            (name, issue, s, e)
            for name, items_list in existing_assignees.items()
            for issue, s, e in items_list
        ]
        # Sort by start date for even distribution
        all_items.sort(key=lambda x: x[2])

        distributed: dict[str, list[tuple[Issue, date, date]]] = defaultdict(list)
        # Round-robin assignment
        for idx, (_orig_name, issue, s, e) in enumerate(all_items):
            target = all_assignees[idx % total_members]
            distributed[target].append((issue, s, e))

        for assignee_name, issue_list in distributed.items():
            for issue, start, end in issue_list:
                bar = TimelineBar(
                    key=issue.key,
                    label=issue.summary[:60],
                    assignee=assignee_name,
                    team=team_key,
                    start=start,
                    end=end,
                    progress_pct=100.0 if issue.is_done else 50.0 if issue.is_in_progress else 0.0,
                    story_points=issue.story_points,
                    is_blocked=issue.is_blocked,
                    is_done=issue.is_done,
                    issue_type=issue.issue_type.value,
                    priority=issue.priority.value,
                    epic_key=issue.epic_key,
                    sprint_name=issue.sprint.name if issue.sprint else "",
                )
                groups[assignee_name].append(bar)
                all_bars.append(bar)

    swimlanes: list[TimelineSwimlane] = []
    all_overlaps: list[OverlapMarker] = []
    for name in sorted(groups.keys()):
        bars = groups[name]
        overlaps = _detect_overlaps(bars, name)
        all_overlaps.extend(overlaps)
        swimlanes.append(
            TimelineSwimlane(
                key=name,
                label=name,
                bars=sorted(bars, key=lambda b: b.start),
                overlap_count=len(overlaps),
                total_points=sum(b.story_points for b in bars),
            )
        )

    swimlanes.sort(key=lambda s: (-s.overlap_count, s.label))
    rng_start, rng_end = _compute_range(all_bars)

    return TimelineData(
        mode=TimelineMode.ASSIGNEE,
        swimlanes=swimlanes,
        overlaps=all_overlaps,
        range_start=rng_start,
        range_end=rng_end,
        total_days=(rng_end - rng_start).days,
        sprint_boundaries=_sprint_boundaries(snapshot),
    )


# ---------------------------------------------------------------------------
# Compute deltas between baseline and simulated
# ---------------------------------------------------------------------------


def _compute_delta(baseline: SimulationMetrics, simulated: SimulationMetrics) -> MetricDelta:
    """Compute improvement deltas (positive = improvement)."""

    def _pct_reduction(before: float, after: float) -> float:
        if before == 0:
            return 0.0
        return round(((before - after) / before) * 100, 1)

    return MetricDelta(
        collisions_reduced=max(0, baseline.total_collisions - simulated.total_collisions),
        overload_reduced=max(0, baseline.overloaded_people - simulated.overloaded_people),
        wip_violations_reduced=max(0, baseline.wip_violations - simulated.wip_violations),
        timeline_overlaps_reduced=max(0, baseline.timeline_overlaps - simulated.timeline_overlaps),
        avg_load_reduction_pct=_pct_reduction(
            baseline.avg_load_per_person, simulated.avg_load_per_person
        ),
        peak_load_reduction_pct=_pct_reduction(baseline.max_load_person, simulated.max_load_person),
        utilization_improvement_pct=round(
            simulated.avg_utilization_pct - baseline.avg_utilization_pct, 1
        ),
        risk_teams_reduced=max(0, baseline.at_risk_teams - simulated.at_risk_teams),
        balance_improvement=round(simulated.team_balance_score - baseline.team_balance_score, 1),
    )


# ---------------------------------------------------------------------------
# Team impact analysis — where to hire next
# ---------------------------------------------------------------------------


def compute_team_impacts(
    snapshot: BoardSnapshot,
    thresholds: Thresholds,
) -> list[TeamImpact]:
    """Analyze which team would benefit most from an additional resource."""
    by_team: dict[str, list[WorkloadRecord]] = defaultdict(list)
    for wr in snapshot.workload_records:
        by_team[wr.team or "unassigned"].append(wr)

    team_map = {t.key: t for t in snapshot.teams}
    impacts: list[TeamImpact] = []

    for team_key, members in by_team.items():
        team = team_map.get(team_key)
        team_name = team.name if team else team_key
        total_sp = sum(m.story_points for m in members)
        member_count = len(members)
        load_per_person = total_sp / member_count if member_count else total_sp

        overloaded = sum(1 for m in members if m.story_points > thresholds.overload_points)
        collision_contrib = sum(
            1
            for c in snapshot.overlap_conflicts
            if any(p in [m.person.display_name for m in members] for p in c.affected_people)
        )

        # Impact score: weighted combination of factors
        score = 0.0
        # Overload factor (40% weight)
        if member_count > 0:
            overload_ratio = overloaded / member_count
            score += overload_ratio * 40
        # Load per person vs threshold (30% weight)
        if thresholds.overload_points > 0:
            load_ratio = min(2.0, load_per_person / thresholds.overload_points)
            score += load_ratio * 15
        # Collision contribution (20% weight)
        score += min(20.0, collision_contrib * 4)
        # WIP pressure (10% weight)
        wip_pressure = sum(m.in_progress_count for m in members)
        wip_threshold = thresholds.wip_limit * member_count
        if wip_threshold > 0:
            score += min(10.0, (wip_pressure / wip_threshold) * 10)

        score = min(100.0, score)

        impacts.append(
            TeamImpact(
                team_key=team_key,
                team_name=team_name,
                current_load=round(total_sp, 1),
                current_members=member_count,
                load_per_person=round(load_per_person, 1),
                collision_contribution=collision_contrib,
                overloaded_members=overloaded,
                impact_score=round(score, 1),
            )
        )

    impacts.sort(key=lambda ti: ti.impact_score, reverse=True)

    # Add recommendations
    for i, ti in enumerate(impacts):
        if i == 0 and ti.impact_score > 30:
            ti.recommendation = (
                f"Highest impact: adding 1 resource to {ti.team_name} would "
                f"reduce load per person from {ti.load_per_person:.0f} SP to "
                f"{ti.current_load / (ti.current_members + 1):.0f} SP"
            )
        elif ti.overloaded_members > 0:
            ti.recommendation = (
                f"{ti.overloaded_members} overloaded member(s) — "
                f"additional capacity would reduce pressure"
            )

    return impacts


# ---------------------------------------------------------------------------
# Global recommendations
# ---------------------------------------------------------------------------


def compute_recommendations(
    snapshot: BoardSnapshot,
    baseline: SimulationMetrics,
    team_impacts: list[TeamImpact],
    thresholds: Thresholds,
    *,
    t: Any = None,
) -> list[Recommendation]:
    """Generate actionable staffing and workload recommendations."""

    def _t(key: str, **kw: object) -> str:
        if t is not None:
            return t(key, **kw)
        # Fallback: load English catalog directly
        from flowboard.i18n.translator import Translator

        _fallback = Translator("en")
        return _fallback(key, **kw)

    recs: list[Recommendation] = []
    priority = 1

    # 1. Best hire recommendation
    if team_impacts and team_impacts[0].impact_score > 20:
        best = team_impacts[0]
        recs.append(
            Recommendation(
                priority=priority,
                severity=RiskSeverity.HIGH if best.impact_score > 50 else RiskSeverity.MEDIUM,
                title=_t("sim.rec.add_resource_title", team=best.team_name),
                description=_t(
                    "sim.rec.add_resource_desc",
                    team=best.team_name,
                    load=f"{best.load_per_person:.0f}",
                    overloaded=best.overloaded_members,
                ),
                team_key=best.team_key,
                impact_score=best.impact_score,
            )
        )
        priority += 1

    # 2. Overload warnings
    for wr in snapshot.workload_records:
        if wr.story_points > thresholds.overload_points * 1.5:
            recs.append(
                Recommendation(
                    priority=priority,
                    severity=RiskSeverity.CRITICAL,
                    title=_t("sim.rec.overload_title", person=wr.person.display_name),
                    description=_t(
                        "sim.rec.overload_desc",
                        points=f"{wr.story_points:.0f}",
                        threshold=f"{thresholds.overload_points:.0f}",
                        excess=f"{wr.story_points - thresholds.overload_points:.0f}",
                    ),
                    team_key=wr.team,
                    impact_score=min(100, wr.story_points / thresholds.overload_points * 50),
                )
            )
            priority += 1

    # 3. WIP limit violations
    wip_violators = [
        wr for wr in snapshot.workload_records if wr.in_progress_count > thresholds.wip_limit
    ]
    if wip_violators:
        names = ", ".join(wr.person.display_name for wr in wip_violators[:3])
        names_display = (
            _t("sim.rec.wip_and_others", names=names) if len(wip_violators) > 3 else names
        )
        recs.append(
            Recommendation(
                priority=priority,
                severity=RiskSeverity.HIGH,
                title=_t("sim.rec.wip_title", count=len(wip_violators)),
                description=_t(
                    "sim.rec.wip_desc",
                    names=names_display,
                    limit=thresholds.wip_limit,
                ),
                impact_score=min(80, len(wip_violators) * 15),
            )
        )
        priority += 1

    # 4. Team balance
    if team_impacts and len(team_impacts) >= 2:
        loads = [ti.load_per_person for ti in team_impacts if ti.current_members > 0]
        if loads and max(loads) > min(loads) * 2:
            heaviest = team_impacts[0]
            lightest = min(team_impacts, key=lambda ti: ti.load_per_person)
            recs.append(
                Recommendation(
                    priority=priority,
                    severity=RiskSeverity.MEDIUM,
                    title=_t("sim.rec.imbalance_title"),
                    description=_t(
                        "sim.rec.imbalance_desc",
                        heavy=heaviest.team_name,
                        heavy_load=f"{heaviest.load_per_person:.0f}",
                        light=lightest.team_name,
                        light_load=f"{lightest.load_per_person:.0f}",
                    ),
                    impact_score=40,
                )
            )
            priority += 1

    # 5. Blocked work cluster
    blocked_issues = [i for i in snapshot.issues if i.is_blocked and not i.is_done]
    if len(blocked_issues) > 3:
        recs.append(
            Recommendation(
                priority=priority,
                severity=RiskSeverity.MEDIUM,
                title=_t("sim.rec.blocked_title", count=len(blocked_issues)),
                description=_t(
                    "sim.rec.blocked_desc",
                    points=f"{sum(i.story_points for i in blocked_issues):.0f}",
                ),
                impact_score=min(60, len(blocked_issues) * 8),
            )
        )
        priority += 1

    recs.sort(key=lambda r: (-r.impact_score, r.priority))
    return recs
