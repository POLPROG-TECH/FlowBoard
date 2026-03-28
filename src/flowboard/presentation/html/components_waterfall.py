"""Waterfall UI components — phases, milestones, critical path.

Renders HTML fragments for the Waterfall methodology dashboard tabs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from markupsafe import escape

if TYPE_CHECKING:
    from flowboard.domain.waterfall_models import WaterfallInsights
    from flowboard.i18n.translator import Translator


def _status_class(status: str) -> str:
    """Map phase/milestone status to CSS class."""
    return {
        "completed": "status-done",
        "on_track": "status-good",
        "at_risk": "status-warn",
        "delayed": "status-danger",
        "missed": "status-danger",
        "upcoming": "status-neutral",
    }.get(status, "")


def _status_icon(status: str) -> str:
    return {
        "completed": "✅",
        "on_track": "🟢",
        "at_risk": "🟡",
        "delayed": "🔴",
        "missed": "❌",
        "upcoming": "⏳",
    }.get(status, "⚪")


# ---------------------------------------------------------------------------
# Phase Progress Cards
# ---------------------------------------------------------------------------


def phase_progress_cards(insights: WaterfallInsights | None, *, t: Translator) -> str:
    """Render phase progress summary cards."""
    if insights is None:
        return (
            '<div class="empty-state">'
            + str(escape(t("waterfall.no_data", fallback="No Waterfall data available")))
            + "</div>"
        )

    pp = insights.phase_progress
    cards = [
        (
            t("waterfall.overall_progress", fallback="Overall Progress"),
            f"{pp.overall_progress_pct:.0f}%",
            "progress",
        ),
        (
            t("waterfall.current_phase", fallback="Current Phase"),
            pp.current_phase or "—",
            "current",
        ),
        (
            t("waterfall.phases_completed", fallback="Phases Completed"),
            f"{pp.completed_phases}/{pp.total_phases}",
            "completed",
        ),
        (t("waterfall.on_track", fallback="On Track"), str(pp.on_track), "good"),
        (
            t("waterfall.at_risk", fallback="At Risk"),
            str(pp.at_risk),
            "warn" if pp.at_risk > 0 else "",
        ),
        (
            t("waterfall.delayed", fallback="Delayed"),
            str(pp.delayed),
            "danger" if pp.delayed > 0 else "",
        ),
    ]

    parts = ['<div class="kanban-metrics-grid">']
    for label, value, css_class in cards:
        parts.append(
            f'<div class="metric-card {escape(css_class)}">'
            f'<span class="metric-label">{escape(label)}</span>'
            f'<span class="metric-value">{escape(value)}</span>'
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Phase Table
# ---------------------------------------------------------------------------


def phase_table(insights: WaterfallInsights | None, *, t: Translator) -> str:
    """Render a table of all phases with progress bars."""
    if insights is None or not insights.phases:
        return (
            '<div class="empty-state">'
            + str(escape(t("waterfall.no_phases", fallback="No phases detected")))
            + "</div>"
        )

    parts = ['<div class="table-scroll">']
    parts.append('<table class="data-table phase-table">')
    parts.append("<thead><tr>")
    for col in [
        t("waterfall.phase", fallback="Phase"),
        t("waterfall.status", fallback="Status"),
        t("waterfall.progress", fallback="Progress"),
        t("waterfall.issues", fallback="Issues"),
        t("waterfall.blocked", fallback="Blocked"),
    ]:
        parts.append(f"<th>{escape(col)}</th>")
    parts.append("</tr></thead><tbody>")

    for phase in insights.phases:
        status_cls = _status_class(phase.status)
        parts.append(
            f"<tr>"
            f"<td><strong>{escape(phase.name)}</strong></td>"
            f'<td><span class="chip {status_cls}">{_status_icon(phase.status)} {escape(phase.status.replace("_", " ").title())}</span></td>'
            f"<td>"
            f'<div class="wip-bar-track"><div class="wip-bar-fill" style="width:{phase.progress_pct:.0f}%"></div></div>'
            f"<span>{phase.progress_pct:.0f}%</span>"
            f"</td>"
            f"<td>{phase.done_issues}/{phase.total_issues}</td>"
            f"<td>{phase.blocked_issues}</td>"
            f"</tr>"
        )

    parts.append("</tbody></table></div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Milestone Timeline
# ---------------------------------------------------------------------------


def milestone_timeline(insights: WaterfallInsights | None, *, t: Translator) -> str:
    """Render milestone list with status indicators."""
    if insights is None or not insights.milestones:
        return (
            '<div class="empty-state">'
            + str(escape(t("waterfall.no_milestones", fallback="No milestones detected")))
            + "</div>"
        )

    parts = ['<div class="milestone-list">']
    for ms in insights.milestones:
        status_cls = _status_class(ms.status)
        date_str = ms.target_date.isoformat() if ms.target_date else "—"
        parts.append(
            f'<div class="milestone-item {status_cls}">'
            f'<span class="milestone-icon">{_status_icon(ms.status)}</span>'
            f'<div class="milestone-info">'
            f'<span class="milestone-name">{escape(ms.name)}</span>'
            f'<span class="milestone-date">{escape(date_str)}</span>'
            f"</div>"
            f'<span class="milestone-status">{escape(ms.status.replace("_", " ").title())}</span>'
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Critical Path Table
# ---------------------------------------------------------------------------


def critical_path_table(insights: WaterfallInsights | None, *, t: Translator) -> str:
    """Render critical path items."""
    if insights is None or not insights.critical_path:
        return (
            '<div class="empty-state">'
            + str(escape(t("waterfall.no_critical_path", fallback="No critical path items")))
            + "</div>"
        )

    parts = ['<div class="table-scroll">']
    parts.append('<table class="data-table">')
    parts.append("<thead><tr>")
    for col in [
        t("table.key", fallback="Key"),
        t("table.summary", fallback="Summary"),
        t("waterfall.phase", fallback="Phase"),
        t("waterfall.slack", fallback="Slack"),
        t("table.assignee", fallback="Assignee"),
        t("waterfall.critical", fallback="Critical"),
    ]:
        parts.append(f"<th>{escape(col)}</th>")
    parts.append("</tr></thead><tbody>")

    for item in insights.critical_path:
        critical_cls = "risk-high" if item.is_critical else ""
        parts.append(
            f'<tr class="{critical_cls}">'
            f'<td class="mono">{escape(item.key)}</td>'
            f"<td>{escape(item.summary[:60])}</td>"
            f"<td>{escape(item.phase)}</td>"
            f"<td>{item.slack_days}d</td>"
            f"<td>{escape(item.assignee)}</td>"
            f"<td>{'🔴' if item.is_critical else '⚪'}</td>"
            f"</tr>"
        )

    parts.append("</tbody></table></div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Full Phases Tab HTML
# ---------------------------------------------------------------------------


def phases_tab_html(insights: WaterfallInsights | None, *, t: Translator) -> str:
    """Render the complete Phases tab content for Waterfall methodology."""
    parts = []

    # Phase progress summary
    parts.append('<section class="section" id="phase-progress">')
    parts.append(
        f'<h3 class="section-title">{escape(t("waterfall.phase_progress", fallback="Phase Progress"))}</h3>'
    )
    parts.append(phase_progress_cards(insights, t=t))
    parts.append("</section>")

    # Phase table
    parts.append('<section class="section" id="phase-details">')
    parts.append(
        f'<h3 class="section-title">{escape(t("waterfall.phases", fallback="Phases"))}</h3>'
    )
    parts.append(phase_table(insights, t=t))
    parts.append("</section>")

    # Milestones
    parts.append('<section class="section" id="milestones">')
    parts.append(
        f'<h3 class="section-title">{escape(t("waterfall.milestones", fallback="Milestones"))}</h3>'
    )
    parts.append(milestone_timeline(insights, t=t))
    parts.append("</section>")

    # Critical path
    parts.append('<section class="section" id="critical-path">')
    parts.append(
        f'<h3 class="section-title">{escape(t("waterfall.critical_path", fallback="Critical Path"))}</h3>'
    )
    parts.append(critical_path_table(insights, t=t))
    parts.append("</section>")

    return "\n".join(parts)
