"""Configuration loader with environment-variable overrides and defaults.

Split into sub-modules for maintainability:
- config_models: dataclass definitions

This module re-exports all models for backward compatibility and provides
the builder/loader/serializer functions.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from flowboard.infrastructure.config.config_models import (
    _DEFAULT_ISSUES_COLUMNS,
    _DEFAULT_SUMMARY_CARDS,
    _DEFAULT_TABS,
    _DEFAULT_WORKING_DAYS,
    BrandingConfig,
    ChartsConfig,
    DashboardConfig,
    FieldMappings,
    FiltersConfig,
    FlowBoardConfig,
    JiraConfig,
    LayoutConfig,
    OutputConfig,
    PIConfig,
    RiskDisplayConfig,
    RoadmapDisplayConfig,
    SimulationConfig,
    SummaryCardsConfig,
    TablesConfig,
    TabsConfig,
    TeamDef,
    Thresholds,
    TimelineDisplayConfig,
)
from flowboard.infrastructure.config.validator import validate_config_dict

_logger = logging.getLogger(__name__)

_SUPPORTED_LOCALES = ("en", "pl")


def _validate_locale(locale: str) -> str:
    """Validate locale and warn if unsupported, falling back to 'en'."""
    if locale in _SUPPORTED_LOCALES:
        return locale
    _logger.warning(
        "Unsupported locale '%s'. Supported: %s. Falling back to 'en'.",
        locale,
        ", ".join(_SUPPORTED_LOCALES),
    )
    return "en"


def _validate_methodology(methodology: str) -> str:
    """Validate methodology and warn if unsupported, falling back to 'scrum'."""
    from flowboard.infrastructure.config.config_models import SUPPORTED_METHODOLOGIES

    if methodology in SUPPORTED_METHODOLOGIES:
        return methodology
    _logger.warning(
        "Unsupported methodology '%s'. Supported: %s. Falling back to 'scrum'.",
        methodology,
        ", ".join(sorted(SUPPORTED_METHODOLOGIES)),
    )
    return "scrum"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

_SAFE_EXPAND_KEYS = frozenset(
    {
        "base_url",
        "auth_token",
        "auth_email",
        "pat",
        "password",
        "path",
        "output_path",
    }
)


def _expand_env_vars(obj: Any, *, _key: str = "") -> Any:
    """Recursively expand ${VAR} patterns only in safe config keys."""
    if isinstance(obj, str) and _key in _SAFE_EXPAND_KEYS:
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v, _key=k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(item, _key=_key) for item in obj]
    return obj


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Override sensitive config fields from environment variables.

    Values are stripped and empty strings are ignored so that
    ``FLOWBOARD_JIRA_URL=""`` doesn't override a valid config value.
    """
    # First expand ${VAR} patterns in all string values
    raw = _expand_env_vars(raw)

    jira = raw.setdefault("jira", {})
    if token := os.environ.get("FLOWBOARD_JIRA_TOKEN", "").strip():
        jira["auth_token"] = token
    if email := os.environ.get("FLOWBOARD_JIRA_EMAIL", "").strip():
        jira["auth_email"] = email
    if base := os.environ.get("FLOWBOARD_JIRA_URL", "").strip():
        jira["base_url"] = base.rstrip("/")
    return raw


def _build_jira_config(raw: dict[str, Any]) -> JiraConfig:
    j = raw.get("jira", {})
    return JiraConfig(
        base_url=j.get("base_url", "").rstrip("/"),
        auth_token=j.get("auth_token", ""),
        auth_email=j.get("auth_email", ""),
        server_type=j.get("server_type", "cloud"),
        auth_method=j.get("auth_method", "basic"),
        api_version=j.get("api_version", "2"),
        projects=j.get("projects", []),
        boards=j.get("boards", []),
        max_results=j.get("max_results", 100),
        jql_filter=j.get("jql_filter", ""),
    )


def _build_field_mappings(raw: dict[str, Any]) -> FieldMappings:
    fm = raw.get("field_mappings", {})
    known = {"story_points", "epic_link", "sprint"}
    extra = {k: v for k, v in fm.items() if k not in known}
    return FieldMappings(
        story_points=fm.get("story_points", "customfield_10016"),
        epic_link=fm.get("epic_link", "customfield_10014"),
        sprint=fm.get("sprint", "customfield_10020"),
        extra=extra,
    )


def _build_teams(raw: dict[str, Any]) -> list[TeamDef]:
    teams: list[TeamDef] = []
    for t in raw.get("teams", []):
        if not isinstance(t, dict):
            _logger.warning("Skipping non-dict team entry: %r", t)
            continue
        key = t.get("key")
        name = t.get("name")
        if not key or not name:
            _logger.warning("Skipping team with missing key or name: %r", t)
            continue
        # Per-team threshold overrides (Improvement #11)
        team_th = t.get("thresholds", {})
        teams.append(
            TeamDef(
                key=key,
                name=name,
                members=t.get("members", []),
                thresholds=team_th if team_th else None,
            )
        )
    return teams


