"""Kanban UI components — flow metrics, WIP monitor, cycle time, throughput, CFD.

Renders HTML fragments for the Kanban methodology dashboard tabs.
All functions return safe HTML strings (pre-escaped).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from markupsafe import escape

if TYPE_CHECKING:
    from flowboard.domain.kanban_models import KanbanInsights
    from flowboard.i18n.translator import Translator


def _fmt(val: float, decimals: int = 1) -> str:
    """Format a float for display."""
    if decimals == 0:
        return str(int(val))
    return f"{val:.{decimals}f}"


# ---------------------------------------------------------------------------
# Flow Metrics Summary Cards
# ---------------------------------------------------------------------------


def flow_metrics_cards(insights: KanbanInsights | None, *, t: Translator) -> str:
    """Render Kanban-specific summary cards for the Flow tab."""
    if insights is None:
        return (
            '<div class="empty-state">'
            + str(escape(t("kanban.no_data", fallback="No Kanban data available")))
            + "</div>"
        )

    fm = insights.flow_metrics
    def _safe_fmt(template: str, **kwargs: object) -> str:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template

    cards = [
        (
            t("kanban.avg_cycle_time", fallback="Avg Cycle Time"),
            f"{_fmt(fm.avg_cycle_time)}d",
            "cycle-time",
            _safe_fmt(
                t("kanban.median_val", fallback="Median: {val}d"),
                val=_fmt(fm.median_cycle_time),
            ),
        ),
        (
            t("kanban.throughput", fallback="Throughput"),
            f"{_fmt(fm.throughput_per_week)}/wk",
            "throughput",
            t("kanban.items_per_week", fallback="items per week"),
        ),
        (
            t("kanban.wip", fallback="WIP"),
            str(fm.current_wip),
            "wip" + (" wip-over" if fm.current_wip > fm.wip_limit else ""),
            _safe_fmt(t("kanban.wip_limit_val", fallback="Limit: {val}"), val=fm.wip_limit),
        ),
        (
            t("kanban.flow_efficiency", fallback="Flow Efficiency"),
            f"{_fmt(fm.flow_efficiency * 100, 0)}%",
            "efficiency",
            t("kanban.active_vs_wait", fallback="active vs. wait time"),
        ),
        (
            t("kanban.p85_cycle_time", fallback="P85 Cycle Time"),
            f"{_fmt(fm.p85_cycle_time)}d",
            "p85",
            t("kanban.sla_target", fallback="SLA target reference"),
        ),
        (
            t("kanban.wip_violations", fallback="WIP Violations"),
            str(fm.wip_violations),
            "violations" + (" risk-high" if fm.wip_violations > 0 else ""),
            t("kanban.people_over_limit", fallback="people over WIP limit"),
        ),
    ]

    parts = ['<div class="kanban-metrics-grid">']
    for label, value, css_class, subtitle in cards:
        parts.append(
            f'<div class="metric-card {escape(css_class)}">'
            f'<span class="metric-label">{escape(label)}</span>'
            f'<span class="metric-value">{escape(value)}</span>'
            f'<span class="metric-sub">{escape(subtitle)}</span>'
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# WIP Monitor
# ---------------------------------------------------------------------------


def wip_monitor(insights: KanbanInsights | None, *, t: Translator) -> str:
    """Render WIP breakdown by person with limit indicator."""
    if insights is None:
        return ""

    wip = insights.wip_snapshot
    fm = insights.flow_metrics
    if not wip.wip_by_person:
        return (
            '<div class="empty-state">'
            + str(escape(t("kanban.no_wip", fallback="No work in progress")))
            + "</div>"
        )

    sorted_people = sorted(wip.wip_by_person.items(), key=lambda x: x[1], reverse=True)

    parts = ['<div class="wip-monitor">']
    parts.append(f"<h4>{escape(t('kanban.wip_by_person', fallback='WIP by Person'))}</h4>")
    parts.append('<div class="wip-bars">')

    for person, count in sorted_people:
        pct = min(100, (count / max(fm.wip_limit, 1)) * 100)
        over = " over-limit" if count > fm.wip_limit else ""
        parts.append(
            f'<div class="wip-row">'
            f'<span class="wip-person">{escape(person)}</span>'
            f'<div class="wip-bar-track">'
            f'<div class="wip-bar-fill{over}" style="width:{pct:.0f}%"></div>'
            f'<span class="wip-bar-limit" style="left:{min(100, (fm.wip_limit / max(count, fm.wip_limit, 1)) * 100):.0f}%"></span>'
            f"</div>"
            f'<span class="wip-count{over}">{count}</span>'
            f"</div>"
        )

    parts.append("</div></div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Cycle Time Table
# ---------------------------------------------------------------------------


def cycle_time_table(insights: KanbanInsights | None, *, t: Translator, max_rows: int = 20) -> str:
    """Render recently completed items with their cycle/lead times."""
    if insights is None or not insights.cycle_times:
        return (
            '<div class="empty-state">'
            + str(escape(t("kanban.no_completed", fallback="No completed items")))
            + "</div>"
        )

    parts = ['<div class="table-scroll">']
    parts.append('<table class="data-table cycle-time-table">')
    parts.append("<thead><tr>")
    for col in [
        t("table.key", fallback="Key"),
        t("table.summary", fallback="Summary"),
        t("kanban.cycle_time", fallback="Cycle Time"),
        t("kanban.lead_time", fallback="Lead Time"),
        t("table.type", fallback="Type"),
        t("table.assignee", fallback="Assignee"),
    ]:
        parts.append(f"<th>{escape(col)}</th>")
    parts.append("</tr></thead><tbody>")

    for rec in insights.cycle_times[:max_rows]:
        parts.append(
            f"<tr>"
            f'<td class="mono">{escape(rec.key)}</td>'
            f"<td>{escape(rec.summary[:60])}</td>"
            f"<td>{_fmt(rec.cycle_time_days)}d</td>"
            f"<td>{_fmt(rec.lead_time_days)}d</td>"
            f"<td>{escape(rec.issue_type)}</td>"
            f"<td>{escape(rec.assignee)}</td>"
            f"</tr>"
        )

    parts.append("</tbody></table></div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Throughput Chart Data (JSON for Chart.js)
# ---------------------------------------------------------------------------


def throughput_chart_data(insights: KanbanInsights | None, *, t: Translator) -> str:
    """Return JSON for a throughput trend line chart."""
    if insights is None or not insights.throughput:
        return "null"

    labels = [rec.period_start.isoformat() for rec in insights.throughput]
    counts = [rec.count for rec in insights.throughput]
    points = [rec.story_points for rec in insights.throughput]

    data = {
        "labels": labels,
        "datasets": [
            {
                "label": str(t("kanban.items_completed", fallback="Items Completed")),
                "data": counts,
                "borderColor": "var(--primary)",
                "fill": False,
            },
            {
                "label": str(t("kanban.story_points", fallback="Story Points")),
                "data": points,
                "borderColor": "var(--secondary)",
                "fill": False,
            },
        ],
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# CFD Chart Data (JSON for Chart.js)
# ---------------------------------------------------------------------------


def cfd_chart_data(insights: KanbanInsights | None, *, t: Translator) -> str:
    """Return JSON for a cumulative flow diagram (stacked area chart)."""
    if insights is None or not insights.cfd_data:
        return "null"

    labels = [pt.date.isoformat() for pt in insights.cfd_data]
    done = [pt.done for pt in insights.cfd_data]
    in_progress = [pt.in_progress for pt in insights.cfd_data]
    todo = [pt.todo for pt in insights.cfd_data]

    data = {
        "labels": labels,
        "datasets": [
            {
                "label": str(t("chart.done", fallback="Done")),
                "data": done,
                "backgroundColor": "rgba(34,197,94,0.3)",
                "borderColor": "#22c55e",
                "fill": True,
            },
            {
                "label": str(t("chart.in_progress", fallback="In Progress")),
                "data": in_progress,
                "backgroundColor": "rgba(59,130,246,0.3)",
                "borderColor": "#3b82f6",
                "fill": True,
            },
            {
                "label": str(t("chart.todo", fallback="To Do")),
                "data": todo,
                "backgroundColor": "rgba(156,163,175,0.2)",
                "borderColor": "#9ca3af",
                "fill": True,
            },
        ],
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Full Flow Tab HTML
# ---------------------------------------------------------------------------


def flow_tab_html(insights: KanbanInsights | None, *, t: Translator) -> str:
    """Render the complete Flow tab content for Kanban methodology."""
    parts = []

    # Flow metrics cards
    parts.append('<section class="section" id="flow-metrics">')
    parts.append(
        f'<h3 class="section-title">{escape(t("kanban.flow_metrics", fallback="Flow Metrics"))}</h3>'
    )
    parts.append(flow_metrics_cards(insights, t=t))
    parts.append("</section>")

    # WIP Monitor
    parts.append('<section class="section" id="wip-monitor">')
    parts.append(
        f'<h3 class="section-title">{escape(t("kanban.wip_monitor", fallback="WIP Monitor"))}</h3>'
    )
    parts.append(wip_monitor(insights, t=t))
    parts.append("</section>")

    # Charts placeholder (rendered client-side by Chart.js)
    parts.append('<section class="section" id="flow-charts">')
    parts.append(
        f'<h3 class="section-title">{escape(t("kanban.flow_charts", fallback="Flow Charts"))}</h3>'
    )
    parts.append('<div class="charts-grid">')
    parts.append(
        '<div class="chart-card">'
        f"<h4>{escape(t('kanban.throughput_trend', fallback='Throughput Trend'))}</h4>"
        '<canvas id="throughputChart"></canvas>'
        "</div>"
    )
    parts.append(
        '<div class="chart-card">'
        f"<h4>{escape(t('kanban.cfd', fallback='Cumulative Flow Diagram'))}</h4>"
        '<canvas id="cfdChart"></canvas>'
        "</div>"
    )
    parts.append("</div></section>")

    # Cycle time table
    parts.append('<section class="section" id="cycle-times">')
    parts.append(
        f'<h3 class="section-title">{escape(t("kanban.recent_completions", fallback="Recent Completions"))}</h3>'
    )
    parts.append(cycle_time_table(insights, t=t))
    parts.append("</section>")

    return "\n".join(parts)
