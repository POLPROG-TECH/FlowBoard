"""Table and card components: workload, risk, sprint health, issues, dependencies."""

from __future__ import annotations

from flowboard.domain.models import (
    BoardSnapshot,
    Issue,
    RiskSignal,
    SprintHealth,
    WorkloadRecord,
)
from flowboard.i18n.translator import Translator, get_translator
from flowboard.presentation.html.components import (
    _esc,
    _issue_type_key,
    _link_type_key,
    _t,
    severity_badge,
    status_chip,
)
from flowboard.shared.types import LinkType
from flowboard.shared.utils import truncate_html

__all__ = [
    "_find_team",
    "dependency_table",
    "deps_blockers_detail",
    "issues_table",
    "risk_table",
    "sprint_health_cards",
    "workload_table",
]


# ---------------------------------------------------------------------------
# Workload table
# ---------------------------------------------------------------------------


def workload_table(
    records: list[WorkloadRecord],
    t: Translator | None = None,
    *,
    overload_points: float = 20.0,
    overload_issues: int = 8,
) -> str:
    if t is None:
        t = get_translator()
    if not records:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_workload")}</p>'
    rows = []
    for wr in records:
        is_overloaded = wr.story_points > overload_points or wr.issue_count > overload_issues
        overload_cls = ' class="row-warn"' if is_overloaded else ""
        overload_icon = (
            f' <span title="{_esc(t("table.overloaded"))}" aria-label="{_esc(t("table.overloaded"))}">⚠️</span>'
            if is_overloaded
            else ""
        )
        rows.append(
            f"<tr{overload_cls}>"
            f'<td data-sort-value="{_esc(wr.person.display_name)}">{_esc(wr.person.display_name)}{overload_icon}</td>'
            f'<td data-sort-value="{_esc(wr.team or "")}">{_esc(wr.team) if wr.team else "—"}</td>'
            f'<td data-sort-value="{wr.issue_count}">{wr.issue_count}</td>'
            f'<td data-sort-value="{wr.story_points}"><strong>{wr.story_points:.0f}</strong></td>'
            f'<td data-sort-value="{wr.in_progress_count}">{wr.in_progress_count}</td>'
            f'<td data-sort-value="{wr.blocked_count}">{wr.blocked_count}</td>'
            f"</tr>"
        )
    total = len(records)
    return (
        f'<div class="fb-table-container" data-table-id="workload" data-total-rows="{total}">'
        '<div class="table-scroll">'
        '<table class="data-table">'
        "<thead><tr>"
        f'<th data-sort-type="text">{_t(t, "table.person")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.team")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.issues")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.story_points")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.in_progress")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.blocked")}</th>'
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
        "</div></div>"
    )


# ---------------------------------------------------------------------------
# Risk table
# ---------------------------------------------------------------------------


