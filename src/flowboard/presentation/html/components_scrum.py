"""Scrum Insights component renderers."""

from __future__ import annotations

from flowboard.i18n.translator import Translator, get_translator
from flowboard.presentation.html.components import _esc, _t

# Expose private helpers so ``from components_scrum import *`` re-exports them
# through the hub — tests import them via components.
__all__ = [
    "_format_ceremony_headline",
    "_translate_factors",
    "_translate_missing",
    "scrum_backlog_quality_view",
    "scrum_blockers_view",
    "scrum_capacity_view",
    "scrum_ceremonies_view",
    "scrum_delivery_risks_view",
    "scrum_dep_heatmap_view",
    "scrum_product_progress_view",
    "scrum_readiness_view",
    "scrum_scope_changes_view",
    "scrum_sprint_goals_view",
]

# Maps for translating domain identifiers to i18n keys
_MISSING_LABELS = {
    "estimate": "scrum.missing_estimate",
    "assignee": "scrum.missing_assignee",
    "epic": "scrum.missing_epic",
    "priority": "scrum.missing_priority",
    "too_large": "scrum.missing_too_large",
}

_RISK_FACTORS = {
    "low_completion": "scrum.factor_low_completion",
    "more_todo": "scrum.factor_more_todo",
}


def _translate_missing(items: list[str], t: Translator) -> list[str]:
    """Translate readiness missing-field identifiers."""
    return [t(_MISSING_LABELS.get(m, m)) for m in items]


def _translate_factors(factors: list[str], t: Translator) -> str:
    """Translate risk factor identifiers."""
    result = []
    for f in factors:
        if ":" in f:
            key, val = f.split(":", 1)
            i18n_key = f"scrum.factor_{key}"
            result.append(t(i18n_key, count=val))
        else:
            i18n_key = _RISK_FACTORS.get(f, f)
            result.append(t(i18n_key))
    return ", ".join(result) if result else "\u2014"


_CEREMONY_KEYS = {
    "daily": ("scrum.headline_daily", ("escalations", "aging")),
    "planning": ("scrum.headline_planning", ("ready", "not_ready")),
    "review": ("scrum.headline_review", ("done", "total")),
    "retro": ("scrum.headline_retro", ("blockers", "churn")),
}


def _format_ceremony_headline(raw: str, t: Translator) -> str:
    """Translate encoded ceremony headline from domain."""
    parts = raw.split(":")
    if len(parts) < 3:
        return raw
    key_info = _CEREMONY_KEYS.get(parts[0])
    if not key_info:
        return raw
    i18n_key, param_names = key_info
    return t(i18n_key, **dict(zip(param_names, parts[1:], strict=False)))