def _build_thresholds(raw: dict[str, Any]) -> Thresholds:
    th = raw.get("thresholds", {})
    return Thresholds(
        overload_points=th.get("overload_points", 20.0),
        overload_issues=th.get("overload_issues", 8),
        wip_limit=th.get("wip_limit", 5),
        aging_days=th.get("aging_days", 14),
        capacity_per_person=th.get("capacity_per_person", 13.0),
    )


def _build_output(raw: dict[str, Any]) -> OutputConfig:
    o = raw.get("output", {})
    return OutputConfig(
        path=o.get("path", "output/dashboard.html"),
        title=o.get("title", "FlowBoard Dashboard"),
        primary_color=o.get("accent_color", o.get("primary_color", "#fb6400")),
        company_name=o.get("company_name", ""),
    )


def _build_branding(raw: dict[str, Any], output: OutputConfig) -> BrandingConfig:
    b = raw.get("branding", {})
    return BrandingConfig(
        title=b.get("title", output.title),
        subtitle=b.get("subtitle", "Jira-Based Delivery & Workload Intelligence"),
        primary_color=b.get("accent_color", b.get("primary_color", output.primary_color)),
        secondary_color=b.get("secondary_color", "#002754e6"),
        tertiary_color=b.get("tertiary_color", "#666666"),
        company_name=b.get("company_name", output.company_name),
    )


def _build_dashboard(raw: dict[str, Any], output: OutputConfig) -> DashboardConfig:
    d = raw.get("dashboard", {})
    branding = _build_branding(d, output)
    layout_raw = d.get("layout", {})
    tabs_raw = d.get("tabs", {})
    cards_raw = d.get("summary_cards", {})
    charts_raw = d.get("charts", {})
    tables_raw = d.get("tables", {})
    filters_raw = d.get("filters", {})
    risk_raw = d.get("risk_display", {})
    roadmap_raw = d.get("roadmap", {})
    timeline_raw = d.get("timeline", {})
    theme = d.get("theme", "system")
    if theme not in ("light", "dark", "midnight", "system"):
        theme = "light"

    return DashboardConfig(
        theme=theme,
        branding=branding,
        layout=LayoutConfig(
            density=layout_raw.get("density", "comfortable"),
            max_width=layout_raw.get("max_width", "1440px"),
        ),
        tabs=TabsConfig(
            visible=tabs_raw.get("visible", list(_DEFAULT_TABS)),
            order=tabs_raw.get("order", list(_DEFAULT_TABS)),
            default_tab=tabs_raw.get("default_tab", "overview"),
        ),
        summary_cards=SummaryCardsConfig(
            visible=cards_raw.get("visible", list(_DEFAULT_SUMMARY_CARDS)),
        ),
        charts=ChartsConfig(
            enabled=charts_raw.get("enabled", True),
            status_distribution=charts_raw.get("status_distribution", True),
            type_distribution=charts_raw.get("type_distribution", True),
            risk_severity=charts_raw.get("risk_severity", True),
            team_workload=charts_raw.get("team_workload", True),
            sprint_progress=charts_raw.get("sprint_progress", True),
            workload_per_person=charts_raw.get("workload_per_person", True),
        ),
        tables=TablesConfig(
            issues_columns=tables_raw.get("issues_columns", list(_DEFAULT_ISSUES_COLUMNS)),
            max_rows=tables_raw.get("max_rows", 200),
            default_sort=tables_raw.get("default_sort", "key"),
            sort_direction=tables_raw.get("sort_direction", "asc"),
        ),
        filters=FiltersConfig(
            default_teams=filters_raw.get("default_teams", []),
            default_sprints=filters_raw.get("default_sprints", []),
            default_statuses=filters_raw.get("default_statuses", []),
            default_types=filters_raw.get("default_types", []),
            default_priorities=filters_raw.get("default_priorities", []),
        ),
        risk_display=RiskDisplayConfig(
            show_severity_badges=risk_raw.get("show_severity_badges", True),
            show_recommendations=risk_raw.get("show_recommendations", True),
            highlight_blocked=risk_raw.get("highlight_blocked", True),
        ),
        roadmap=RoadmapDisplayConfig(
            time_window_months=roadmap_raw.get("time_window_months", 3),
            default_zoom=roadmap_raw.get("default_zoom", 100),
            show_dependencies=roadmap_raw.get("show_dependencies", True),
            show_risk_badges=roadmap_raw.get("show_risk_badges", True),
        ),
        timeline=TimelineDisplayConfig(
            default_mode=timeline_raw.get("default_mode", "assignee"),
            default_zoom=timeline_raw.get("default_zoom", 100),
            max_swimlanes=timeline_raw.get("max_swimlanes", 30),
            show_overlaps=timeline_raw.get("show_overlaps", True),
            show_sprint_boundaries=timeline_raw.get("show_sprint_boundaries", True),
            show_today_marker=timeline_raw.get("show_today_marker", True),
            compact_bar_height=timeline_raw.get("compact_bar_height", False),
        ),
        sections_collapsed=d.get("sections_collapsed", []),
        refresh_metadata=d.get("refresh_metadata", True),
    )


