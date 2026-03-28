"""Data quality checks for FlowBoard analysis pipeline.

Provides warnings for common data integrity issues in Jira data:
- Duplicate sprint detection across boards
- Team member presence validation
- Stale data detection
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from flowboard.domain.models import Issue
from flowboard.infrastructure.config.loader import FlowBoardConfig

_log = logging.getLogger(__name__)


def check_duplicate_sprints(sprints: list[dict[str, Any]]) -> list[str]:
    """Detect sprints appearing on multiple boards (may cause double-counting).

    Returns list of warning messages.
    """
    warnings: list[str] = []
    sprint_names: dict[str, list[int]] = {}
    for s in sprints:
        name = s.get("name", "")
        board_id = s.get("originBoardId", s.get("boardId", 0))
        if name:
            sprint_names.setdefault(name, []).append(board_id)

    for name, boards in sprint_names.items():
        unique = set(boards)
        if len(unique) > 1:
            msg = f"Sprint '{name}' appears on {len(unique)} boards: {sorted(unique)}. This may cause double-counting."
            _log.warning(msg)
            warnings.append(msg)

    return warnings


def check_team_member_presence(
    config: FlowBoardConfig,
    issues: list[Issue],
) -> list[str]:
    """Warn if configured team members don't appear in actual Jira data.

    Returns list of warning messages.
    """
    warnings: list[str] = []
    if not config.teams:
        return warnings

    # Collect all assignees from issues
    actual_assignees: set[str] = set()
    for issue in issues:
        if issue.assignee:
            actual_assignees.add(issue.assignee)

    for team in config.teams:
        missing = [m for m in team.members if m not in actual_assignees]
        if missing:
            msg = (
                f"Team '{team.name}': {len(missing)} configured member(s) not found in Jira data: "
                f"{', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}. "
                "Check display name spelling."
            )
            _log.warning(msg)
            warnings.append(msg)

    return warnings


def check_data_freshness(issues: list[Issue], max_age_days: int = 7) -> list[str]:
    """Warn if the most recent issue update is older than max_age_days."""
    warnings: list[str] = []
    if not issues:
        warnings.append("No issues found. Dashboard will be empty.")
        return warnings

    cutoff = date.today() - timedelta(days=max_age_days)
    recent_dates = [i.updated for i in issues if i.updated]
    if recent_dates:
        most_recent = max(recent_dates)
        if most_recent < cutoff:
            msg = f"Most recent issue update was {most_recent}, over {max_age_days} days ago. Data may be stale."
            _log.warning(msg)
            warnings.append(msg)

    return warnings