def scrum_sprint_goals_view(insights: object | None, t: Translator | None = None) -> str:
    """Render sprint goal health cards."""
    if t is None:
        t = get_translator()
    if not insights or not insights.sprint_goals:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_sprints")}</p>'

    parts: list[str] = ['<div class="sprint-grid">']
    for sg in insights.sprint_goals:
        health_cls = {
            "on_track": "card-green",
            "at_risk": "card-amber",
            "off_track": "card-red",
        }.get(sg.health, "")
        health_label = t(f"scrum.{sg.health}")
        parts.append(
            f'<div class="sprint-card {health_cls}" style="border-top:3px solid">'
            f'<div class="sprint-header"><h4>{_esc(sg.sprint_name)}</h4>'
            f'<span class="chip chip-{_esc(sg.sprint_state)}">{_esc(t("enum.sprint_state." + sg.sprint_state))}</span></div>'
            f'<div class="progress-bar" role="progressbar" aria-valuenow="{sg.completion_pct:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="{_esc(t("scrum.completion"))}"><div class="progress-fill progress-fill-success" style="width:{sg.completion_pct:.0f}%"></div></div>'
            f'<div class="sprint-stats">'
            f"<span>\U0001f3af {sg.total_goal_items} {_esc(t('scrum.goal_items'))}</span>"
            f"<span>\u2705 {sg.completed} {_esc(t('scrum.completed'))}</span>"
            f"<span>\U0001f6ab {sg.blocked} {_esc(t('scrum.blocked'))}</span>"
            f"</div>"
            f'<div class="scrum-goal-health">'
            f'{_esc(t("scrum.goal_health"))}: <span style="color:{"var(--color-success)" if sg.health == "on_track" else "var(--color-warning)" if sg.health == "at_risk" else "var(--color-danger)"}">{_esc(health_label)}</span>'
            f"</div>"
        )
        if sg.goal_items:
            parts.append('<div class="scrum-detail-items">')
            for gi in sg.goal_items[:8]:
                icon = (
                    "\u2705"
                    if gi.status == "done"
                    else (
                        "\U0001f6ab"
                        if gi.is_blocked
                        else ("\U0001f504" if gi.status == "in_progress" else "\u2b1c")
                    )
                )
                parts.append(
                    f'<div class="scrum-detail-item">{icon} '
                    f"<strong>{_esc(gi.key)}</strong> {_esc(gi.summary)} "
                    f'<span class="opacity-muted">({_esc(gi.assignee)})</span></div>'
                )
            parts.append("</div>")
        parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def scrum_scope_changes_view(insights: object | None, t: Translator | None = None) -> str:
    """Render scope change tracker."""
    if t is None:
        t = get_translator()
    if not insights or not insights.scope_changes:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_sprints")}</p>'

    parts: list[str] = ['<div class="sprint-grid">']
    for sc in insights.scope_changes:
        stab_color = {
            "stable": "var(--color-success)",
            "moderate": "var(--color-warning)",
            "unstable": "var(--color-danger)",
        }.get(sc.stability, "var(--text)")
        parts.append(
            f'<div class="sprint-card">'
            f'<div class="sprint-header"><h4>{_esc(sc.sprint_name)}</h4>'
            f'<span style="font-weight:700;color:{stab_color}">{_esc(t("scrum." + sc.stability))}</span></div>'
            f'<div class="sprint-stats sprint-stats-spaced">'
            f"<span>\U0001f4cb {sc.original_count} {_esc(t('scrum.original'))}</span>"
            f"<span>\u2795 {sc.added_count} {_esc(t('scrum.added'))}</span>"
            f"<span>\U0001f4ca {sc.sp_added:.0f} {_esc(t('unit.sp'))} {_esc(t('scrum.added'))}</span>"
            f"<span>\U0001f504 {sc.churn_pct:.0f}% {_esc(t('scrum.churn'))}</span>"
            f"</div>"
        )
        if sc.added_items:
            parts.append('<div class="scrum-detail-items">')
            for ai in sc.added_items[:5]:
                parts.append(
                    f'<div class="scrum-detail-item">\u2795 '
                    f"<strong>{_esc(ai.key)}</strong> {_esc(ai.summary)} "
                    f"({ai.story_points:.0f} {_esc(t('unit.sp'))})</div>"
                )
            parts.append("</div>")
        parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def scrum_capacity_view(insights: object | None, t: Translator | None = None) -> str:
    """Render capacity vs commitment view."""
    if t is None:
        t = get_translator()
    if not insights or not insights.capacity:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_capacity")}</p>'

    _status_order = {"over": 0, "under": 1, "balanced": 2}
    rows: list[str] = []
    for c in insights.capacity:
        status_color = {
            "over": "var(--color-danger)",
            "under": "var(--color-warning)",
            "balanced": "var(--color-success)",
        }.get(c.status, "")
        util_color = (
            "var(--color-danger)"
            if c.utilization_pct > 100
            else ("var(--color-warning)" if c.utilization_pct > 85 else "var(--color-success)")
        )
        rows.append(
            f'<tr><td data-sort-value="{_esc(c.team)}"><strong>{_esc(c.team)}</strong></td>'
            f'<td data-sort-value="{c.capacity_sp}">{c.capacity_sp:.0f} {_esc(t("unit.sp"))}</td>'
            f'<td data-sort-value="{c.committed_sp}">{c.committed_sp:.0f} {_esc(t("unit.sp"))}</td>'
            f'<td data-sort-value="{c.in_progress_sp}">{c.in_progress_sp:.0f} {_esc(t("unit.sp"))}</td>'
            f'<td data-sort-value="{c.blocked_sp}">{c.blocked_sp:.0f} {_esc(t("unit.sp"))}</td>'
            f'<td data-sort-value="{c.utilization_pct}" style="font-weight:700;color:{util_color}">{c.utilization_pct:.0f}%</td>'
            f'<td data-sort-value="{_status_order.get(c.status, 9)}" style="font-weight:700;color:{status_color}">{_esc(t("scrum." + c.status))}</td></tr>'
        )
    total = len(insights.capacity)
    return (
        f'<div class="fb-table-container" data-table-id="capacity" data-total-rows="{total}">'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th data-sort-type="text">{_esc(t("table.team"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.capacity"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.committed"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.in_progress"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.blocked"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.utilization"))}</th>'
        f'<th data-sort-type="num">{_esc(t("table.status"))}</th>'
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div></div>"
    )


def scrum_blockers_view(insights: object | None, t: Translator | None = None) -> str:
    """Render blocker aging and escalation view."""
    if t is None:
        t = get_translator()
    if not insights or not insights.blockers:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_blockers")}</p>'

    _sev_order = {"escalate": 0, "critical": 1, "high": 2, "medium": 3, "low": 4}
    rows: list[str] = []
    for b in insights.blockers[:30]:
        sev_style = ""
        if b.severity == "escalate":
            sev_style = 'style="background:rgba(239,68,68,.12);color:var(--color-danger)"'
        row_cls = ""
        row_icon = ""
        if b.severity == "escalate":
            row_cls = ' class="row-blocked"'
            row_icon = f' <span aria-label="{_esc(t("scrum.escalated"))}">🚨</span>'
        elif b.severity == "critical":
            row_cls = ' class="row-warn"'
            row_icon = f' <span aria-label="{_esc(t("scrum.critical"))}">⚠️</span>'
        sev_val = _sev_order.get(b.severity, 9)
        rows.append(
            f'<tr{row_cls}><td class="cell-key" data-sort-value="{_esc(b.key)}"><strong>{_esc(b.key)}</strong>{row_icon}</td>'
            f'<td data-sort-value="{_esc(b.summary)}">{_esc(b.summary)}</td>'
            f'<td data-sort-value="{_esc(b.assignee)}">{_esc(b.assignee)}</td>'
            f'<td data-sort-value="{_esc(b.team)}">{_esc(b.team)}</td>'
            f'<td data-sort-value="{b.blocked_days}" class="fw-bold">{_esc(t.plural(b.blocked_days, "plural.day.one", "plural.day.few", "plural.day.many"))}</td>'
            f'<td data-sort-value="{sev_val}"><span class="chip" {sev_style}>{_esc(t("scrum." + b.severity))}</span></td>'
            f'<td data-sort-value="{_esc(b.sprint_name)}">{_esc(b.sprint_name)}</td></tr>'
        )
    total = len(rows)
    return (
        f'<div class="fb-table-container" data-table-id="blockers" data-total-rows="{total}">'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th data-sort-type="text">{_esc(t("table.key"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.summary"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.assignee"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.team"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.days_blocked"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.severity"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.sprint"))}</th>'
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div></div>"
    )


def scrum_delivery_risks_view(insights: object | None, t: Translator | None = None) -> str:
    """Render delivery risk forecast."""
    if t is None:
        t = get_translator()
    if not insights or not insights.delivery_risks:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_delivery_risks")}</p>'

    _level_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows: list[str] = []
    for dr in insights.delivery_risks[:20]:
        level_color = {
            "critical": "var(--color-danger)",
            "high": "var(--color-warning)",
            "medium": "var(--primary)",
            "low": "var(--color-success)",
        }.get(dr.level, "")
        row_cls = ""
        row_icon = ""
        if dr.level == "critical":
            row_cls = ' class="row-blocked"'
            row_icon = f' <span aria-label="{_esc(t("scrum.critical"))}">🚨</span>'
        elif dr.level == "high":
            row_cls = ' class="row-warn"'
            row_icon = f' <span aria-label="{_esc(t("scrum.high_risk"))}">⚠️</span>'
        factors = _translate_factors(dr.factors, t) if dr.factors else "\u2014"
        level_val = _level_order.get(dr.level, 9)
        rows.append(
            f'<tr{row_cls}><td class="cell-key" data-sort-value="{_esc(dr.key)}"><strong>{_esc(dr.key)}</strong>{row_icon}</td>'
            f'<td data-sort-value="{_esc(dr.title)}">{_esc(dr.title)}</td>'
            f'<td data-sort-value="{dr.risk_score}" style="font-weight:700;color:{level_color}">{dr.risk_score:.0f}</td>'
            f'<td data-sort-value="{level_val}" style="font-weight:700;color:{level_color}">{_esc(t("scrum." + dr.level))}</td>'
            f'<td class="text-secondary-sm">{_esc(factors)}</td></tr>'
        )
    total = len(rows)
    return (
        f'<p class="sim-disclaimer"><span class="sim-disclaimer-icon">\U0001f4ca</span> {_esc(t("scrum.disclaimer"))}</p>'
        f'<div class="fb-table-container" data-table-id="delivery-risks" data-total-rows="{total}">'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th data-sort-type="text">{_esc(t("table.epic"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.title"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.risk_score"))}</th>'
        f'<th data-sort-type="num">{_esc(t("table.level"))}</th>'
        f"<th>{_esc(t('scrum.factors'))}</th>"
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div></div>"
    )


def scrum_backlog_quality_view(insights: object | None, t: Translator | None = None) -> str:
    """Render backlog quality/hygiene score."""
    if t is None:
        t = get_translator()
    if not insights:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_backlog")}</p>'

    bq = insights.backlog_quality
    grade_color = {
        "A": "var(--color-success)",
        "B": "var(--primary)",
        "C": "var(--color-warning)",
        "D": "var(--color-danger)",
    }.get(bq.grade, "var(--text)")
    parts: list[str] = [
        '<div class="summary-grid" class="summary-grid-spaced">',
        f'<div class="summary-card card-default"><span class="card-value" style="color:{grade_color}">{_esc(bq.grade)}</span><span class="card-label">{_esc(t("scrum.grade"))}</span></div>',
        f'<div class="summary-card card-default"><span class="card-value">{bq.quality_score:.0f}%</span><span class="card-label">{_esc(t("scrum.quality_score"))}</span></div>',
        f'<div class="summary-card card-default"><span class="card-value">{bq.total_backlog}</span><span class="card-label">{_esc(t("scrum.backlog_items"))}</span></div>',
        "</div>",
        '<div class="summary-grid">',
        f'<div class="summary-card card-red"><span class="card-value">{bq.no_estimate}</span><span class="card-label">{_esc(t("scrum.no_estimate"))}</span></div>',
        f'<div class="summary-card card-amber"><span class="card-value">{bq.no_assignee}</span><span class="card-label">{_esc(t("scrum.no_assignee"))}</span></div>',
        f'<div class="summary-card card-amber"><span class="card-value">{bq.no_epic}</span><span class="card-label">{_esc(t("scrum.no_epic"))}</span></div>',
        f'<div class="summary-card card-default"><span class="card-value">{bq.stale_count}</span><span class="card-label">{_esc(t("scrum.stale"))}</span></div>',
        "</div>",
    ]
    return "\n".join(parts)


def scrum_readiness_view(insights: object | None, t: Translator | None = None) -> str:
    """Render sprint readiness view."""
    if t is None:
        t = get_translator()
    if not insights or not insights.readiness.items:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_readiness")}</p>'

    r = insights.readiness
    rows: list[str] = []
    for ri in r.items[:30]:
        r_color = (
            "var(--color-success)"
            if ri.readiness_pct >= 80
            else ("var(--color-warning)" if ri.readiness_pct >= 40 else "var(--color-danger)")
        )
        missing = (
            ", ".join(_translate_missing(ri.missing, t))
            if ri.missing
            else f"\u2705 {_t(t, 'scrum.ready_check')}"
        )
        rows.append(
            f'<tr><td class="cell-key" data-sort-value="{_esc(ri.key)}"><strong>{_esc(ri.key)}</strong></td>'
            f'<td data-sort-value="{_esc(ri.summary)}">{_esc(ri.summary)}</td>'
            f'<td data-sort-value="{ri.readiness_pct}" style="font-weight:700;color:{r_color}">{ri.readiness_pct:.0f}%</td>'
            f'<td class="text-secondary-sm">{_esc(missing)}</td></tr>'
        )
    total = len(rows)
    return (
        '<div class="summary-grid" class="summary-grid-spaced">'
        f'<div class="summary-card card-green"><span class="card-value">{r.ready_count}</span><span class="card-label">{_esc(t("scrum.ready"))}</span></div>'
        f'<div class="summary-card card-amber"><span class="card-value">{r.partial_count}</span><span class="card-label">{_esc(t("scrum.partial"))}</span></div>'
        f'<div class="summary-card card-red"><span class="card-value">{r.not_ready_count}</span><span class="card-label">{_esc(t("scrum.not_ready"))}</span></div>'
        f'<div class="summary-card card-default"><span class="card-value">{r.avg_readiness:.0f}%</span><span class="card-label">{_esc(t("scrum.avg_readiness"))}</span></div>'
        "</div>"
        f'<div class="fb-table-container" data-table-id="readiness" data-total-rows="{total}">'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th data-sort-type="text">{_esc(t("table.key"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.summary"))}</th>'
        f'<th data-sort-type="num">{_esc(t("scrum.readiness_score"))}</th>'
        f"<th>{_esc(t('scrum.missing'))}</th>"
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div></div>"
    )


def scrum_dep_heatmap_view(insights: object | None, t: Translator | None = None) -> str:
    """Render dependency heatmap."""
    if t is None:
        t = get_translator()
    if not insights or not insights.dependency_heat:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_dep_heatmap")}</p>'

    teams = insights.dependency_teams
    heat = {(c.from_team, c.to_team): c for c in insights.dependency_heat}

    parts: list[str] = [
        '<div class="table-scroll"><table class="data-table"><thead><tr>',
        f"<th>{_esc(t('scrum.from_team'))} \\ {_esc(t('scrum.to_team'))}</th>",
    ]
    for team in teams:
        parts.append(f"<th>{_esc(team)}</th>")
    parts.append("</tr></thead><tbody>")

    for ft in teams:
        parts.append(f"<tr><td><strong>{_esc(ft)}</strong></td>")
        for tt in teams:
            parts.append(_heatmap_cell(ft, tt, heat))
        parts.append("</tr>")

    parts.append("</tbody></table></div>")
    return "\n".join(parts)


def _heatmap_cell(ft: str, tt: str, heat: dict) -> str:
    """Render a single heatmap cell."""
    if ft == tt:
        return '<td style="background:var(--border);text-align:center">\u2014</td>'
    cell = heat.get((ft, tt))
    if not cell:
        return '<td style="text-align:center;color:var(--text-secondary)">0</td>'
    intensity = min(cell.count * 20, 100)
    bg = f"color-mix(in srgb, var(--color-warning) {intensity}%, var(--surface))"
    blocked = ""
    if cell.blocked_count:
        blocked = f' <span style="color:var(--color-danger);font-weight:700">({cell.blocked_count}\U0001f6ab)</span>'
    return (
        f'<td style="background:{bg};text-align:center;font-weight:600">{cell.count}{blocked}</td>'
    )


def scrum_ceremonies_view(insights: object | None, t: Translator | None = None) -> str:
    """Render ceremony support cards."""
    if t is None:
        t = get_translator()
    if not insights or not insights.ceremonies:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_ceremonies")}</p>'

    icons = {
        "daily": "\u2600\ufe0f",
        "planning": "\U0001f4cb",
        "review": "\U0001f50d",
        "retro": "\U0001f504",
    }
    parts: list[str] = ['<div class="sprint-grid">']
    for key in ("daily", "planning", "review", "retro"):
        c = insights.ceremonies.get(key)
        if not c:
            continue
        label = t(f"scrum.{key}")
        headline = _format_ceremony_headline(c.headline, t)
        parts.append(
            f'<div class="sprint-card">'
            f'<div class="sprint-header"><h4>{icons.get(key, "")} {_esc(label)}</h4></div>'
            f'<p class="text-muted-italic">{_esc(headline)}</p>'
            f'<div class="sprint-stats">'
        )
        for mk, mv in list(c.metrics.items())[:4]:
            parts.append(
                f"<span><strong>{_esc(mv)}</strong> {_esc(t('scrum.metric_' + mk, fallback=mk.replace('_', ' ').title()))}</span>"
            )
        parts.append("</div>")
        if c.items:
            parts.append('<div class="ceremony-items">')
            for ci in c.items[:5]:
                parts.append(
                    f'<div class="ceremony-item">'
                    f"\u26a1 <strong>{_esc(ci.key)}</strong> {_esc(ci.summary)}</div>"
                )
            parts.append("</div>")
        parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def scrum_product_progress_view(insights: object | None, t: Translator | None = None) -> str:
    """Render product progress / value delivery view."""
    if t is None:
        t = get_translator()
    if not insights or not insights.product_progress.epics:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_progress")}</p>'

    pp = insights.product_progress
    _status_order = {"done": 0, "on_track": 1, "slipping": 2, "at_risk": 3}
    rows: list[str] = []
    for ep in pp.epics[:25]:
        bar_cls = (
            "progress-fill-success"
            if ep.completion_pct >= 80
            else ("progress-fill-warning" if ep.completion_pct >= 40 else "progress-fill-danger")
        )
        status_color = {
            "done": "var(--color-success)",
            "on_track": "var(--color-success)",
            "slipping": "var(--color-warning)",
            "at_risk": "var(--color-danger)",
        }.get(ep.status, "")
        rows.append(
            f'<tr><td class="cell-key" data-sort-value="{_esc(ep.key)}"><strong>{_esc(ep.key)}</strong></td>'
            f'<td data-sort-value="{_esc(ep.title)}">{_esc(ep.title)}</td>'
            f'<td data-sort-value="{_esc(ep.team)}">{_esc(ep.team)}</td>'
            f'<td data-sort-value="{ep.completion_pct}"><div class="progress-bar-sm" role="progressbar" aria-valuenow="{ep.completion_pct:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="{_esc(ep.key)} progress"><div class="progress-fill {bar_cls}" style="width:{ep.completion_pct:.0f}%"></div></div>'
            f'<span class="pct-label">{ep.completion_pct:.0f}%</span></td>'
            f'<td data-sort-value="{ep.done_issues}">{ep.done_issues}/{ep.total_issues}</td>'
            f'<td data-sort-value="{_status_order.get(ep.status, 9)}" style="font-weight:700;color:{status_color}">{_esc(t("scrum." + ep.status))}</td></tr>'
        )
    total = len(rows)
    return (
        '<div class="summary-grid" class="summary-grid-spaced">'
        f'<div class="summary-card card-default"><span class="card-value">{pp.overall_completion:.0f}%</span><span class="card-label">{_esc(t("scrum.overall_progress"))}</span></div>'
        f'<div class="summary-card card-green"><span class="card-value">{pp.on_track}</span><span class="card-label">{_esc(t("scrum.on_track"))}</span></div>'
        f'<div class="summary-card card-amber"><span class="card-value">{pp.slipping}</span><span class="card-label">{_esc(t("scrum.slipping"))}</span></div>'
        f'<div class="summary-card card-red"><span class="card-value">{pp.at_risk}</span><span class="card-label">{_esc(t("scrum.at_risk"))}</span></div>'
        "</div>"
        f'<div class="fb-table-container" data-table-id="product-progress" data-total-rows="{total}">'
        '<div class="table-scroll"><table class="data-table"><thead><tr>'
        f'<th data-sort-type="text">{_esc(t("table.epic"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.title"))}</th>'
        f'<th data-sort-type="text">{_esc(t("table.team"))}</th>'
        f'<th data-sort-type="num">{_esc(t("table.progress"))}</th>'
        f'<th data-sort-type="num">{_esc(t("table.issues"))}</th>'
        f'<th data-sort-type="num">{_esc(t("table.status"))}</th>'
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div></div>"
    )