def _build_pi(raw: dict[str, Any]) -> PIConfig:
    p = raw.get("pi", {})
    return PIConfig(
        enabled=p.get("enabled", False),
        name=p.get("name", ""),
        start_date=p.get("start_date", ""),
        sprints_per_pi=p.get("sprints_per_pi", 5),
        sprint_length_days=p.get("sprint_length_days", 10),
        working_days=p.get("working_days", list(_DEFAULT_WORKING_DAYS)),
        show_weekends=p.get("show_weekends", False),
        date_format=p.get("date_format", "%b %d"),
        show_today_marker=p.get("show_today_marker", True),
        show_sprint_boundaries=p.get("show_sprint_boundaries", True),
        show_progress_indicator=p.get("show_progress_indicator", True),
        show_remaining_days=p.get("show_remaining_days", True),
    )


def _build_simulation(raw: dict[str, Any]) -> SimulationConfig:
    s = raw.get("simulation", {})
    return SimulationConfig(
        enabled=s.get("enabled", True),
    )


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------


def _warn_embedded_credentials(raw: dict[str, Any]) -> None:
    """Blocker #3: warn if credentials are embedded in config files."""
    jira = raw.get("jira", {})
    for key in ("auth_token", "pat", "password"):
        if jira.get(key):
            _logger.warning(
                "Credential '%s' found in config file. "
                "Use environment variables (FLOWBOARD_JIRA_TOKEN) instead.",
                key,
            )


