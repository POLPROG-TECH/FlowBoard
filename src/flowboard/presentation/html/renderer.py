"""HTML dashboard renderer.

Uses Jinja2 to render a self-contained, single-file HTML dashboard
from a :class:`BoardSnapshot` and config.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import jinja2
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from flowboard import __version__
from flowboard.domain.models import BoardSnapshot
from flowboard.domain.pi import PISnapshot
from flowboard.domain.timeline import (
    TimelineMode,
    build_timeline,
)
from flowboard.i18n.translator import Translator, get_translator
from flowboard.infrastructure.config.loader import (
    FlowBoardConfig,
    config_to_dict,
)
from flowboard.presentation.html import charts, components, components_kanban, components_waterfall

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _build_env() -> Environment:
    if not _TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(
            f"Template directory not found: {_TEMPLATE_DIR}. "
            "FlowBoard may not be installed correctly."
        )
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _json_serializer(obj: object) -> str:
    """Strict JSON default handler — only serialises known safe types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(obj)  # type: ignore[return-value]
    return str(obj)


def _json_dumps(obj: object) -> str:
    """JSON-serialize for safe embedding inside HTML <script> tags."""
    s = json.dumps(obj, default=_json_serializer)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_CSS_LENGTH_RE = re.compile(r"^\d+(px|rem|em|%)$")


def _safe_color(value: str, fallback: str = "#fb6400") -> str:
    """Sanitize a CSS color value to prevent CSS injection."""
    return value if _COLOR_RE.match(value) else fallback


def _safe_css_length(value: str, fallback: str = "1440px") -> str:
    """Sanitize a CSS length value to prevent CSS injection."""
    return value if _CSS_LENGTH_RE.match(value) else fallback


