"""Dependency and blocker analysis.

Provides functions to identify blocking chains, critical path dependencies,
and unresolved dependency summaries.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from flowboard.domain.models import Dependency, Issue, Sprint, SprintHealth
from flowboard.shared.types import LinkType, SprintState, StatusCategory

logger = logging.getLogger(__name__)


def find_blocked_issues(issues: list[Issue]) -> list[Issue]:
    """Return all non-done issues that are blocked by unresolved work."""
    return [i for i in issues if i.is_blocked and not i.is_done]


def find_blocking_issues(issues: list[Issue]) -> list[Issue]:
    """Return issues that are blocking other work (outward 'blocks' links)."""
    blocking_keys: set[str] = set()
    for issue in issues:
        for lnk in issue.links:
            if lnk.link_type == LinkType.IS_BLOCKED_BY and not lnk.is_resolved:
                blocking_keys.add(lnk.target_key)
    return [i for i in issues if i.key in blocking_keys and not i.is_done]


def build_dependency_chains(dependencies: list[Dependency]) -> list[list[str]]:
    """Identify chains of blocking dependencies (topological paths).

    Returns a list of chains where each chain is a list of issue keys
    forming a transitive blocking path.  Branching graphs produce one
    chain per root-to-leaf path.
    """
    graph: dict[str, list[str]] = defaultdict(list)
    for dep in dependencies:
        if (
            dep.link_type in (LinkType.BLOCKS, LinkType.IS_DEPENDED_ON_BY)
            and dep.target_status != StatusCategory.DONE
        ):
            graph[dep.source_key].append(dep.target_key)

    chains: list[list[str]] = []

    def _dfs(node: str, path: list[str], on_stack: set[str]) -> None:
        if node in on_stack:
            # Cycle detected — record the path so far and stop.
            if len(path) > 1:
                chains.append(list(path))
            return
        on_stack.add(node)
        path.append(node)
        neighbors = graph.get(node)
        if neighbors:
            for neighbor in neighbors:
                _dfs(neighbor, path, on_stack)
        else:
            # Leaf node — record the full root-to-leaf path.
            if len(path) > 1:
                chains.append(list(path))
        path.pop()
        on_stack.discard(node)

    roots = set(graph.keys()) - {t for targets in graph.values() for t in targets}
    if not roots:
        roots = set(graph.keys())
    for root in roots:
        _dfs(root, [], set())

    chains.sort(key=len, reverse=True)
    return chains


def dependency_summary_by_team(
    dependencies: list[Dependency],
    issues: list[Issue],
) -> dict[str, dict[str, int]]:
    """Summarize unresolved dependencies grouped by assignee team.

    Returns ``{team_key: {"blocked": N, "blocking": M}}``.
    """
    issue_map = {i.key: i for i in issues}
    result: dict[str, dict[str, int]] = defaultdict(lambda: {"blocked": 0, "blocking": 0})
    for dep in dependencies:
        if dep.target_status == StatusCategory.DONE:
            continue
        source = issue_map.get(dep.source_key)
        target = issue_map.get(dep.target_key)
        if source and source.assignee:
            team = source.assignee.team or "Unassigned"
            if dep.link_type in (LinkType.BLOCKS, LinkType.IS_DEPENDED_ON_BY):
                result[team]["blocking"] += 1
            else:
                result[team]["blocked"] += 1
        if target and target.assignee:
            team = target.assignee.team or "Unassigned"
            if dep.link_type in (LinkType.BLOCKS, LinkType.IS_DEPENDED_ON_BY):
                result[team]["blocked"] += 1
    return dict(result)


def compute_sprint_health(
    sprint_issues: dict[int, list[Issue]],
    sprints: list[Sprint],
    aging_days: int = 14,
    *,
    today: date | None = None,
) -> list[SprintHealth]:
    """Compute :class:`SprintHealth` for each sprint."""

    today = today or date.today()

    healths: list[SprintHealth] = []
    sprint_map = {s.id: s for s in sprints}
    for sid, issues in sprint_issues.items():
        sprint = sprint_map.get(sid)
        if not sprint:
            logger.warning("Sprint ID %s has issues but was not found in sprints list", sid)
            continue
        done = [i for i in issues if i.is_done]
        in_prog = [i for i in issues if i.is_in_progress]
        blocked = [i for i in issues if i.is_blocked and not i.is_done]
        todo = [i for i in issues if i.status_category == StatusCategory.TODO]
        aging = [i for i in issues if not i.is_done and (i.age_days or 0) > aging_days]

        by_type: dict[str, int] = defaultdict(int)
        by_assignee: dict[str, int] = defaultdict(int)
        total_sp = 0.0
        done_sp = 0.0
        for i in issues:
            by_type[i.issue_type] += 1
            if i.assignee:
                by_assignee[i.assignee.display_name] += 1
            total_sp += i.story_points
            if i.is_done:
                done_sp += i.story_points

        carry_over = 0
        if (
            sprint.state == SprintState.ACTIVE
            and sprint.end_date
            and (sprint.end_date - today).days <= 2
        ):
            carry_over = len(todo) + len(in_prog)

        healths.append(
            SprintHealth(
                sprint=sprint,
                total_issues=len(issues),
                done_issues=len(done),
                in_progress_issues=len(in_prog),
                todo_issues=len(todo),
                blocked_issues=len(blocked),
                total_points=total_sp,
                completed_points=done_sp,
                carry_over_count=carry_over,
                aging_issues=len(aging),
                by_type=dict(by_type),
                by_assignee=dict(by_assignee),
            )
        )
    return healths