def _validate_output_path(output_path: str) -> None:
    """Blocker #12: prevent path traversal in output path."""
    resolved = Path(output_path).resolve()
    cwd = Path.cwd().resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError:
        raise ValueError(
            f"Output path '{output_path}' resolves outside the current directory. "
            "Use a relative path within the project."
        ) from None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> FlowBoardConfig:
    """Load, validate, and parse a FlowBoard JSON config file.

    Environment variables ``FLOWBOARD_JIRA_TOKEN``, ``FLOWBOARD_JIRA_EMAIL``,
    and ``FLOWBOARD_JIRA_URL`` override the corresponding fields.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    # Blocker #3: warn if credentials appear in the config file
    _warn_embedded_credentials(raw)

    raw = _apply_env_overrides(raw)
    validate_config_dict(raw)

    cfg = _build_full_config(raw)

    # Blocker #12: validate output path is safe
    _validate_output_path(cfg.output.path)

    return cfg


def load_config_from_dict(raw: dict[str, Any]) -> FlowBoardConfig:
    """Build config from a plain dict (useful for tests and programmatic use)."""
    import copy

    raw = _apply_env_overrides(copy.deepcopy(raw))
    validate_config_dict(raw)
    return _build_full_config(raw)


def config_to_dict(config: FlowBoardConfig) -> dict[str, Any]:
    """Serialize a FlowBoardConfig back to a JSON-safe dict (for export/round-trip).

    .. note::
        Authentication credentials (``email``, ``api_token``, ``pat``) are
        intentionally **omitted** from the exported dict to prevent accidental
        credential leakage in exported/shared configuration files.
    """
    return {
        "jira": {
            "base_url": config.jira.base_url,
            "server_type": config.jira.server_type,
            "auth_method": config.jira.auth_method,
            "api_version": config.jira.api_version,
            "projects": config.jira.projects,
            "boards": config.jira.boards,
            "max_results": config.jira.max_results,
            "jql_filter": config.jira.jql_filter,
        },
        "field_mappings": {
            "story_points": config.field_mappings.story_points,
            "epic_link": config.field_mappings.epic_link,
            "sprint": config.field_mappings.sprint,
            **config.field_mappings.extra,
        },
        "status_mapping": config.status_mapping,
        "teams": [{"key": t.key, "name": t.name, "members": t.members} for t in config.teams],
        "thresholds": {
            "overload_points": config.thresholds.overload_points,
            "overload_issues": config.thresholds.overload_issues,
            "wip_limit": config.thresholds.wip_limit,
            "aging_days": config.thresholds.aging_days,
            "capacity_per_person": config.thresholds.capacity_per_person,
        },
        "blocked_link_types": config.blocked_link_types,
        "output": {
            "path": config.output.path,
            "title": config.output.title,
            "primary_color": config.output.primary_color,
            "company_name": config.output.company_name,
        },
        "dashboard": _dashboard_to_dict(config.dashboard),
        "pi": _pi_to_dict(config.pi),
        "simulation": {"enabled": config.simulation.enabled},
        "locale": config.locale,
        "methodology": config.methodology,
    }


def _dashboard_to_dict(d: DashboardConfig) -> dict[str, Any]:
    return {
        "theme": d.theme,
        "branding": {
            "title": d.branding.title,
            "subtitle": d.branding.subtitle,
            "primary_color": d.branding.primary_color,
            "secondary_color": d.branding.secondary_color,
            "tertiary_color": d.branding.tertiary_color,
            "company_name": d.branding.company_name,
        },
        "layout": {"density": d.layout.density, "max_width": d.layout.max_width},
        "tabs": {
            "visible": d.tabs.visible,
            "order": d.tabs.order,
            "default_tab": d.tabs.default_tab,
        },
        "summary_cards": {"visible": d.summary_cards.visible},
        "charts": {
            "enabled": d.charts.enabled,
            "status_distribution": d.charts.status_distribution,
            "type_distribution": d.charts.type_distribution,
            "risk_severity": d.charts.risk_severity,
            "team_workload": d.charts.team_workload,
            "sprint_progress": d.charts.sprint_progress,
            "workload_per_person": d.charts.workload_per_person,
        },
        "tables": {
            "issues_columns": d.tables.issues_columns,
            "max_rows": d.tables.max_rows,
            "default_sort": d.tables.default_sort,
            "sort_direction": d.tables.sort_direction,
        },
        "filters": {
            "default_teams": d.filters.default_teams,
            "default_sprints": d.filters.default_sprints,
            "default_statuses": d.filters.default_statuses,
            "default_types": d.filters.default_types,
            "default_priorities": d.filters.default_priorities,
        },
        "risk_display": {
            "show_severity_badges": d.risk_display.show_severity_badges,
            "show_recommendations": d.risk_display.show_recommendations,
            "highlight_blocked": d.risk_display.highlight_blocked,
        },
        "roadmap": {
            "time_window_months": d.roadmap.time_window_months,
            "default_zoom": d.roadmap.default_zoom,
            "show_dependencies": d.roadmap.show_dependencies,
            "show_risk_badges": d.roadmap.show_risk_badges,
        },
        "timeline": {
            "default_mode": d.timeline.default_mode,
            "default_zoom": d.timeline.default_zoom,
            "max_swimlanes": d.timeline.max_swimlanes,
            "show_overlaps": d.timeline.show_overlaps,
            "show_sprint_boundaries": d.timeline.show_sprint_boundaries,
            "show_today_marker": d.timeline.show_today_marker,
            "compact_bar_height": d.timeline.compact_bar_height,
        },
        "sections_collapsed": d.sections_collapsed,
        "refresh_metadata": d.refresh_metadata,
    }


def _pi_to_dict(p: PIConfig) -> dict[str, Any]:
    return {
        "enabled": p.enabled,
        "name": p.name,
        "start_date": p.start_date,
        "sprints_per_pi": p.sprints_per_pi,
        "sprint_length_days": p.sprint_length_days,
        "working_days": p.working_days,
        "show_weekends": p.show_weekends,
        "date_format": p.date_format,
        "show_today_marker": p.show_today_marker,
        "show_sprint_boundaries": p.show_sprint_boundaries,
        "show_progress_indicator": p.show_progress_indicator,
        "show_remaining_days": p.show_remaining_days,
    }


def _build_full_config(raw: dict[str, Any]) -> FlowBoardConfig:
    """Assemble a FlowBoardConfig from a validated raw dict."""
    methodology = _validate_methodology(raw.get("methodology", "scrum"))

    # Apply methodology preset defaults (user values take precedence)
    from flowboard.infrastructure.config.presets import apply_preset

    raw = apply_preset(raw, methodology)

    output = _build_output(raw)
    locale = raw.get("locale", "en")
    return FlowBoardConfig(
        jira=_build_jira_config(raw),
        field_mappings=_build_field_mappings(raw),
        status_mapping=raw.get("status_mapping", {}),
        teams=_build_teams(raw),
        thresholds=_build_thresholds(raw),
        blocked_link_types=raw.get("blocked_link_types", ["Blocks", "is blocked by"]),
        output=output,
        dashboard=_build_dashboard(raw, output),
        pi=_build_pi(raw),
        simulation=_build_simulation(raw),
        locale=_validate_locale(locale),
        methodology=methodology,
    )