def risk_table(signals: list[RiskSignal], t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    if not signals:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_risks")}</p>'
    _sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows = []
    for rs in signals:
        sev_val = _sev_order.get(rs.severity.value, 9)
        rows.append(
            f'<tr data-severity="{_esc(rs.severity.value)}">'
            f'<td data-sort-value="{sev_val}">{severity_badge(rs.severity, t)}</td>'
            f'<td data-sort-value="{_esc(rs.category.value)}">{_esc(t("enum.risk_category." + rs.category.value))}</td>'
            f'<td data-sort-value="{_esc(rs.title)}">{_esc(rs.title)}</td>'
            f"<td>{truncate_html(rs.description, 120)}</td>"
            f"<td>{_esc(rs.recommendation)}</td>"
            f"</tr>"
        )
    total = len(signals)
    return (
        f'<div class="fb-table-container" data-table-id="risks" data-total-rows="{total}">'
        '<div class="table-scroll">'
        '<table class="data-table">'
        "<thead><tr>"
        f'<th data-sort-type="num">{_t(t, "table.severity")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.category")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.title")}</th>'
        f"<th>{_t(t, 'table.description')}</th>"
        f"<th>{_t(t, 'table.recommendation')}</th>"
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
        "</div></div>"
    )


# ---------------------------------------------------------------------------
# Sprint health cards
# ---------------------------------------------------------------------------


def sprint_health_cards(healths: list[SprintHealth], t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    if not healths:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_sprints")}</p>'
    parts = ['<div class="sprint-grid">']
    for sh in healths:
        state_cls = "sprint-active" if sh.sprint.state.value == "active" else "sprint-other"
        pct = sh.completion_pct
        bar_cls = (
            "progress-fill-success"
            if pct >= 80
            else "progress-fill-warning"
            if pct >= 40
            else "progress-fill-danger"
        )
        parts.append(
            f'<div class="sprint-card {state_cls}">'
            f'<div class="sprint-header">'
            f"<h4>{_esc(sh.sprint.name)}</h4>"
            f'<span class="chip chip-{_esc(sh.sprint.state.value)}">{_esc(t("enum.sprint_state." + sh.sprint.state.value))}</span>'
            f"</div>"
            f'<div class="progress-bar" role="progressbar" aria-valuenow="{pct:.0f}" aria-valuemin="0" aria-valuemax="100" aria-label="{_esc(sh.sprint.name)} progress"><div class="progress-fill {bar_cls}" style="width:{pct:.0f}%"></div></div>'
            f'<div class="sprint-stats">'
            f"<span>✅ {sh.done_issues}/{sh.total_issues}</span>"
            f"<span>📊 {sh.completed_points:.0f}/{sh.total_points:.0f} {_esc(t('unit.sp'))}</span>"
            f"<span>🚫 {sh.blocked_issues} {_esc(t('sprint.blocked'))}</span>"
            f"<span>⏳ {sh.aging_issues} {_esc(t('sprint.aging'))}</span>"
            f"</div></div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Issues table (compact)
# ---------------------------------------------------------------------------


def issues_table(issues: list[Issue], *, max_rows: int = 200, t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    if not issues:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_issues")}</p>'
    _pri_order = {"highest": 0, "high": 1, "medium": 2, "low": 3, "lowest": 4, "__unset__": 5}
    _cat_order = {"In Progress": 0, "To Do": 1, "Done": 2}
    rows = []
    for issue in issues[:max_rows]:
        assignee = _esc(issue.assignee.display_name) if issue.assignee else "—"
        sprint_name = _esc(issue.sprint.name) if issue.sprint else "—"
        age = issue.age_days if issue.age_days is not None else -1
        age_display = _esc(t("format.age_days", days=age)) if age >= 0 else "—"
        blocked_cls = ' class="row-blocked"' if issue.is_blocked else ""
        blocked_icon = (
            f' <span title="{_esc(t("table.blocked"))}" aria-label="{_esc(t("table.blocked"))}">🚫</span>'
            if issue.is_blocked
            else ""
        )
        pri_val = _pri_order.get(issue.priority.value.lower(), 5)
        cat_val = _cat_order.get(issue.status_category.value, 9)
        rows.append(
            f"<tr{blocked_cls}>"
            f'<td class="cell-key" data-sort-value="{_esc(issue.key)}">{_esc(issue.key)}{blocked_icon}</td>'
            f'<td data-sort-value="{_esc(issue.summary)}">{truncate_html(issue.summary, 55)}</td>'
            f'<td data-sort-value="{_esc(issue.issue_type.value)}">{_esc(t(f"enum.issue_type.{_issue_type_key(issue.issue_type)}"))}</td>'
            f'<td data-sort-value="{cat_val}">{status_chip(issue.status_category, t)}</td>'
            f'<td data-sort-value="{_esc(issue.assignee.display_name if issue.assignee else "")}">{assignee}</td>'
            f'<td data-sort-value="{issue.story_points}">{issue.story_points:.0f}</td>'
            f'<td data-sort-value="{pri_val}">{_esc(t(f"enum.priority.{issue.priority.value.lower()}"))}</td>'
            f'<td data-sort-value="{_esc(issue.sprint.name if issue.sprint else "")}">{sprint_name}</td>'
            f'<td data-sort-value="{age}">{age_display}</td>'
            f"</tr>"
        )
    total = len(issues)
    return (
        f'<div class="fb-table-container" data-table-id="issues" data-total-rows="{total}">'
        '<div class="table-scroll">'
        '<table class="data-table">'
        "<thead><tr>"
        f'<th data-sort-type="text">{_t(t, "table.key")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.summary")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.type")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.status")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.assignee")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.sp")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.priority")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.sprint")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.age")}</th>'
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
        "</div></div>"
    )


# ---------------------------------------------------------------------------
# Dependency summary
# ---------------------------------------------------------------------------


def dependency_table(snapshot: BoardSnapshot, t: Translator | None = None) -> str:
    if t is None:
        t = get_translator()
    blocking_deps = [d for d in snapshot.dependencies if d.is_blocking]
    if not blocking_deps:
        return f'<p class="empty-state" role="status">{_t(t, "empty.no_dependencies")}</p>'
    _cat_order = {"In Progress": 0, "To Do": 1, "Done": 2}
    rows = []
    for dep in blocking_deps[:50]:
        src_cat = _cat_order.get(dep.source_status.value, 9)
        tgt_cat = _cat_order.get(dep.target_status.value, 9)
        rows.append(
            f"<tr>"
            f'<td class="cell-key" data-sort-value="{_esc(dep.source_key)}">{_esc(dep.source_key)}</td>'
            f'<td data-sort-value="{_esc(dep.link_type.value)}">{_esc(t(f"enum.link_type.{_link_type_key(dep.link_type)}"))}</td>'
            f'<td class="cell-key" data-sort-value="{_esc(dep.target_key)}">{_esc(dep.target_key)}</td>'
            f'<td data-sort-value="{src_cat}">{status_chip(dep.source_status, t)}</td>'
            f'<td data-sort-value="{tgt_cat}">{status_chip(dep.target_status, t)}</td>'
            f"</tr>"
        )
    total = len(blocking_deps)
    return (
        f'<div class="fb-table-container" data-table-id="deps" data-total-rows="{total}">'
        '<div class="table-scroll">'
        '<table class="data-table">'
        "<thead><tr>"
        f'<th data-sort-type="text">{_t(t, "table.source")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.relation")}</th>'
        f'<th data-sort-type="text">{_t(t, "table.target")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.source_status")}</th>'
        f'<th data-sort-type="num">{_t(t, "table.target_status")}</th>'
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
        "</div></div>"
    )


# ---------------------------------------------------------------------------
# Dependencies & Blockers detail view (for Insights sub-tab)
# ---------------------------------------------------------------------------


def deps_blockers_detail(
    snapshot: BoardSnapshot,
    blockers: list | None = None,
    t: Translator | None = None,
) -> str:
    """Render a combined dependencies & blockers detail view with summary cards."""
    if t is None:
        t = get_translator()

    blocking_deps = [d for d in snapshot.dependencies if d.is_blocking]
    blocked_issues = [i for i in snapshot.issues if i.is_blocked and not i.is_done]

    # Pre-build issue-key → team lookup to avoid O(N*M) _find_team calls
    _team_cache: dict[str, str] = {}
    for issue in snapshot.issues:
        if issue.components:
            _team_cache[issue.key] = issue.components[0]
        elif issue.assignee and issue.assignee.team:
            _team_cache[issue.key] = issue.assignee.team
        else:
            _team_cache[issue.key] = ""

    # Build summary cards
    total_blocked = len(blocked_issues)
    total_deps = len(blocking_deps)
    cross_team_deps = 0
    teams_waiting: dict[str, int] = {}
    for dep in blocking_deps:
        src_team = _team_cache.get(dep.source_key, "")
        tgt_team = _team_cache.get(dep.target_key, "")
        if src_team and tgt_team and src_team != tgt_team:
            cross_team_deps += 1
        if tgt_team:
            teams_waiting[tgt_team] = teams_waiting.get(tgt_team, 0) + 1

    aging_blocked = 0
    for issue in blocked_issues:
        if issue.age_days is not None and issue.age_days > 7:
            aging_blocked += 1

    parts: list[str] = []
    # Summary cards row
    parts.append(
        '<div class="summary-grid" class="summary-grid-spaced">'
        f'<div class="summary-card card-danger"><div class="card-icon">🚫</div>'
        f'<div class="card-value">{total_blocked}</div>'
        f'<div class="card-label">{_t(t, "deps.blocked_items")}</div></div>'
        f'<div class="summary-card card-warning"><div class="card-icon">🔗</div>'
        f'<div class="card-value">{total_deps}</div>'
        f'<div class="card-label">{_t(t, "deps.blocking_deps")}</div></div>'
        f'<div class="summary-card card-default"><div class="card-icon">🔀</div>'
        f'<div class="card-value">{cross_team_deps}</div>'
        f'<div class="card-label">{_t(t, "deps.cross_team")}</div></div>'
        f'<div class="summary-card card-danger"><div class="card-icon">⏰</div>'
        f'<div class="card-value">{aging_blocked}</div>'
        f'<div class="card-label">{_t(t, "deps.aging_blocked")}</div></div>'
        "</div>"
    )

    # Teams waiting section
    if teams_waiting:
        top_teams = sorted(teams_waiting.items(), key=lambda x: -x[1])[:6]
        parts.append('<div class="deps-teams-section">')
        parts.append(f'<h4 class="deps-section-heading">{_t(t, "deps.teams_waiting")}</h4>')
        parts.append('<div class="deps-teams-chips">')
        for team_name, count in top_teams:
            parts.append(
                f'<span class="chip chip-todo">{_esc(team_name)}: <strong>{count}</strong></span>'
            )
        parts.append("</div></div>")

    # Blocked items table
    if blocked_issues:
        parts.append(f'<h4 class="deps-section-heading">{_t(t, "deps.blocked_items_detail")}</h4>')
        rows: list[str] = []
        for issue in blocked_issues[:40]:
            age = issue.age_days or 0
            age_cls = (
                "color:var(--color-danger);font-weight:700"
                if age > 14
                else ("color:var(--color-warning);font-weight:600" if age > 7 else "")
            )
            assignee = _esc(issue.assignee.display_name) if issue.assignee else "—"
            blocker_keys = (
                ", ".join(
                    _esc(lnk.target_key)
                    for lnk in issue.links
                    if lnk.link_type in (LinkType.IS_BLOCKED_BY, LinkType.DEPENDS_ON)
                )
                or "—"
            )
            rows.append(
                f"<tr>"
                f'<td class="cell-key" data-sort-value="{_esc(issue.key)}"><strong>{_esc(issue.key)}</strong> 🚫</td>'
                f'<td data-sort-value="{_esc(issue.summary)}">{truncate_html(issue.summary, 50)}</td>'
                f'<td data-sort-value="{_esc(issue.assignee.display_name if issue.assignee else "")}">{assignee}</td>'
                f'<td data-sort-value="{age}" style="{age_cls}">{_esc(t.plural(age, "plural.day.one", "plural.day.few", "plural.day.many"))}</td>'
                f"<td>{blocker_keys}</td>"
                f"</tr>"
            )
        total = len(blocked_issues)
        parts.append(
            f'<div class="fb-table-container" data-table-id="deps-blockers" data-total-rows="{total}">'
            '<div class="table-scroll"><table class="data-table"><thead><tr>'
            f'<th data-sort-type="text">{_t(t, "table.key")}</th>'
            f'<th data-sort-type="text">{_t(t, "table.summary")}</th>'
            f'<th data-sort-type="text">{_t(t, "table.assignee")}</th>'
            f'<th data-sort-type="num">{_t(t, "deps.days_blocked")}</th>'
            f"<th>{_t(t, 'deps.blocked_by')}</th>"
            "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table></div></div>"
        )
    else:
        parts.append(f'<p class="empty-state" role="status">{_t(t, "empty.no_blockers")}</p>')

    return "\n".join(parts)


def _find_team(issue_key: str, snapshot: BoardSnapshot) -> str:
    """Find the team for an issue key from the snapshot."""
    for issue in snapshot.issues:
        if issue.key == issue_key:
            if issue.components:
                return issue.components[0]
            if issue.assignee and issue.assignee.team:
                return issue.assignee.team
            return ""
    return ""
