"""Configuration data models for FlowBoard."""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Typed config objects — Jira / field / teams / thresholds
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class JiraConfig:
    base_url: str = ""
    auth_token: str = ""
    auth_email: str = ""
    server_type: str = "cloud"  # cloud | server | datacenter
    auth_method: str = "basic"  # basic | pat | oauth
    api_version: str = "2"
    projects: list[str] = field(default_factory=list)
    boards: list[int] = field(default_factory=list)
    max_results: int = 100
    jql_filter: str = ""


@dataclass(slots=True)
class FieldMappings:
    story_points: str = "customfield_10016"
    epic_link: str = "customfield_10014"
    sprint: str = "customfield_10020"
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TeamDef:
    key: str
    name: str
    members: list[str] = field(default_factory=list)
    thresholds: dict | None = None  # Per-team threshold overrides


@dataclass(slots=True)
class Thresholds:
    overload_points: float = 20.0
    overload_issues: int = 8
    wip_limit: int = 5
    aging_days: int = 14
    capacity_per_person: float = 13.0


@dataclass(slots=True)
class OutputConfig:
    path: str = "output/dashboard.html"
    title: str = "FlowBoard Dashboard"
    primary_color: str = "#fb6400"
    company_name: str = ""


# ---------------------------------------------------------------------------
# Dashboard configuration — the full UI/presentation config subsystem
# ---------------------------------------------------------------------------

_DEFAULT_TABS = [
    "overview",
    "workload",
    "sprints",
    "timeline",
    "pi",
    "insights",
    "issues",
]

_DEFAULT_SUMMARY_CARDS = [
    "total_issues",
    "open_issues",
    "blocked",
    "story_points",
    "completed_sp",
    "critical_risks",
    "high_risks",
    "overloaded",
    "conflicts",
]

_DEFAULT_ISSUES_COLUMNS = [
    "key",
    "summary",
    "type",
    "status",
    "assignee",
    "sp",
    "priority",
    "sprint",
    "age",
]

SUPPORTED_METHODOLOGIES = frozenset({"scrum", "kanban", "waterfall", "hybrid", "custom"})


@dataclass(slots=True)
class BrandingConfig:
    title: str = "FlowBoard Dashboard"
    subtitle: str = "Jira-Based Delivery & Workload Intelligence"
    primary_color: str = "#fb6400"
    secondary_color: str = "#002754"
    tertiary_color: str = "#666666"
    company_name: str = ""


@dataclass(slots=True)
class LayoutConfig:
    density: str = "comfortable"  # compact | comfortable | spacious
    max_width: str = "1440px"


@dataclass(slots=True)
class TabsConfig:
    visible: list[str] = field(default_factory=lambda: list(_DEFAULT_TABS))
    order: list[str] = field(default_factory=lambda: list(_DEFAULT_TABS))
    default_tab: str = "overview"


@dataclass(slots=True)
class SummaryCardsConfig:
    visible: list[str] = field(default_factory=lambda: list(_DEFAULT_SUMMARY_CARDS))


@dataclass(slots=True)
class ChartsConfig:
    enabled: bool = True
    status_distribution: bool = True
    type_distribution: bool = True
    risk_severity: bool = True
    team_workload: bool = True
    sprint_progress: bool = True
    workload_per_person: bool = True


@dataclass(slots=True)
class TablesConfig:
    issues_columns: list[str] = field(default_factory=lambda: list(_DEFAULT_ISSUES_COLUMNS))
    max_rows: int = 200
    default_sort: str = "key"
    sort_direction: str = "asc"


@dataclass(slots=True)
class FiltersConfig:
    default_teams: list[str] = field(default_factory=list)
    default_sprints: list[str] = field(default_factory=list)
    default_statuses: list[str] = field(default_factory=list)
    default_types: list[str] = field(default_factory=list)
    default_priorities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskDisplayConfig:
    show_severity_badges: bool = True
    show_recommendations: bool = True
    highlight_blocked: bool = True


@dataclass(slots=True)
class RoadmapDisplayConfig:
    time_window_months: int = 3
    default_zoom: int = 100
    show_dependencies: bool = True
    show_risk_badges: bool = True


@dataclass(slots=True)
class TimelineDisplayConfig:
    """Timeline view presentation settings."""

    default_mode: str = "assignee"  # assignee | team | epic | conflict | executive
    default_zoom: int = 100
    max_swimlanes: int = 30
    show_overlaps: bool = True
    show_sprint_boundaries: bool = True
    show_today_marker: bool = True
    compact_bar_height: bool = False


@dataclass(slots=True)
class DashboardConfig:
    """Comprehensive dashboard presentation configuration."""

    theme: str = "system"  # light | dark | midnight | system
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    tabs: TabsConfig = field(default_factory=TabsConfig)
    summary_cards: SummaryCardsConfig = field(default_factory=SummaryCardsConfig)
    charts: ChartsConfig = field(default_factory=ChartsConfig)
    tables: TablesConfig = field(default_factory=TablesConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    risk_display: RiskDisplayConfig = field(default_factory=RiskDisplayConfig)
    roadmap: RoadmapDisplayConfig = field(default_factory=RoadmapDisplayConfig)
    timeline: TimelineDisplayConfig = field(default_factory=TimelineDisplayConfig)
    sections_collapsed: list[str] = field(default_factory=list)
    refresh_metadata: bool = True


# ---------------------------------------------------------------------------
# PI (Program Increment) configuration
# ---------------------------------------------------------------------------

# ISO weekday: 1=Monday … 7=Sunday
_DEFAULT_WORKING_DAYS = [1, 2, 3, 4, 5]  # Mon-Fri


@dataclass(slots=True)
class PIConfig:
    """Program Increment timing configuration."""

    enabled: bool = False
    name: str = ""
    start_date: str = ""  # ISO date e.g. "2026-03-02"
    sprints_per_pi: int = 5
    sprint_length_days: int = 10  # working days
    working_days: list[int] = field(default_factory=lambda: list(_DEFAULT_WORKING_DAYS))
    show_weekends: bool = False
    date_format: str = "%b %d"
    show_today_marker: bool = True
    show_sprint_boundaries: bool = True
    show_progress_indicator: bool = True
    show_remaining_days: bool = True


# ---------------------------------------------------------------------------
# Simulation (Capacity What-If) configuration
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SimulationConfig:
    """Capacity simulation / what-if planning configuration."""

    enabled: bool = True


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FlowBoardConfig:
    jira: JiraConfig = field(default_factory=JiraConfig)
    field_mappings: FieldMappings = field(default_factory=FieldMappings)
    status_mapping: dict[str, str] = field(default_factory=dict)
    teams: list[TeamDef] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)
    blocked_link_types: list[str] = field(default_factory=lambda: ["Blocks", "is blocked by"])
    output: OutputConfig = field(default_factory=OutputConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    pi: PIConfig = field(default_factory=PIConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    locale: str = "en"
    methodology: str = "scrum"  # scrum | kanban | waterfall | hybrid | custom
