"""Chart data builders for the HTML dashboard.

Generates JSON-serializable data structures consumed by Chart.js
inside the rendered HTML.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING

from flowboard.domain.models import BoardSnapshot
from flowboard.shared.types import StatusCategory

if TYPE_CHECKING:
    from flowboard.i18n.translator import Translator

_STATUS_CAT_KEY = {"To Do": "todo", "In Progress": "in_progress", "Done": "done"}

_ISSUE_TYPE_KEY = {
    "Epic": "epic",
    "Story": "story",
    "Task": "task",
    "Bug": "bug",
    "Sub-task": "sub_task",
    "Other": "other",
}


def _sc_key(lbl: str) -> str:
    return _STATUS_CAT_KEY.get(lbl, "todo")


# Colorblind-safe palette (distinguishable under deuteranopia/protanopia).
PALETTE = [
    "#4F46E5",
    "#E8590C",
    "#0EA5E9",
    "#D946EF",
    "#059669",
    "#CA8A04",
    "#DC2626",
    "#6D28D9",
    "#0284C7",
    "#EA580C",
]

STATUS_COLORS = {
    StatusCategory.TODO: "#94A3B8",
    StatusCategory.IN_PROGRESS: "#3B82F6",
    StatusCategory.DONE: "#10B981",
}


def _json(obj: object) -> str:
    """JSON-serialize for safe embedding inside HTML <script> tags."""
    s = json.dumps(obj, default=str)
    # Escape characters that could break out of a <script> block or
    # interfere with HTML parsing — prevents stored XSS via Jira field values.
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def workload_chart_data(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Horizontal bar chart: story points per person."""
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    records = snapshot.workload_records[:20]  # top 20
    labels = [wr.person.display_name for wr in records]
    points = [wr.story_points for wr in records]
    issues = [wr.issue_count for wr in records]
    return _json(
        {
            "labels": labels,
            "datasets": [
                {"label": t("chart.story_points"), "data": points, "backgroundColor": "#4F46E5"},
                {"label": t("chart.issue_count"), "data": issues, "backgroundColor": "#94A3B8"},
            ],
        }
    )


def status_distribution_data(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Doughnut chart: issue count by status category."""
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    counts: dict[str, int] = defaultdict(int)
    for issue in snapshot.issues:
        counts[issue.status_category.value] += 1
    raw_labels = list(counts.keys())
    labels = [t(f"enum.status_category.{_sc_key(lbl)}") for lbl in raw_labels]
    values = list(counts.values())

    def _safe_color(lbl: str) -> str:
        try:
            return STATUS_COLORS.get(StatusCategory(lbl), "#94A3B8")
        except ValueError:
            return "#94A3B8"

    colors = [_safe_color(lbl) for lbl in raw_labels]
    return _json(
        {
            "labels": labels,
            "datasets": [{"data": values, "backgroundColor": colors}],
        }
    )


def type_distribution_data(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Doughnut chart: issue count by type."""
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    counts: dict[str, int] = defaultdict(int)
    for issue in snapshot.issues:
        counts[issue.issue_type.value] += 1
    raw_labels = list(counts.keys())
    labels = [t(f"enum.issue_type.{_ISSUE_TYPE_KEY.get(lbl, 'other')}") for lbl in raw_labels]
    values = list(counts.values())
    return _json(
        {
            "labels": labels,
            "datasets": [{"data": values, "backgroundColor": PALETTE[: len(labels)]}],
        }
    )


def sprint_progress_data(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Stacked bar chart: sprint completion by status category."""
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    labels = [sh.sprint.name for sh in snapshot.sprint_health]
    done = [sh.done_issues for sh in snapshot.sprint_health]
    in_prog = [sh.in_progress_issues for sh in snapshot.sprint_health]
    todo = [sh.todo_issues for sh in snapshot.sprint_health]
    return _json(
        {
            "labels": labels,
            "datasets": [
                {"label": t("chart.done"), "data": done, "backgroundColor": "#10B981"},
                {"label": t("chart.in_progress"), "data": in_prog, "backgroundColor": "#3B82F6"},
                {"label": t("chart.todo"), "data": todo, "backgroundColor": "#94A3B8"},
            ],
        }
    )


def team_workload_data(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Bar chart: story points per team."""
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    labels = [tw.team.name for tw in snapshot.team_workloads]
    points = [tw.total_story_points for tw in snapshot.team_workloads]
    return _json(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": t("chart.story_points"),
                    "data": points,
                    "backgroundColor": PALETTE[: len(labels)],
                },
            ],
        }
    )


def risk_severity_data(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    """Doughnut chart: risk signals by severity."""
    if t is None:
        from flowboard.i18n.translator import get_translator

        t = get_translator()
    counts: dict[str, int] = defaultdict(int)
    for rs in snapshot.risk_signals:
        counts[rs.severity.value] += 1
    sev_colors = {
        "critical": "#DC2626",
        "high": "#F59E0B",
        "medium": "#3B82F6",
        "low": "#10B981",
        "info": "#94A3B8",
    }
    raw_labels = list(counts.keys())
    labels = [t(f"enum.risk_severity.{lbl}") for lbl in raw_labels]
    values = list(counts.values())
    colors = [sev_colors.get(lbl, "#94A3B8") for lbl in raw_labels]
    return _json(
        {
            "labels": labels,
            "datasets": [{"data": values, "backgroundColor": colors}],
        }
    )
