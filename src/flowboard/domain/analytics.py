"""High-level analytics façade.

Coordinates workload, risk, dependency, and overlap analysis to build
a complete :class:`BoardSnapshot`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from flowboard.domain.dependencies import (
    compute_sprint_health,
)
from flowboard.domain.models import (
    BoardSnapshot,
    Dependency,
    Issue,
    Person,
    RoadmapItem,
    Sprint,
    Team,
)
from flowboard.domain.overlap import detect_all_conflicts
from flowboard.domain.pi import compute_pi_snapshot
from flowboard.domain.risk import detect_all_risks
from flowboard.domain.scrum import compute_scrum_insights
from flowboard.domain.simulation import run_simulation_suite
from flowboard.domain.workload import (
    compute_capacity_records,
    compute_team_workloads,
    compute_workload_records,
)
from flowboard.infrastructure.config.loader import FlowBoardConfig


def build_board_snapshot(
    issues: list[Issue],
    sprints: list[Sprint],
    teams: list[Team],
    roadmap_items: list[RoadmapItem],
    dependencies: list[Dependency],
    people: list[Person],
    config: FlowBoardConfig,
    *,
    today: date | None = None,
) -> BoardSnapshot:
    """Assemble a full analytical snapshot from normalized data."""
    from flowboard.i18n.translator import get_translator

    today = today or date.today()
    t = get_translator(config.locale)

    # Workload
    workload_records = compute_workload_records(issues, config.thresholds)
    team_workloads = compute_team_workloads(workload_records, teams)
    capacity_records = compute_capacity_records(
        workload_records,
        issues,
        config.thresholds.capacity_per_person,
    )

    # Sprint health
    sprint_issues: dict[int, list[Issue]] = defaultdict(list)
    for issue in issues:
        if issue.sprint:
            sprint_issues[issue.sprint.id].append(issue)
    sprint_healths = compute_sprint_health(
        sprint_issues, sprints, config.thresholds.aging_days, today=today
    )

    # Risk
    risk_signals = detect_all_risks(
        issues,
        workload_records,
        sprint_healths,
        roadmap_items,
        config.thresholds,
        today=today,
        t=t,
    )

    # Overlap / conflicts
    overlap_conflicts = detect_all_conflicts(
        issues,
        workload_records,
        roadmap_items,
        config.thresholds,
        today=today,
        t=t,
    )

    # PI snapshot (only when enabled and start_date is set)
    pi_snap = None
    if config.pi.enabled and config.pi.start_date:
        try:
            pi_snap = compute_pi_snapshot(
                name=config.pi.name or "Current PI",
                pi_start_iso=config.pi.start_date,
                sprint_length=config.pi.sprint_length_days,
                num_sprints=config.pi.sprints_per_pi,
                working_days=config.pi.working_days,
                today=today,
            )
        except (ValueError, TypeError):
            import logging

            logging.getLogger("flowboard.analytics").warning(
                "Failed to compute PI snapshot — check pi config dates"
            )
            pi_snap = None

    # Capacity simulation (when enabled)
    sim_suite = None
    if config.simulation.enabled and teams:
        snapshot_for_sim = BoardSnapshot(
            title=config.output.title,
            projects=config.jira.projects,
            issues=issues,
            sprints=sprints,
            teams=teams,
            people=people,
            roadmap_items=roadmap_items,
            sprint_health=sprint_healths,
            workload_records=workload_records,
            team_workloads=team_workloads,
            capacity_records=capacity_records,
            dependencies=dependencies,
            risk_signals=risk_signals,
            overlap_conflicts=overlap_conflicts,
            pi_snapshot=pi_snap,
        )
        sim_suite = run_simulation_suite(snapshot_for_sim, config.thresholds, t=t)

    # Scrum insights (computed when methodology uses sprints)
    scrum = None
    methodology = getattr(config, "methodology", "scrum")
    if methodology in ("scrum", "hybrid"):
        scrum = compute_scrum_insights(
            BoardSnapshot(
                title=config.output.title,
                projects=config.jira.projects,
                issues=issues,
                sprints=sprints,
                teams=teams,
                people=people,
                roadmap_items=roadmap_items,
                sprint_health=sprint_healths,
                workload_records=workload_records,
                team_workloads=team_workloads,
                capacity_records=capacity_records,
                dependencies=dependencies,
                risk_signals=risk_signals,
                overlap_conflicts=overlap_conflicts,
            ),
            config.thresholds,
            today,
        )

    # Kanban insights (computed when methodology uses flow metrics)
    kanban = None
    if methodology in ("kanban", "hybrid"):
        from flowboard.domain.kanban_compute import compute_kanban_insights

        kanban = compute_kanban_insights(
            issues,
            wip_limit=config.thresholds.wip_limit,
            today=today,
        )

    # Waterfall insights (computed when methodology uses phases)
    waterfall = None
    if methodology in ("waterfall",):
        from flowboard.domain.waterfall_compute import compute_waterfall_insights

        waterfall = compute_waterfall_insights(issues, today=today)

    return BoardSnapshot(
        title=config.output.title,
        projects=config.jira.projects,
        issues=issues,
        sprints=sprints,
        teams=teams,
        people=people,
        roadmap_items=roadmap_items,
        sprint_health=sprint_healths,
        workload_records=workload_records,
        team_workloads=team_workloads,
        capacity_records=capacity_records,
        dependencies=dependencies,
        risk_signals=risk_signals,
        overlap_conflicts=overlap_conflicts,
        pi_snapshot=pi_snap,
        simulation=sim_suite,
        scrum_insights=scrum,
        kanban_insights=kanban,
        waterfall_insights=waterfall,
    )
