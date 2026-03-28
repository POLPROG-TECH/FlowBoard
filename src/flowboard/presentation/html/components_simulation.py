"""Capacity simulation / what-if planning component."""

from __future__ import annotations

from datetime import date

from flowboard.domain.timeline import TimelineData
from flowboard.i18n.translator import Translator, get_translator
from flowboard.presentation.html.components import SEVERITY_BADGE, _esc, _loc, _t
from flowboard.presentation.html.components_timeline import (
    _TL_OVERLAP_COLORS,
    _TL_TYPE_COLORS,
    _bar_width_pct,
    _day_offset,
)

__all__ = [
    "_render_mini_timeline",
    "simulation_view",
]


# ---------------------------------------------------------------------------
# Capacity Simulation view
# ---------------------------------------------------------------------------


def simulation_view(
    simulation: object | None,
    *,
    t: Translator | None = None,
) -> str:
    """Render the complete capacity simulation / what-if planning component.

    The ``simulation`` parameter is a ``SimulationSuite`` from the domain layer.
    All interactive scenario switching happens client-side via embedded JSON.
    """
    if t is None:
        t = get_translator()

    if simulation is None:
        return f'<p class="empty-state" role="status">{_t(t, "sim.no_scenarios")}</p>'

    from flowboard.domain.simulation import SimulationSuite

    sim: SimulationSuite = simulation  # type: ignore[assignment]

    if not sim.scenarios:
        return f'<p class="empty-state" role="status">{_t(t, "sim.no_scenarios")}</p>'

    parts: list[str] = []

    # Disclaimer banner
    parts.append(
        '<div class="sim-disclaimer">'
        f'<span class="sim-disclaimer-icon">ℹ️</span> {_esc(t("sim.disclaimer"))}'
        "</div>"
    )

    # ── Best Next Hire card ──
    if sim.best_hire_team:
        best_impact = next(
            (ti for ti in sim.team_impacts if ti.team_key == sim.best_hire_team), None
        )
        score = best_impact.impact_score if best_impact else 0
        parts.append(
            '<div class="sim-best-hire">'
            f'<div class="sim-best-hire-header">'
            f'<span class="sim-best-hire-icon">🎯</span>'
            f"<h3>{_esc(t('sim.best_hire'))}</h3>"
            f"</div>"
            f'<p class="sim-best-hire-question">{_esc(t("sim.best_hire_desc"))}</p>'
            f'<div class="sim-best-hire-answer">'
            f'<span class="sim-best-hire-team">{_esc(sim.best_hire_team.upper())}</span>'
            f'<span class="sim-best-hire-score">{_esc(t("sim.impact_score"))}: {score:.0f}/100</span>'
            f"</div>"
            f'<p class="sim-best-hire-reason">{_esc(sim.best_hire_reason)}</p>'
            "</div>"
        )

    # ── View mode switcher ──
    parts.append(
        '<div class="sim-view-bar">'
        f'<button class="sim-view-btn sim-view-active" data-sim-view="summary">{_esc(t("sim.view_summary"))}</button>'
        f'<button class="sim-view-btn" data-sim-view="detail">{_esc(t("sim.view_detail"))}</button>'
        f'<button class="sim-view-btn" data-sim-view="timeline">{_esc(t("sim.view_timeline"))}</button>'
        "</div>"
    )

    # ── Scenario selector ──
    parts.append('<div class="sim-scenario-bar">')
    parts.append(f'<label class="sim-scenario-label">{_esc(t("sim.scenarios"))}:</label>')
    parts.append('<div class="sim-scenario-chips">')
    for idx, sr in enumerate(sim.scenarios):
        active_cls = " sim-chip-active" if idx == 0 else ""
        preset_badge = (
            f' <span class="sim-preset-badge">{_esc(t("sim.preset"))}</span>'
            if sr.scenario.is_preset
            else ""
        )
        parts.append(
            f'<button class="sim-chip{active_cls}" data-sim-scenario="{idx}">'
            f"{_esc(sr.scenario.name)}{preset_badge}"
            f"</button>"
        )
    parts.append("</div></div>")

    # ══════════════════════════════════════════════════════════════
    # SUMMARY VIEW — scenario comparison cards + metrics
    # ══════════════════════════════════════════════════════════════
    parts.append('<div class="sim-panel" id="simPanel-summary">')

    for idx, sr in enumerate(sim.scenarios):
        display = "block" if idx == 0 else "none"
        sc = sr.scenario

        parts.append(
            f'<div class="sim-scenario-detail" data-sim-detail="{idx}" style="display:{display}">'
        )

        # Impact score header
        impact_cls = (
            "sim-impact-high"
            if sr.impact_score > 50
            else "sim-impact-med"
            if sr.impact_score > 20
            else "sim-impact-low"
        )
        parts.append(
            f'<div class="sim-impact-header {impact_cls}">'
            f'<div class="sim-impact-title">{_esc(sc.name)}</div>'
            f'<div class="sim-impact-desc">{_esc(sc.description)}</div>'
            f'<div class="sim-impact-badge">{_esc(t("sim.impact_score"))}: <strong>{sr.impact_score:.0f}</strong>/100</div>'
            f"</div>"
        )

        # Resource changes
        parts.append('<div class="sim-changes">')
        for rc in sc.changes:
            sign = "+" if rc.delta > 0 else ""
            parts.append(
                f'<span class="sim-change-chip">{sign}{rc.delta} {_esc(rc.team_key.upper())}</span>'
            )
        parts.append("</div>")

        # Before/After comparison table
        b = sr.baseline
        s = sr.simulated
        d = sr.delta
        metrics = [
            (
                "sim.metric.collisions",
                b.total_collisions,
                s.total_collisions,
                d.collisions_reduced,
                True,
            ),
            (
                "sim.metric.overloaded",
                b.overloaded_people,
                s.overloaded_people,
                d.overload_reduced,
                True,
            ),
            (
                "sim.metric.wip_violations",
                b.wip_violations,
                s.wip_violations,
                d.wip_violations_reduced,
                True,
            ),
            (
                "sim.metric.timeline_overlaps",
                b.timeline_overlaps,
                s.timeline_overlaps,
                d.timeline_overlaps_reduced,
                True,
            ),
            (
                "sim.metric.avg_load",
                t.format_number(b.avg_load_per_person, 1),
                t.format_number(s.avg_load_per_person, 1),
                f"-{t.format_number(d.avg_load_reduction_pct, 1)}%",
                True,
            ),
            (
                "sim.metric.max_load",
                t.format_number(b.max_load_person, 1),
                t.format_number(s.max_load_person, 1),
                f"-{t.format_number(d.peak_load_reduction_pct, 1)}%",
                True,
            ),
            (
                "sim.metric.balance",
                f"{b.team_balance_score:.0f}",
                f"{s.team_balance_score:.0f}",
                f"+{t.format_number(d.balance_improvement, 1)}",
                False,
            ),
            ("sim.metric.blocked", b.blocked_work_items, s.blocked_work_items, 0, True),
        ]

        parts.append(
            '<div class="table-scroll">'
            '<table class="sim-comparison-table">'
            "<thead><tr>"
            f"<th>{_esc(t('sim.metric.collisions').split()[0])}…</th>"
            f"<th>{_esc(t('sim.before'))}</th>"
            f"<th>{_esc(t('sim.after'))}</th>"
            f"<th>{_esc(t('sim.change'))}</th>"
            "</tr></thead><tbody>"
        )
        for label_key, before_val, after_val, delta_val, lower_is_better in metrics:
            if isinstance(delta_val, (int, float)):
                imp_cls = "sim-improved" if delta_val > 0 else "sim-worse" if delta_val < 0 else ""
                delta_display = (
                    f"{'+' if delta_val > 0 else ''}{delta_val}" if delta_val != 0 else "—"
                )
            else:
                imp_cls = (
                    "sim-improved" if str(delta_val).startswith("-") and lower_is_better else ""
                )
                delta_display = str(delta_val)

            parts.append(
                f"<tr>"
                f'<td class="sim-metric-label">{_esc(t(label_key))}</td>'
                f'<td class="sim-val-before">{before_val}</td>'
                f'<td class="sim-val-after">{after_val}</td>'
                f'<td class="sim-val-delta {imp_cls}">{delta_display}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")
        parts.append("</div>")  # /sim-scenario-detail

    parts.append("</div>")  # /simPanel-summary

    # ══════════════════════════════════════════════════════════════
    # DETAIL VIEW — team impact + workload changes + recommendations
    # ══════════════════════════════════════════════════════════════
    parts.append('<div class="sim-panel" id="simPanel-detail" style="display:none">')

    # Team Impact table
    parts.append(f'<h3 class="sim-section-title">{_esc(t("sim.team_impact"))}</h3>')
    if sim.team_impacts:
        parts.append(
            '<div class="table-scroll"><table class="data-table sim-team-table">'
            "<thead><tr>"
            f"<th>{_esc(t('sim.team_col.team'))}</th>"
            f"<th>{_esc(t('sim.team_col.members'))}</th>"
            f"<th>{_esc(t('sim.team_col.load'))}</th>"
            f"<th>{_esc(t('sim.team_col.per_person'))}</th>"
            f"<th>{_esc(t('sim.team_col.overloaded'))}</th>"
            f"<th>{_esc(t('sim.team_col.collisions'))}</th>"
            f"<th>{_esc(t('sim.team_col.impact'))}</th>"
            "</tr></thead><tbody>"
        )
        for ti in sim.team_impacts:
            impact_cls = (
                "sim-impact-high"
                if ti.impact_score > 50
                else "sim-impact-med"
                if ti.impact_score > 20
                else "sim-impact-low"
            )
            parts.append(
                f"<tr>"
                f"<td><strong>{_esc(ti.team_name)}</strong></td>"
                f"<td>{ti.current_members}</td>"
                f"<td>{ti.current_load:.0f} {_esc(t('unit.sp'))}</td>"
                f"<td>{ti.load_per_person:.0f} {_esc(t('unit.sp'))}</td>"
                f"<td>{ti.overloaded_members}</td>"
                f"<td>{ti.collision_contribution}</td>"
                f'<td><span class="sim-score-badge {impact_cls}">{ti.impact_score:.0f}</span></td>'
                f"</tr>"
            )
            if ti.recommendation:
                parts.append(
                    f'<tr class="sim-rec-row"><td colspan="7">'
                    f'<span class="sim-rec-inline">💡 {_esc(ti.recommendation)}</span>'
                    f"</td></tr>"
                )
        parts.append("</tbody></table></div>")

    # Recommendations
    if sim.global_recommendations:
        parts.append(f'<h3 class="sim-section-title">{_esc(t("sim.recommendations"))}</h3>')
        parts.append('<div class="sim-rec-list">')
        for rec in sim.global_recommendations:
            sev_cls, sev_icon = SEVERITY_BADGE.get(rec.severity, ("", ""))
            parts.append(
                f'<div class="sim-rec-card">'
                f'<div class="sim-rec-header">'
                f'<span class="badge {sev_cls}">{sev_icon} {_esc(rec.severity.value)}</span>'
                f'<span class="sim-rec-title">{_esc(rec.title)}</span>'
                f'<span class="sim-rec-impact">{_esc(t("sim.impact_score"))}: {rec.impact_score:.0f}</span>'
                f"</div>"
                f'<p class="sim-rec-desc">{_esc(rec.description)}</p>'
                f"</div>"
            )
        parts.append("</div>")

    # Workload changes per scenario
    parts.append(f'<h3 class="sim-section-title">{_esc(t("sim.workload_change"))}</h3>')
    for idx, sr in enumerate(sim.scenarios):
        display = "block" if idx == 0 else "none"
        parts.append(f'<div class="sim-wl-detail" data-sim-wl="{idx}" style="display:{display}">')
        parts.append(
            '<div class="table-scroll"><table class="data-table">'
            "<thead><tr>"
            f"<th>{_esc(t('sim.person'))}</th>"
            f"<th>{_esc(t('table.team'))}</th>"
            f"<th>{_esc(t('sim.original_sp'))}</th>"
            f"<th>{_esc(t('sim.simulated_sp'))}</th>"
            f"<th>{_esc(t('sim.reduction'))}</th>"
            "</tr></thead><tbody>"
        )
        for wl in sr.simulated_workloads:
            is_new = wl.get("is_new", False)
            new_badge = (
                f' <span class="sim-new-badge">{_esc(t("sim.new_resource"))}</span>'
                if is_new
                else ""
            )
            reduction = wl.get("reduction_pct", 0)
            red_cls = (
                "sim-improved" if isinstance(reduction, (int, float)) and reduction > 0 else ""
            )
            orig_sp = wl.get("original_sp", 0)
            sim_sp = wl.get("story_points", 0)
            orig_val = (
                t.format_number(orig_sp, 1) if isinstance(orig_sp, (int, float)) else str(orig_sp)
            )
            sim_val = (
                t.format_number(sim_sp, 1) if isinstance(sim_sp, (int, float)) else str(sim_sp)
            )
            red_val = (
                t.format_number(reduction, 1)
                if isinstance(reduction, (int, float))
                else str(reduction)
            )
            parts.append(
                f"<tr{'' if not is_new else ' class=sim-new-row'}>"
                f"<td>{_esc(wl['person'])}{new_badge}</td>"
                f"<td>{_esc(wl['team'])}</td>"
                f"<td>{orig_val}</td>"
                f"<td>{sim_val}</td>"
                f'<td class="{red_cls}">{"-" if isinstance(reduction, (int, float)) and reduction > 0 else ""}{red_val}%</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")
        parts.append("</div>")

    # Assumptions
    if sim.assumptions:
        parts.append(f'<h3 class="sim-section-title">{_esc(t("sim.assumptions"))}</h3>')
        parts.append('<ul class="sim-assumptions">')
        for a in sim.assumptions:
            parts.append(f"<li>{_esc(a)}</li>")
        parts.append("</ul>")

    parts.append("</div>")  # /simPanel-detail

    # ══════════════════════════════════════════════════════════════
    # TIMELINE VIEW — before/after comparison
    # ══════════════════════════════════════════════════════════════
    parts.append('<div class="sim-panel" id="simPanel-timeline" style="display:none">')

    for idx, sr in enumerate(sim.scenarios):
        display = "block" if idx == 0 else "none"
        parts.append(f'<div class="sim-tl-detail" data-sim-tl="{idx}" style="display:{display}">')

        # Before timeline
        parts.append(f'<h4 class="sim-tl-label">{_esc(t("sim.timeline_before"))}</h4>')
        if sr.timeline_before and sr.timeline_before.swimlanes:
            parts.append(_render_mini_timeline(sr.timeline_before, "before", t))
        else:
            parts.append(f'<p class="empty-state" role="status">{_t(t, "timeline.no_data")}</p>')

        # After timeline
        drag_hint = _esc(t("sim.drag_hint"))
        parts.append(
            f'<h4 class="sim-tl-label sim-tl-after-label">{_esc(t("sim.timeline_after"))}</h4>'
        )
        parts.append(f'<p class="sim-drag-hint">↔ {drag_hint}</p>')
        if sr.timeline_after and sr.timeline_after.swimlanes:
            parts.append(_render_mini_timeline(sr.timeline_after, "after", t))
        else:
            parts.append(f'<p class="empty-state" role="status">{_t(t, "timeline.no_data")}</p>')

        # Overlap comparison summary
        if sr.timeline_before and sr.timeline_after:
            before_overlaps = sum(s.overlap_count for s in sr.timeline_before.swimlanes)
            after_overlaps = sum(s.overlap_count for s in sr.timeline_after.swimlanes)
            reduction = before_overlaps - after_overlaps
            parts.append(
                '<div class="sim-tl-summary">'
                f'<span class="sim-tl-stat">{_esc(t("sim.before"))}: <strong>{before_overlaps}</strong> {_esc(t("sim.overlaps_label"))}</span>'
                f'<span class="sim-tl-arrow">→</span>'
                f'<span class="sim-tl-stat">{_esc(t("sim.after"))}: <strong>{after_overlaps}</strong> {_esc(t("sim.overlaps_label"))}</span>'
            )
            if reduction > 0:
                parts.append(
                    f'<span class="sim-tl-reduction sim-improved">↓ {reduction} {_esc(t("sim.fewer_overlaps"))}</span>'
                )
            parts.append("</div>")

        parts.append("</div>")  # /sim-tl-detail

    parts.append("</div>")  # /simPanel-timeline

    return "\n".join(parts)


def _render_mini_timeline(
    data: TimelineData,
    variant: str,
    t: Translator,
    max_lanes: int = 20,
) -> str:
    """Render a compact timeline for simulation comparison."""
    parts: list[str] = []
    total_days = data.total_days or 1
    today = date.today()
    lanes = data.swimlanes[:max_lanes]

    variant_cls = "sim-tl-before" if variant == "before" else "sim-tl-after"
    parts.append(f'<div class="sim-mini-tl {variant_cls}">')
    parts.append('<div class="tl-container tl-compact">')

    # Header with month markers
    parts.append('<div class="tl-header"><div class="tl-label-col"></div><div class="tl-axis">')
    current = data.range_start.replace(day=1)
    while current <= data.range_end:
        left = _day_offset(data.range_start, current, total_days)
        parts.append(
            f'<span class="tl-month-mark" style="left:{left:.1f}%">{_esc(t.format_month_short(current))}</span>'
        )
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    parts.append("</div></div>")

    # Swimlanes
    for lane in lanes:
        parts.append('<div class="tl-row">')
        overlap_badge = ""
        if lane.overlap_count > 0:
            overlap_badge = f' <span class="tl-overlap-badge">{lane.overlap_count}</span>'
        parts.append(
            f'<div class="tl-label-col" title="{_esc(_loc(lane.label, t))}">'
            f'<span class="tl-lane-name">{_esc(_loc(lane.label, t))}</span>{overlap_badge}'
            f"</div>"
        )
        parts.append('<div class="tl-bar-area">')

        # Today line
        if data.range_start <= today <= data.range_end:
            today_left = _day_offset(data.range_start, today, total_days)
            parts.append(f'<div class="tl-today-line" style="left:{today_left:.1f}%"></div>')

        # Overlap zones
        for ov in data.overlaps:
            if ov.swimlane_key == lane.key:
                ov_left = _day_offset(data.range_start, ov.start, total_days)
                ov_width = _bar_width_pct(ov.start, ov.end, total_days)
                ov_color = _TL_OVERLAP_COLORS.get(ov.severity, _TL_OVERLAP_COLORS["medium"])
                parts.append(
                    f'<div class="tl-overlap-zone" style="left:{ov_left:.1f}%;width:{ov_width:.1f}%;background:{ov_color}"></div>'
                )

        # Bars
        drag_cls = " sim-draggable" if variant == "after" else ""
        for bar in lane.bars:
            left = _day_offset(data.range_start, bar.start, total_days)
            width = _bar_width_pct(bar.start, bar.end, total_days)
            color = _TL_TYPE_COLORS.get(bar.issue_type, _TL_TYPE_COLORS["Other"])
            extra_cls = ""
            if bar.is_blocked:
                extra_cls = " tl-bar-blocked"
            elif bar.is_done:
                extra_cls = " tl-bar-done"
            parts.append(
                f'<div class="tl-bar{extra_cls}{drag_cls}" style="left:{left:.1f}%;width:{width:.1f}%;--bar-color:{color}" title="{_esc(bar.key)}: {_esc(bar.label)}">'
                f'<span class="tl-bar-label">{_esc(bar.key)}</span>'
                f"</div>"
            )

        parts.append("</div></div>")  # /bar-area, /row

    parts.append("</div></div>")  # /tl-container, /sim-mini-tl
    return "\n".join(parts)
