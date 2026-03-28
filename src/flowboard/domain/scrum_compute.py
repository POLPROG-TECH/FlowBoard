"""Compute functions for Scrum-oriented analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING

from flowboard.domain.scrum_models import (
    BacklogQualityReport,
    BlockerItem,
    CapacityRow,
    CeremonySummary,
    DeliveryRiskItem,
    DependencyHeatCell,
    EpicProgress,
    GoalItem,
    ProductProgressReport,
    ReadinessItem,
    ReadinessReport,
    ScopeChangeReport,
    SprintGoalReport,
)

if TYPE_CHECKING:
    from flowboard.domain.models import (
        BoardSnapshot,
        Issue,
        SprintHealth,
    )


# ---------------------------------------------------------------------------
# Analytics functions
# ---------------------------------------------------------------------------


def _is_goal_item(issue: Issue) -> bool:
    """Heuristic: high-priority items in a sprint are sprint-goal items."""
    from flowboard.domain.models import Priority

    return issue.priority in (Priority.HIGHEST, Priority.HIGH)


def compute_sprint_goals(
    issues: list[Issue],
    sprint_healths: list[SprintHealth],
) -> list[SprintGoalReport]:
    """Assess sprint goal health for each sprint."""
    from flowboard.domain.models import StatusCategory

    sprint_issues: dict[str, list[Issue]] = defaultdict(list)
    for iss in issues:
        if iss.sprint:
            sprint_issues[iss.sprint.name].append(iss)

    reports: list[SprintGoalReport] = []
    for sh in sprint_healths:
        sp_name = sh.sprint.name
        goal_items: list[GoalItem] = []
        completed = in_prog = blocked = not_started = 0

        for iss in sprint_issues.get(sp_name, []):
            if not _is_goal_item(iss):
                continue
            assignee = iss.assignee.display_name if iss.assignee else "__unassigned__"
            status_cat = iss.status_category
            is_at_risk = iss.is_blocked or (
                status_cat == StatusCategory.TODO and sh.sprint.state.value == "active"
            )
            gi = GoalItem(
                key=iss.key,
                summary=iss.summary[:60],
                status=status_cat.value,
                assignee=assignee,
                story_points=iss.story_points,
                is_blocked=iss.is_blocked,
                is_at_risk=is_at_risk,
            )
            goal_items.append(gi)
            if status_cat == StatusCategory.DONE:
                completed += 1
            elif iss.is_blocked:
                blocked += 1
            elif status_cat == StatusCategory.IN_PROGRESS:
                in_prog += 1
            else:
                not_started += 1

        total = len(goal_items)
        pct = (completed / total * 100) if total else 0.0
        if blocked > 0 or (not_started > completed and sh.sprint.state.value == "active"):
            health = "off_track"
        elif not_started > 0 and sh.sprint.state.value == "active":
            health = "at_risk"
        else:
            health = "on_track"

        reports.append(
            SprintGoalReport(
                sprint_name=sp_name,
                sprint_state=sh.sprint.state.value,
                total_goal_items=total,
                completed=completed,
                in_progress=in_prog,
                blocked=blocked,
                not_started=not_started,
                completion_pct=pct,
                health=health,
                goal_items=goal_items,
            )
        )
    return reports


def compute_scope_changes(
    issues: list[Issue],
    sprint_healths: list[SprintHealth],
) -> list[ScopeChangeReport]:
    """Track scope churn per sprint."""
    reports: list[ScopeChangeReport] = []

    for sh in sprint_healths:
        sp = sh.sprint
        if not sp.start_date:
            continue

        sp_issues = [i for i in issues if i.sprint and i.sprint.name == sp.name]
        original: list[Issue] = []
        added: list[Issue] = []

        for iss in sp_issues:
            created = (
                iss.created.date()
                if iss.created and hasattr(iss.created, "date")
                else (iss.created if iss.created else None)
            )
            if created and created > sp.start_date + timedelta(days=1):
                added.append(iss)
            else:
                original.append(iss)

        sp_orig = sum(i.story_points for i in original)
        sp_added = sum(i.story_points for i in added)
        churn = (len(added) / len(original) * 100) if original else (100.0 if added else 0.0)
        stability = "stable" if churn < 10 else ("moderate" if churn < 25 else "unstable")

        added_items = [
            GoalItem(
                key=i.key,
                summary=i.summary[:60],
                status=i.status_category.value,
                assignee=i.assignee.display_name if i.assignee else "__unassigned__",
                story_points=i.story_points,
                is_blocked=i.is_blocked,
                is_at_risk=False,
            )
            for i in added[:20]
        ]

        reports.append(
            ScopeChangeReport(
                sprint_name=sp.name,
                original_count=len(original),
                added_count=len(added),
                sp_original=sp_orig,
                sp_added=sp_added,
                churn_pct=churn,
                stability=stability,
                added_items=added_items,
            )
        )
    return reports


def compute_blockers(
    issues: list[Issue],
    today: date | None = None,
) -> list[BlockerItem]:
    """Identify blocked items with aging and escalation severity."""
    today = today or date.today()
    items: list[BlockerItem] = []

    for iss in issues:
        if not iss.is_blocked:
            continue
        age = iss.age_days or 0
        if age <= 0 and iss.created:
            created = iss.created.date() if hasattr(iss.created, "date") else iss.created
            age = (today - created).days

        if age > 7:
            severity = "escalate"
        elif age > 3:
            severity = "critical"
        else:
            severity = "warning"

        items.append(
            BlockerItem(
                key=iss.key,
                summary=iss.summary[:60],
                assignee=iss.assignee.display_name if iss.assignee else "__unassigned__",
                team=iss.assignee.team if iss.assignee else "",
                blocked_days=age,
                severity=severity,
                sprint_name=iss.sprint.name if iss.sprint else "—",
            )
        )

    return sorted(items, key=lambda b: -b.blocked_days)


def compute_backlog_quality(
    issues: list[Issue],
    stale_days: int = 30,
    today: date | None = None,
) -> BacklogQualityReport:
    """Assess backlog hygiene for Product Owners."""
    from flowboard.domain.models import Priority, StatusCategory

    today = today or date.today()
    backlog = [i for i in issues if i.status_category == StatusCategory.TODO]
    if not backlog:
        return BacklogQualityReport(quality_score=100.0, grade="A")

    total = len(backlog)
    no_est = sum(1 for i in backlog if i.story_points <= 0)
    no_assign = sum(1 for i in backlog if not i.assignee)
    no_epic = sum(1 for i in backlog if not i.epic_key)
    no_pri = sum(1 for i in backlog if i.priority == Priority.UNSET)
    stale = 0
    for i in backlog:
        if i.created:
            created = i.created.date() if hasattr(i.created, "date") else i.created
            if (today - created).days > stale_days:
                stale += 1

    checks = total * 5
    issues_found = no_est + no_assign + no_epic + no_pri + stale
    score = max(0.0, (1 - issues_found / checks) * 100) if checks else 100.0
    grade = "A" if score >= 85 else ("B" if score >= 70 else ("C" if score >= 50 else "D"))

    return BacklogQualityReport(
        total_backlog=total,
        no_estimate=no_est,
        no_assignee=no_assign,
        no_epic=no_epic,
        stale_count=stale,
        no_priority=no_pri,
        quality_score=round(score, 1),
        grade=grade,
    )


def compute_readiness(
    issues: list[Issue],
    max_sp: float = 13.0,
) -> ReadinessReport:
    """Assess whether backlog items are ready for sprint commitment."""
    from flowboard.domain.models import Priority, StatusCategory

    candidates = [
        i for i in issues if i.status_category == StatusCategory.TODO and not i.is_blocked
    ]
    if not candidates:
        return ReadinessReport()

    items: list[ReadinessItem] = []
    for iss in candidates[:50]:
        missing: list[str] = []
        has_est = iss.story_points > 0
        has_assign = iss.assignee is not None
        has_epic = bool(iss.epic_key)
        has_pri = iss.priority != Priority.UNSET
        small = iss.story_points <= max_sp

        if not has_est:
            missing.append("estimate")
        if not has_assign:
            missing.append("assignee")
        if not has_epic:
            missing.append("epic")
        if not has_pri:
            missing.append("priority")
        if not small:
            missing.append("too_large")

        checks = 5
        passed = sum([has_est, has_assign, has_epic, has_pri, small])
        pct = passed / checks * 100

        items.append(
            ReadinessItem(
                key=iss.key,
                summary=iss.summary[:60],
                has_estimate=has_est,
                has_assignee=has_assign,
                has_epic=has_epic,
                has_priority=has_pri,
                is_small_enough=small,
                readiness_pct=pct,
                missing=missing,
            )
        )

    ready = sum(1 for i in items if i.readiness_pct >= 80)
    partial = sum(1 for i in items if 40 <= i.readiness_pct < 80)
    not_ready = sum(1 for i in items if i.readiness_pct < 40)
    avg = sum(i.readiness_pct for i in items) / len(items) if items else 0.0

    return ReadinessReport(
        total_candidates=len(items),
        ready_count=ready,
        partial_count=partial,
        not_ready_count=not_ready,
        avg_readiness=round(avg, 1),
        items=sorted(items, key=lambda x: -x.readiness_pct),
    )


def compute_delivery_risks(
    issues: list[Issue],
    sprint_healths: list[SprintHealth],
) -> list[DeliveryRiskItem]:
    """Heuristic delivery-risk forecast per epic."""
    from flowboard.domain.models import StatusCategory

    epic_issues: dict[str, list[Issue]] = defaultdict(list)
    for iss in issues:
        if iss.epic_key:
            epic_issues[iss.epic_key].append(iss)

    results: list[DeliveryRiskItem] = []
    for epic_key, ep_issues in epic_issues.items():
        factors: list[str] = []
        score = 0.0

        total = len(ep_issues)
        blocked = sum(1 for i in ep_issues if i.is_blocked)
        done = sum(1 for i in ep_issues if i.status_category == StatusCategory.DONE)
        in_prog = sum(1 for i in ep_issues if i.status_category == StatusCategory.IN_PROGRESS)
        todo = total - done - in_prog

        if blocked > 0:
            score += blocked * 15
            factors.append(f"blocked:{blocked}")
        if total > 0 and done / total < 0.3 and in_prog > 0:
            score += 10
            factors.append("low_completion")
        if in_prog > 5:
            score += 10
            factors.append(f"high_wip:{in_prog}")
        if todo > done and total > 3:
            score += 8
            factors.append("more_todo")

        score = min(score, 100.0)
        level = (
            "critical"
            if score >= 60
            else "high"
            if score >= 40
            else "medium"
            if score >= 20
            else "low"
        )

        title = ep_issues[0].summary[:50] if ep_issues else epic_key
        results.append(
            DeliveryRiskItem(
                key=epic_key,
                title=title,
                risk_score=round(score, 1),
                factors=factors,
                level=level,
            )
        )

    return sorted(results, key=lambda r: -r.risk_score)


def compute_dependency_heatmap(
    snapshot: BoardSnapshot,
) -> tuple[list[DependencyHeatCell], list[str]]:
    """Build a team-to-team dependency heatmap."""
    issue_map: dict[str, Issue] = {i.key: i for i in snapshot.issues}
    team_pairs: dict[tuple[str, str], list[bool]] = defaultdict(list)
    all_teams: set[str] = set()

    for dep in snapshot.dependencies:
        src = issue_map.get(dep.source_key)
        tgt = issue_map.get(dep.target_key)
        if not src or not tgt:
            continue
        src_team = src.assignee.team if src.assignee else "__unassigned__"
        tgt_team = tgt.assignee.team if tgt.assignee else "__unassigned__"
        if src_team == tgt_team:
            continue
        all_teams.add(src_team)
        all_teams.add(tgt_team)
        team_pairs[(src_team, tgt_team)].append(dep.is_blocking)

    teams = sorted(all_teams)
    cells: list[DependencyHeatCell] = []
    for (ft, tt), blocking_list in team_pairs.items():
        cells.append(
            DependencyHeatCell(
                from_team=ft,
                to_team=tt,
                count=len(blocking_list),
                blocked_count=sum(blocking_list),
            )
        )

    return cells, teams


def compute_capacity(
    snapshot: BoardSnapshot,
    capacity_per_person: float = 13.0,
) -> list[CapacityRow]:
    """Compare capacity vs commitment per team."""
    team_data: dict[str, dict[str, float]] = defaultdict(
        lambda: {"capacity": 0, "committed": 0, "in_prog": 0, "done": 0, "blocked": 0},
    )

    people_per_team: dict[str, set[str]] = defaultdict(set)
    for iss in snapshot.issues:
        if not iss.assignee:
            continue
        team = iss.assignee.team or "__no_team__"
        people_per_team[team].add(iss.assignee.display_name)
        team_data[team]["committed"] += iss.story_points
        if iss.is_done:
            team_data[team]["done"] += iss.story_points
        elif iss.is_blocked:
            team_data[team]["blocked"] += iss.story_points
        elif iss.is_in_progress:
            team_data[team]["in_prog"] += iss.story_points

    rows: list[CapacityRow] = []
    for team in sorted(team_data.keys()):
        d = team_data[team]
        cap = len(people_per_team[team]) * capacity_per_person
        util = (d["committed"] / cap * 100) if cap else 0.0
        status = "over" if util > 100 else ("under" if util < 60 else "balanced")
        rows.append(
            CapacityRow(
                team=team,
                capacity_sp=cap,
                committed_sp=d["committed"],
                in_progress_sp=d["in_prog"],
                done_sp=d["done"],
                blocked_sp=d["blocked"],
                utilization_pct=round(util, 1),
                status=status,
            )
        )
    return rows


def compute_ceremonies(
    issues: list[Issue],
    blockers: list[BlockerItem],
    sprint_goals: list[SprintGoalReport],
    scope_changes: list[ScopeChangeReport],
    readiness: ReadinessReport,
    capacity: list[CapacityRow],
    sprint_healths: list[SprintHealth] | None = None,
    today: date | None = None,
) -> dict[str, CeremonySummary]:
    """Pre-compute data for each Scrum ceremony."""
    from flowboard.domain.models import StatusCategory

    today = today or date.today()

    # Daily Scrum
    active_blocked = [b for b in blockers if b.severity in ("critical", "escalate")]
    aging = [
        GoalItem(
            key=i.key,
            summary=i.summary[:60],
            status=i.status_category.value,
            assignee=i.assignee.display_name if i.assignee else "__unassigned__",
            story_points=i.story_points,
            is_blocked=i.is_blocked,
            is_at_risk=True,
        )
        for i in issues
        if i.is_in_progress and (i.age_days or 0) > 7
    ][:10]

    daily = CeremonySummary(
        ceremony="daily",
        headline=f"daily:{len(active_blocked)}:{len(aging)}",
        metrics={
            "blockers": len(active_blocked),
            "aging_items": len(aging),
            "in_progress": sum(1 for i in issues if i.is_in_progress),
        },
        items=aging,
    )

    # Sprint Planning
    planning = CeremonySummary(
        ceremony="planning",
        headline=f"planning:{readiness.ready_count}:{readiness.not_ready_count}",
        metrics={
            "ready": readiness.ready_count,
            "not_ready": readiness.not_ready_count,
            "avg_readiness": readiness.avg_readiness,
            "teams_over": sum(1 for c in capacity if c.status == "over"),
        },
    )

    # Sprint Review
    active_goals = [g for g in sprint_goals if g.sprint_state == "active"]
    done_items = sum(g.completed for g in active_goals)
    total_items = sum(g.total_goal_items for g in active_goals)
    active_scope = [s for s in scope_changes if s.stability != "stable"]

    review = CeremonySummary(
        ceremony="review",
        headline=f"review:{done_items}:{total_items}",
        metrics={
            "goal_done": done_items,
            "goal_total": total_items,
            "scope_changes": sum(s.added_count for s in active_scope),
            "spillover": sum(
                1
                for i in issues
                if i.status_category == StatusCategory.IN_PROGRESS
                and i.sprint
                and i.sprint.state.value == "active"
            ),
        },
    )

    # Retrospective
    total_blocked = len(blockers)
    avg_churn = sum(s.churn_pct for s in scope_changes) / max(len(scope_changes), 1)
    retro = CeremonySummary(
        ceremony="retro",
        headline=f"retro:{total_blocked}:{avg_churn:.0f}",
        metrics={
            "total_blockers": total_blocked,
            "escalations": len([b for b in blockers if b.severity == "escalate"]),
            "avg_churn": avg_churn,
            "carryover": sum(sh.carry_over_count for sh in (sprint_healths or [])),
        },
    )

    return {"daily": daily, "planning": planning, "review": review, "retro": retro}


def compute_product_progress(
    issues: list[Issue],
    today: date | None = None,
) -> ProductProgressReport:
    """Product-level epic/initiative progress for POs."""
    from flowboard.domain.models import StatusCategory

    epic_data: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "title": "",
            "team": "",
            "total": 0,
            "done": 0,
            "in_prog": 0,
            "blocked": 0,
            "sp_total": 0.0,
            "sp_done": 0.0,
        },
    )

    for iss in issues:
        if not iss.epic_key:
            continue
        d = epic_data[iss.epic_key]
        if not d["title"]:
            d["title"] = iss.summary[:50]
            d["team"] = iss.assignee.team if iss.assignee else ""
        d["total"] += 1
        d["sp_total"] += iss.story_points
        if iss.status_category == StatusCategory.DONE:
            d["done"] += 1
            d["sp_done"] += iss.story_points
        elif iss.is_blocked:
            d["blocked"] += 1
        elif iss.status_category == StatusCategory.IN_PROGRESS:
            d["in_prog"] += 1

    epics: list[EpicProgress] = []
    for key, d in epic_data.items():
        total = d["total"]
        done_count = d["done"]
        pct = (done_count / total * 100) if total else 0.0
        if pct >= 100:
            status = "done"
        elif d["blocked"] > 0:
            status = "at_risk"
        elif pct < 30 and d["in_prog"] > 0:
            status = "slipping"
        else:
            status = "on_track"

        epics.append(
            EpicProgress(
                key=key,
                title=str(d["title"]),
                team=str(d["team"]),
                total_issues=total,
                done_issues=done_count,
                in_progress=d["in_prog"],
                blocked=d["blocked"],
                total_sp=d["sp_total"],
                done_sp=d["sp_done"],
                completion_pct=round(pct, 1),
                status=status,
            )
        )

    epics.sort(key=lambda e: -e.completion_pct)
    on_track = sum(1 for e in epics if e.status == "on_track")
    slipping = sum(1 for e in epics if e.status == "slipping")
    at_risk = sum(1 for e in epics if e.status == "at_risk")
    done = sum(1 for e in epics if e.status == "done")
    overall = sum(e.completion_pct for e in epics) / max(len(epics), 1)

    return ProductProgressReport(
        epics=epics,
        overall_completion=round(overall, 1),
        on_track=on_track,
        slipping=slipping,
        at_risk=at_risk,
        done=done,
    )
