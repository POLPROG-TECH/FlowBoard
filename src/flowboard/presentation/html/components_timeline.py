"""Timeline components: roadmap, PI, conflict list, and multi-mode timeline."""

from __future__ import annotations

from datetime import date

from flowboard.domain.models import OverlapConflict, RoadmapItem
from flowboard.domain.pi import PISnapshot
from flowboard.domain.timeline import TimelineData
from flowboard.i18n.translator import Translator, get_translator
from flowboard.presentation.html.components import _esc, _loc, _t, severity_badge
from flowboard.shared.utils import truncate_html

__all__ = [
    "_TL_OVERLAP_COLORS",
    "_TL_TYPE_COLORS",
    "_bar_width_pct",
    "_day_offset",
    "conflict_list",
    "pi_timeline_view",
    "roadmap_timeline",
    "timeline_view",
]


# ---------------------------------------------------------------------------
# Roadmap timeline
# ---------------------------------------------------------------------------


def roadmap_timeline(items: list[RoadmapItem], t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    if not items:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_roadmap")}</p>'
    rows = []
    for ri in items:
        pct = ri.progress_pct
        bar_cls = (
            "progress-fill-success"
            if pct >= 80
            else "progress-fill-warning"
            if pct >= 40
            else "progress-fill-danger"
        )
        start = t.format_date_short(ri.start_date) if ri.start_date else "—"
        target = t.format_date_short(ri.target_date) if ri.target_date else "—"
        owner = _esc(ri.owner.display_name) if ri.owner else "—"
        risk_badges = " ".join(severity_badge(r.severity, t) for r in ri.risk_signals[:3])
        rows.append(
            f"<tr>"
            f'<td class="cell-key"><strong>{_esc(ri.key)}</strong></td>'
            f"<td>{truncate_html(ri.title, 60)}</td>"
            f"<td>{_esc(ri.team) if ri.team else '—'}</td>"
            f"<td>{owner}</td>"
            f"<td>{start}</td>"
            f"<td>{target}</td>"
            f"<td>"
            f'<div class="progress-bar-sm" role="progressbar" aria-valuenow="{pct:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="{_esc(ri.key)} progress"><div class="progress-fill {bar_cls}" style="width:{pct:.0f}%"></div></div>'
            f'<span class="pct-label">{pct:.0f}%</span>'
            f"</td>"
            f"<td>{ri.done_count}/{ri.child_count}</td>"
            f"<td>{risk_badges}</td>"
            f"</tr>"
        )
    return (
        '<div class="table-scroll">'
        '<table class="data-table">'
        "<thead><tr>"
        f"<th>{_t(t, 'table.key')}</th><th>{_t(t, 'table.epic')}</th><th>{_t(t, 'table.team')}</th><th>{_t(t, 'table.owner')}</th>"
        f"<th>{_t(t, 'table.start')}</th><th>{_t(t, 'table.target')}</th><th>{_t(t, 'table.progress')}</th><th>{_t(t, 'table.done_total')}</th><th>{_t(t, 'table.risks')}</th>"
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# PI timeline view
# ---------------------------------------------------------------------------


def pi_timeline_view(
    pi: PISnapshot | None,
    roadmap_items: list[RoadmapItem] | None = None,
    t: Translator | None = None,
) -> str:
    """Render the PI timeline with sprint slots, today marker, and roadmap items."""
    if t is None:
        t = get_translator()
    if pi is None:
        return f'<p class="empty-state" role="status">{_t(t, "empty.pi_not_configured")}</p>'

    parts = ['<div class="pi-container">']

    # Header row
    cur = pi.sprints[pi.current_sprint_index - 1] if pi.current_sprint_index else None
    if pi.current_sprint_index and cur:
        remaining_label = t(
            "pi.working_days_left_sprint", days=cur.working_days_remaining, sprint=cur.name
        )
    else:
        remaining_label = t("empty.outside_pi_window")
    parts.append(
        f'<div class="pi-header">'
        f'<div class="pi-title"><strong>{_esc(pi.name)}</strong>'
        f' <span class="pi-dates">{_esc(t.format_date_short(pi.start_date))} – {_esc(t.format_date_full(pi.end_date))}</span></div>'
        f'<div class="pi-meta">'
        f'<span class="pi-progress-label">{_esc(t("pi.progress", pct=f"{pi.progress_pct:.0f}"))}</span>'
        f" · <span>{_esc(remaining_label)}</span>"
        f" · <span>{_esc(t('pi.working_days_left_pi', days=pi.remaining_working_days))}</span>"
        f"</div>"
        f'<div class="progress-bar" role="progressbar" aria-valuenow="{pi.progress_pct:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="PI progress"><div class="progress-fill" style="width:{pi.progress_pct:.0f}%;background:var(--primary)"></div></div>'
        f"</div>"
    )

    # Sprint slots
    parts.append('<div class="pi-sprint-grid">')
    for slot in pi.sprints:
        current_cls = "pi-sprint-current" if slot.is_current else ""
        pct = (
            (slot.working_days_elapsed / slot.working_days_total * 100)
            if slot.working_days_total
            else 0
        )
        bar_color = "var(--color-info)" if slot.is_current else "var(--color-muted)"
        current_chip = (
            f'<span class="chip chip-active">{_esc(t("sprint.current"))}</span>'
            if slot.is_current
            else ""
        )
        remaining_days = (
            f'<span class="pi-remaining">{slot.working_days_remaining} {_esc(t("sprint.days_left"))}</span>'
            if slot.is_current
            else ""
        )
        parts.append(
            f'<div class="pi-sprint-slot {current_cls}">'
            f'<div class="pi-sprint-header">'
            f"<strong>{_esc(slot.name)}</strong>"
            f"{current_chip}"
            f"</div>"
            f'<div class="pi-sprint-dates">{_esc(t.format_date_short(slot.start_date))} – {_esc(t.format_date_short(slot.end_date))}</div>'
            f'<div class="progress-bar" role="progressbar" aria-valuenow="{pct:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="{_esc(slot.name)} progress"><div class="progress-fill" style="width:{pct:.0f}%;background:{bar_color}"></div></div>'
            f'<div class="pi-sprint-stats">'
            f"<span>{slot.working_days_elapsed}/{slot.working_days_total} {_esc(t('pi.days'))}</span>"
            f"{remaining_days}"
            f"</div>"
            f"</div>"
        )
    parts.append("</div>")

    # Roadmap items aligned to PI
    if roadmap_items:
        parts.append(
            f'<h3 class="section-title section-title-spaced">{_t(t, "pi.epics_in_window")}</h3>'
        )
        parts.append(roadmap_timeline(roadmap_items, t=t))

    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Overlap / conflict list
# ---------------------------------------------------------------------------


def conflict_list(conflicts: list[OverlapConflict], t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    if not conflicts:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_conflicts")}</p>'
    parts = ['<div class="conflict-list">']
    for c in conflicts:
        parts.append(
            f'<div class="conflict-item">'
            f"{severity_badge(c.severity, t)} "
            f'<span class="conflict-cat">{_esc(t("conflict." + c.category))}</span> '
            f'<span class="conflict-desc">{_esc(c.description)}</span>'
            f'<div class="conflict-rec">💡 {_esc(c.recommendation)}</div>'
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


# Colors for timeline bars per issue type (theme-safe palette)
_TL_TYPE_COLORS = {
    "Epic": "var(--primary)",
    "Story": "var(--color-info)",
    "Task": "var(--color-task, #8B5CF6)",
    "Bug": "var(--color-danger)",
    "Sub-task": "var(--color-subtask, #6366F1)",
    "Other": "var(--color-muted)",
}

_TL_OVERLAP_COLORS = {
    "medium": "rgba(245,158,11,0.18)",
    "high": "rgba(239,68,68,0.18)",
    "critical": "rgba(220,38,38,0.25)",
}


def _day_offset(start: date, d: date, total_days: int) -> float:
    """Compute a bar's left % relative to the timeline's date range."""
    if total_days <= 0:
        return 0.0
    return max(0.0, min(100.0, ((d - start).days / total_days) * 100))


def _bar_width_pct(start: date, end: date, total_days: int) -> float:
    """Compute a bar's width % relative to the timeline's date range."""
    if total_days <= 0:
        return 1.0
    span = (end - start).days
    return max(1.5, min(100.0, (span / total_days) * 100))


def _next_month(d: date) -> date:
    """Advance a date to the first day of the next month."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


def _render_overlap_zones(
    data: TimelineData,
    lane_key: str,
    total_days: int,
    parts: list[str],
) -> None:
    """Render overlap highlight zones for a single swimlane."""
    for ov in data.overlaps:
        if ov.swimlane_key != lane_key:
            continue
        ov_left = _day_offset(data.range_start, ov.start, total_days)
        ov_width = _bar_width_pct(ov.start, ov.end, total_days)
        ov_color = _TL_OVERLAP_COLORS.get(ov.severity, _TL_OVERLAP_COLORS["medium"])
        parts.append(
            f'<div class="tl-overlap-zone" style="left:{ov_left:.1f}%;width:{ov_width:.1f}%;background:{ov_color}"></div>'
        )


def _render_timeline_bar(
    bar: object,
    data: TimelineData,
    total_days: int,
    t: Translator,
    parts: list[str],
) -> None:
    """Render a single work-item bar in the timeline."""
    left = _day_offset(data.range_start, bar.start, total_days)
    width = _bar_width_pct(bar.start, bar.end, total_days)
    color = _TL_TYPE_COLORS.get(bar.issue_type, _TL_TYPE_COLORS["Other"])

    extra_cls = ""
    if bar.is_blocked:
        extra_cls = " tl-bar-blocked"
    elif bar.is_done:
        extra_cls = " tl-bar-done"

    progress_style = f"width:{bar.progress_pct:.0f}%" if bar.progress_pct > 0 else "width:0"

    tooltip_parts = [f"{bar.key}: {bar.label}"]
    if bar.story_points:
        tooltip_parts.append(f"({bar.story_points:.0f} {_esc(t('unit.sp'))})")
    if bar.sprint_name:
        tooltip_parts.append(f"[{bar.sprint_name}]")
    tooltip = " ".join(tooltip_parts)

    data_attrs = (
        f' data-tl-key="{_esc(bar.key)}"'
        f' data-tl-title="{_esc(bar.label)}"'
        f' data-tl-type="{_esc(bar.issue_type)}"'
        f' data-tl-assignee="{_esc(_loc(bar.assignee, t))}"'
        f' data-tl-team="{_esc(_loc(bar.team, t))}"'
        f' data-tl-start="{bar.start.isoformat()}"'
        f' data-tl-end="{bar.end.isoformat()}"'
        f' data-tl-progress="{bar.progress_pct:.0f}"'
        f' data-tl-blocked="{str(bar.is_blocked).lower()}"'
    )
    if bar.story_points:
        data_attrs += f' data-tl-sp="{bar.story_points:.0f}"'
    if bar.sprint_name:
        data_attrs += f' data-tl-sprint="{_esc(bar.sprint_name)}"'
    if bar.priority:
        data_attrs += f' data-tl-priority="{_esc(bar.priority)}"'
    if bar.epic_key:
        data_attrs += f' data-tl-epic="{_esc(bar.epic_key)}"'

    status = (
        t("enum.status.done")
        if bar.is_done
        else (t("enum.status.blocked") if bar.is_blocked else t("enum.status.in_progress"))
    )
    data_attrs += f' data-tl-status="{_esc(status)}"'

    label_cls = " tl-bar-label-hidden" if width < 2.5 else ""

    parts.append(
        f'<div class="tl-bar{extra_cls}" style="left:{left:.1f}%;width:{width:.1f}%;--bar-color:{color}" title="{_esc(tooltip)}"{data_attrs} tabindex="0" role="button">'
        f'<div class="tl-bar-progress" style="{progress_style}"></div>'
        f'<span class="tl-bar-label{label_cls}">{_esc(bar.key)}</span>'
        f"</div>"
    )


def timeline_view(
    timelines: dict[str, TimelineData],
    *,
    default_mode: str = "assignee",
    max_swimlanes: int = 30,
    show_overlaps: bool = True,
    show_sprint_bounds: bool = True,
    show_today: bool = True,
    compact: bool = False,
    has_simulation: bool = False,
    t: Translator | None = None,
) -> str:
    """Render the complete multi-mode timeline component."""
    if t is None:
        t = get_translator()

    if not timelines:
        return f'<p class="empty-state" role="status">{_t(t, "timeline.no_data")}</p>'

    parts: list[str] = []

    # Mode switcher buttons
    mode_labels = {
        "assignee": t("timeline.mode_assignee"),
        "team": t("timeline.mode_team"),
        "epic": t("timeline.mode_epic"),
        "roadmap": t("timeline.mode_roadmap"),
        "conflict": t("timeline.mode_conflict"),
        "executive": t("timeline.mode_executive"),
    }
    parts.append('<div class="tl-mode-bar">')
    for mode_key, label in mode_labels.items():
        if mode_key not in timelines:
            continue
        active_cls = " tl-mode-active" if mode_key == default_mode else ""
        parts.append(
            f'<button class="tl-mode-btn{active_cls}" data-tl-mode="{mode_key}">{_esc(label)}</button>'
        )
    if has_simulation:
        sim_label = t("timeline.mode_simulation")
        parts.append(
            f'<button class="tl-mode-btn tl-mode-sim" data-tl-mode="simulation">'
            f"🔬 {_esc(sim_label)}</button>"
        )
    parts.append("</div>")

    # Filter input with result count display
    parts.append(
        f'<div class="tl-filter-row">'
        f'<input type="text" class="tl-filter-input" id="tlFilter" placeholder="{_esc(t("timeline.filter_placeholder"))}" aria-label="{_esc(t("timeline.filter_placeholder"))}" oninput="filterTimeline()">'
        f'<span id="tlFilterStatus" class="tl-filter-status" aria-live="polite"></span>'
        f"</div>"
    )

    # Render each mode's timeline panel
    for mode_key, data in timelines.items():
        display = "block" if mode_key == default_mode else "none"
        parts.append(f'<div class="tl-panel" id="tlPanel-{mode_key}" style="display:{display}">')

        if not data.swimlanes:
            empty_key = "timeline.no_conflicts" if mode_key == "conflict" else "timeline.no_data"
            parts.append(f'<p class="empty-state" role="status">{_t(t, empty_key)}</p>')
            parts.append("</div>")
            continue

        total_days = data.total_days or 1
        today = date.today()
        lanes = data.swimlanes[:max_swimlanes]

        # Legend
        parts.append('<div class="tl-legend">')
        parts.append(
            f'<span class="tl-legend-item"><span class="tl-legend-swatch"></span> {_esc(t("timeline.legend_bar"))}</span>'
        )
        if show_overlaps:
            parts.append(
                f'<span class="tl-legend-item"><span class="tl-legend-swatch tl-legend-overlap"></span> {_esc(t("timeline.legend_overlap"))}</span>'
            )
        if show_sprint_bounds and data.sprint_boundaries:
            parts.append(
                f'<span class="tl-legend-item"><span class="tl-legend-swatch tl-legend-sprint"></span> {_esc(t("timeline.legend_sprint"))}</span>'
            )
        if show_today:
            parts.append(
                f'<span class="tl-legend-item"><span class="tl-legend-swatch tl-legend-today"></span> {_esc(t("timeline.legend_today"))}</span>'
            )
        parts.append("</div>")

        # Timeline container
        compact_cls = " tl-compact" if compact else ""
        parts.append(f'<div class="tl-container{compact_cls}">')

        # Time axis header
        parts.append('<div class="tl-header">')
        parts.append('<div class="tl-label-col"></div>')
        parts.append('<div class="tl-axis">')
        # Generate month markers
        current = data.range_start.replace(day=1)
        while current <= data.range_end:
            left = _day_offset(data.range_start, current, total_days)
            month_label = t.format_month_year(current)
            parts.append(
                f'<span class="tl-month-mark" style="left:{left:.1f}%">{_esc(month_label)}</span>'
            )
            current = _next_month(current)
        parts.append("</div>")  # /tl-axis
        parts.append("</div>")  # /tl-header

        # Sprint boundaries
        if show_sprint_bounds:
            for sp_name, sp_start, sp_end in data.sprint_boundaries:
                left = _day_offset(data.range_start, sp_start, total_days)
                width = _bar_width_pct(sp_start, sp_end, total_days)
                parts.append(
                    f'<div class="tl-sprint-band" style="left:calc(180px + {left:.1f}% * (100% - 180px) / 100);'
                    f'width:calc({width:.1f}% * (100% - 180px) / 100)" title="{_esc(sp_name)}"></div>'
                )

        # Swimlanes
        for lane in lanes:
            parts.append(f'<div class="tl-row" data-tl-lane="{_esc(lane.key)}">')

            # Label column
            overlap_badge = ""
            if lane.overlap_count > 0:
                overlap_badge = f' <span class="tl-overlap-badge">{lane.overlap_count}</span>'
            sp_label = (
                f' <span class="tl-sp-label">{lane.total_points:.0f} {_esc(t("unit.sp"))}</span>'
                if lane.total_points
                else ""
            )
            parts.append(
                f'<div class="tl-label-col" title="{_esc(_loc(lane.label, t))}">'
                f'<span class="tl-lane-name">{_esc(_loc(lane.label, t))}</span>'
                f"{overlap_badge}{sp_label}"
                f"</div>"
            )

            # Bar area
            parts.append('<div class="tl-bar-area">')

            # Today marker
            if show_today and data.range_start <= today <= data.range_end:
                today_left = _day_offset(data.range_start, today, total_days)
                parts.append(f'<div class="tl-today-line" style="left:{today_left:.1f}%"></div>')

            # Vertical month grid lines for visual alignment
            grid_month = data.range_start.replace(day=1)
            if grid_month < data.range_start:
                grid_month = _next_month(grid_month)
            while grid_month <= data.range_end:
                gl_left = _day_offset(data.range_start, grid_month, total_days)
                parts.append(f'<div class="tl-month-grid-line" style="left:{gl_left:.1f}%"></div>')
                grid_month = _next_month(grid_month)

            # Overlap highlights
            if show_overlaps:
                _render_overlap_zones(data, lane.key, total_days, parts)

            # Work item bars
            for bar in lane.bars:
                _render_timeline_bar(bar, data, total_days, t, parts)

            parts.append("</div>")  # /tl-bar-area
            parts.append("</div>")  # /tl-row

        parts.append("</div>")  # /tl-container
        parts.append("</div>")  # /tl-panel

    return "\n".join(parts)