def render_dashboard(
    snapshot: BoardSnapshot,
    config: FlowBoardConfig,
    *,
    is_demo: bool = False,
) -> str:
    """Render the full dashboard HTML from a snapshot."""
    env = _build_env()
    template = env.get_template("dashboard.html")

    t: Translator = get_translator(config.locale)

    dash = config.dashboard
    pi_snap: PISnapshot | None = snapshot.pi_snapshot

    # Build all timeline variants
    tl_cfg = dash.timeline
    timeline_data = {}
    for mode in TimelineMode:
        timeline_data[mode.value] = build_timeline(snapshot, mode)

    # Config JSON for the settings panel (secrets stripped)
    config_json = _json_dumps(config_to_dict(config))

    ctx = {
        "snapshot": snapshot,
        "config": config,
        "dash": dash,
        "pi_snapshot": pi_snap,
        "t": t,
        "locale": t.locale,
        # Pre-rendered component HTML (marked safe — already escaped by component builders)
        "summary_cards_html": Markup(
            components.summary_cards(
                snapshot,
                dash.summary_cards,
                t=t,
                overload_points=config.thresholds.overload_points,
                overload_issues=config.thresholds.overload_issues,
            )
        ),
        "workload_table_html": Markup(
            components.workload_table(
                snapshot.workload_records,
                t=t,
                overload_points=config.thresholds.overload_points,
                overload_issues=config.thresholds.overload_issues,
            )
        ),
        "risk_table_html": Markup(components.risk_table(snapshot.risk_signals, t=t)),
        "sprint_health_html": Markup(components.sprint_health_cards(snapshot.sprint_health, t=t)),
        "roadmap_html": Markup(components.roadmap_timeline(snapshot.roadmap_items, t=t)),
        "insights_html": Markup(
            components.risk_table(snapshot.risk_signals, t=t)
            + components.conflict_list(snapshot.overlap_conflicts, t=t)
        ),
        "pi_timeline_html": Markup(
            components.pi_timeline_view(pi_snap, snapshot.roadmap_items, t=t)
        ),
        "conflict_html": Markup(components.conflict_list(snapshot.overlap_conflicts, t=t)),
        "issues_table_html": Markup(
            components.issues_table(snapshot.issues, max_rows=dash.tables.max_rows, t=t)
        ),
        "dependency_html": Markup(components.dependency_table(snapshot, t=t)),
        "deps_blockers_html": Markup(
            components.deps_blockers_detail(
                snapshot,
                blockers=snapshot.scrum_insights.blockers if snapshot.scrum_insights else None,
                t=t,
            )
        ),
        # Scrum insights HTML
        "scrum_sprint_goals_html": Markup(
            components.scrum_sprint_goals_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_scope_changes_html": Markup(
            components.scrum_scope_changes_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_capacity_html": Markup(components.scrum_capacity_view(snapshot.scrum_insights, t=t)),
        "scrum_blockers_html": Markup(components.scrum_blockers_view(snapshot.scrum_insights, t=t)),
        "scrum_delivery_risks_html": Markup(
            components.scrum_delivery_risks_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_backlog_quality_html": Markup(
            components.scrum_backlog_quality_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_readiness_html": Markup(
            components.scrum_readiness_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_dep_heatmap_html": Markup(
            components.scrum_dep_heatmap_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_ceremonies_html": Markup(
            components.scrum_ceremonies_view(snapshot.scrum_insights, t=t)
        ),
        "scrum_product_progress_html": Markup(
            components.scrum_product_progress_view(snapshot.scrum_insights, t=t)
        ),
        "timeline_html": Markup(
            components.timeline_view(
                timeline_data,
                default_mode=tl_cfg.default_mode,
                max_swimlanes=tl_cfg.max_swimlanes,
                show_overlaps=tl_cfg.show_overlaps,
                show_sprint_bounds=tl_cfg.show_sprint_boundaries,
                show_today=tl_cfg.show_today_marker,
                compact=tl_cfg.compact_bar_height,
                has_simulation=snapshot.simulation is not None,
                t=t,
            )
        ),
        "simulation_html": Markup(
            components.simulation_view(
                snapshot.simulation,
                t=t,
            )
        ),
        # Chart data (JSON strings — marked safe for template embedding)
        "workload_chart_data": Markup(charts.workload_chart_data(snapshot, t=t)),
        "status_chart_data": Markup(charts.status_distribution_data(snapshot, t=t)),
        "type_chart_data": Markup(charts.type_distribution_data(snapshot, t=t)),
        "sprint_chart_data": Markup(charts.sprint_progress_data(snapshot, t=t)),
        "team_chart_data": Markup(charts.team_workload_data(snapshot, t=t)),
        "risk_chart_data": Markup(charts.risk_severity_data(snapshot, t=t)),
        # Styling / branding (CSS-injection-safe)
        "theme": dash.theme,
        "primary_color": _safe_color(dash.branding.primary_color),
        "secondary_color": _safe_color(dash.branding.secondary_color, "#002754"),
        "tertiary_color": _safe_color(dash.branding.tertiary_color, "#666666"),
        "title": dash.branding.title,
        "subtitle": dash.branding.subtitle,
        "company_name": dash.branding.company_name,
        "generated_at": t.format_datetime(snapshot.generated_at),
        "layout_density": dash.layout.density,
        "max_width": _safe_css_length(dash.layout.max_width),
        "show_refresh_meta": dash.refresh_metadata,
        # Tab config
        "visible_tabs": dash.tabs.visible,
        "tab_order": dash.tabs.order,
        "default_tab": dash.tabs.default_tab,
        # Chart toggles
        "charts_cfg": dash,
        # Sections collapsed
        "sections_collapsed": dash.sections_collapsed,
        # Config JSON for settings panel
        "config_json": Markup(config_json),
        "version": __version__,
        # Methodology
        "methodology": config.methodology,
        # Kanban components (empty if not kanban/hybrid)
        "kanban_flow_html": Markup(components_kanban.flow_tab_html(snapshot.kanban_insights, t=t)),
        "kanban_throughput_data": Markup(
            components_kanban.throughput_chart_data(snapshot.kanban_insights, t=t)
        ),
        "kanban_cfd_data": Markup(components_kanban.cfd_chart_data(snapshot.kanban_insights, t=t)),
        # Waterfall components (empty if not waterfall)
        "waterfall_phases_html": Markup(
            components_waterfall.phases_tab_html(snapshot.waterfall_insights, t=t)
        ),
        # Demo mode
        "is_demo": is_demo,
    }
    try:
        return template.render(**ctx)
    except (jinja2.TemplateError, KeyError, TypeError, ValueError) as exc:
        import logging

        logging.getLogger("flowboard.renderer").exception("Dashboard render failed")
        return _render_error_page(str(exc), locale=config.locale)


def _render_error_page(error_detail: str, locale: str = "en") -> str:
    """Return a styled error page when dashboard rendering fails."""
    from markupsafe import escape

    t = get_translator(locale)
    safe_detail = escape(error_detail)
    title = escape(t("error.page_title", fallback="FlowBoard — Error"))
    heading = escape(t("error.heading", fallback="Dashboard could not be rendered"))
    description = escape(
        t(
            "error.description",
            fallback="An error occurred while generating the dashboard. "
            "Please check your configuration and try again.",
        )
    )
    retry = escape(t("error.retry", fallback="Retry"))
    lang = escape(t.locale)
    return (
        f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title>"
        "<style>"
        "body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;"
        "background:#F8FAFC;color:#1E293B;display:flex;align-items:center;"
        "justify-content:center;min-height:100vh;margin:0;padding:24px}"
        ".err{max-width:480px;text-align:center}"
        ".err-icon{font-size:3rem;margin-bottom:16px;opacity:.6}"
        ".err h1{font-size:1.5rem;font-weight:700;margin-bottom:8px}"
        ".err p{color:#64748B;font-size:.9rem;line-height:1.6;margin-bottom:20px}"
        ".err-detail{background:#F1F5F9;border:1px solid #E2E8F0;border-radius:8px;"
        "padding:12px 16px;font-size:.8rem;color:#475569;text-align:left;"
        "word-break:break-word;margin-bottom:20px}"
        ".err-btn{display:inline-block;padding:10px 24px;background:#4F46E5;"
        "color:#fff;border:none;border-radius:8px;font-size:.88rem;font-weight:600;"
        "cursor:pointer;text-decoration:none}"
        ".err-btn:hover{opacity:.9}"
        "</style></head><body>"
        '<div class="err">'
        '<div class="err-icon">⚠️</div>'
        f"<h1>{heading}</h1>"
        f"<p>{description}</p>"
        f'<div class="err-detail">{safe_detail}</div>'
        f'<a href="/" class="err-btn" onclick="location.reload();return false">'
        f"{retry}</a>"
        "</div></body></html>"
    )


def render_first_run(*, config_path: str = "", locale: str = "en") -> str:
    """Render the first-run setup page with i18n support."""
    from flowboard.i18n import set_locale

    set_locale(locale)
    t: Translator = get_translator(locale)

    env = _build_env()
    template = env.get_template("first_run.html")
    return template.render(t=t, locale=locale, config_path=config_path)
