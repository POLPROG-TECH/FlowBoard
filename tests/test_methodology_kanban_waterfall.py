"""Kanban and Waterfall methodology tests - cycle time, throughput, WIP, CFD, flow metrics, waterfall phases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flowboard.domain.kanban_compute import (
    compute_cfd,
    compute_cycle_times,
    compute_flow_metrics,
    compute_kanban_insights,
    compute_throughput,
    compute_wip_snapshot,
)
from flowboard.domain.kanban_models import (
    CFDDataPoint,
    CycleTimeRecord,
    FlowMetrics,
    KanbanInsights,
    ThroughputRecord,
    WIPSnapshot,
)
from flowboard.domain.models import BoardSnapshot, Issue, Person
from flowboard.i18n.translator import Translator
from flowboard.infrastructure.config.loader import (
    load_config_from_dict,
)
from flowboard.presentation.html.renderer import render_dashboard
from flowboard.shared.types import IssueStatus, StatusCategory

# ===================================================================
# Helpers
# ===================================================================


def _make_config(methodology: str = "scrum", locale: str = "en", **overrides):
    raw = {
        "jira": {"base_url": "https://test.atlassian.net"},
        "output": {"title": "Test Board"},
        "methodology": methodology,
        "locale": locale,
        **overrides,
    }
    return load_config_from_dict(raw)


def _make_issue(
    key: str,
    status_cat: StatusCategory = StatusCategory.TODO,
    created_days_ago: int = 10,
    resolved_days_ago: int | None = None,
    assignee_name: str = "Dev A",
    team: str = "Alpha",
    points: float = 3.0,
) -> Issue:
    now = datetime.now(tz=UTC)
    created = now - timedelta(days=created_days_ago)
    resolved = (now - timedelta(days=resolved_days_ago)) if resolved_days_ago is not None else None
    status = IssueStatus.DONE if status_cat == StatusCategory.DONE else IssueStatus.IN_PROGRESS
    return Issue(
        key=key,
        summary=f"Test issue {key}",
        status=status,
        status_category=status_cat,
        created=created,
        resolved=resolved,
        assignee=Person(
            account_id=f"acc-{assignee_name.lower().replace(' ', '-')}",
            display_name=assignee_name,
            team=team,
        ),
        story_points=points,
    )


def _render(methodology: str = "scrum", locale: str = "en") -> str:
    cfg = _make_config(methodology=methodology, locale=locale)
    snap = BoardSnapshot(title="Test Board")
    return render_dashboard(snap, cfg)


# ===================================================================
# Phase 1: Config & Presets
# ===================================================================


class TestCycleTimeComputation:
    """GIVEN cycle time computation and the scenario: compute cycle times for done issues"""
    def test_compute_cycle_times_for_done_issues(self):
        """WHEN the code under test is exercised for: compute cycle times for done issues"""
        issues = [
            _make_issue("KAN-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("KAN-2", StatusCategory.DONE, created_days_ago=10, resolved_days_ago=2),
            _make_issue("KAN-3", StatusCategory.IN_PROGRESS, created_days_ago=5),
        ]
        records = compute_cycle_times(issues)

        """THEN the expected behaviour holds: compute cycle times for done issues"""
        assert len(records) == 2  # only done issues
        assert all(r.cycle_time_days > 0 for r in records)
        assert all(r.lead_time_days > 0 for r in records)

    """GIVEN cycle time computation and the scenario: cycle time is fraction of lead time"""
    def test_cycle_time_is_fraction_of_lead_time(self):
        """WHEN the code under test is exercised for: cycle time is fraction of lead time"""
        issues = [
            _make_issue("KAN-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=0)
        ]
        records = compute_cycle_times(issues)

        """THEN the expected behaviour holds: cycle time is fraction of lead time"""
        assert len(records) == 1
        assert records[0].cycle_time_days < records[0].lead_time_days

    """GIVEN cycle time computation and the scenario: empty issues returns empty"""
    def test_empty_issues_returns_empty(self):
        """THEN the expected behaviour holds: empty issues returns empty"""
        assert compute_cycle_times([]) == []


class TestThroughput:
    """GIVEN throughput and the scenario: compute throughput buckets"""
    def test_compute_throughput_buckets(self):
        """WHEN the code under test is exercised for: compute throughput buckets"""
        issues = [
            _make_issue("KAN-1", StatusCategory.DONE, created_days_ago=10, resolved_days_ago=3),
            _make_issue("KAN-2", StatusCategory.DONE, created_days_ago=12, resolved_days_ago=3),
            _make_issue("KAN-3", StatusCategory.DONE, created_days_ago=15, resolved_days_ago=10),
        ]
        records = compute_throughput(issues, weeks=4)

        """THEN the expected behaviour holds: compute throughput buckets"""
        assert len(records) > 0
        assert all(isinstance(r, ThroughputRecord) for r in records)
        total = sum(r.count for r in records)
        assert total == 3

    """GIVEN throughput and the scenario: empty issues returns zero throughput"""
    def test_empty_issues_returns_zero_throughput(self):
        """WHEN the code under test is exercised for: empty issues returns zero throughput"""
        records = compute_throughput([], weeks=2)

        """THEN the expected behaviour holds: empty issues returns zero throughput"""
        assert all(r.count == 0 for r in records)


class TestWIPSnapshot:
    """GIVEN w i p snapshot and the scenario: wip counts in progress"""
    def test_wip_counts_in_progress(self):
        """WHEN the code under test is exercised for: wip counts in progress"""
        issues = [
            _make_issue("W-1", StatusCategory.IN_PROGRESS, assignee_name="Alice"),
            _make_issue("W-2", StatusCategory.IN_PROGRESS, assignee_name="Alice"),
            _make_issue("W-3", StatusCategory.IN_PROGRESS, assignee_name="Bob"),
            _make_issue("W-4", StatusCategory.TODO),
            _make_issue("W-5", StatusCategory.DONE, resolved_days_ago=1),
        ]
        wip = compute_wip_snapshot(issues, wip_limit=1)

        """THEN the expected behaviour holds: wip counts in progress"""
        assert wip.wip_count == 3
        assert wip.wip_by_person["Alice"] == 2
        assert wip.wip_by_person["Bob"] == 1
        assert "Alice" in wip.violations  # over limit of 1
        assert "Bob" not in wip.violations  # exactly at limit

    """GIVEN w i p snapshot and the scenario: no violations when under limit"""
    def test_no_violations_when_under_limit(self):
        """WHEN the code under test is exercised for: no violations when under limit"""
        issues = [_make_issue("W-1", StatusCategory.IN_PROGRESS)]
        wip = compute_wip_snapshot(issues, wip_limit=5)

        """THEN the expected behaviour holds: no violations when under limit"""
        assert wip.violations == []


class TestCFD:
    """GIVEN c f d and the scenario: cfd returns data points"""
    def test_cfd_returns_data_points(self):
        """WHEN the code under test is exercised for: cfd returns data points"""
        issues = [
            _make_issue("C-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("C-2", StatusCategory.IN_PROGRESS, created_days_ago=10),
            _make_issue("C-3", StatusCategory.TODO, created_days_ago=3),
        ]
        cfd = compute_cfd(issues, days=15)

        """THEN the expected behaviour holds: cfd returns data points"""
        assert len(cfd) == 16  # 15 days + today
        assert all(isinstance(pt, CFDDataPoint) for pt in cfd)
        # Last point should have at least 1 done
        last = cfd[-1]
        assert last.done >= 1


class TestFlowMetrics:
    """GIVEN flow metrics and the scenario: aggregate metrics"""
    def test_aggregate_metrics(self):
        """WHEN the code under test is exercised for: aggregate metrics"""
        ct_records = [
            CycleTimeRecord(key="X-1", summary="a", cycle_time_days=5.0, lead_time_days=10.0),
            CycleTimeRecord(key="X-2", summary="b", cycle_time_days=3.0, lead_time_days=8.0),
        ]
        tp_records = [
            ThroughputRecord(count=4, story_points=20.0),
            ThroughputRecord(count=6, story_points=30.0),
        ]
        wip = WIPSnapshot(wip_count=3, violations=["Alice"])
        fm = compute_flow_metrics(ct_records, tp_records, wip, wip_limit=2)

        """THEN the expected behaviour holds: aggregate metrics"""
        assert fm.avg_cycle_time == 4.0
        assert fm.throughput_per_week == 5.0
        assert fm.current_wip == 3
        assert fm.wip_violations == 1
        assert 0 < fm.flow_efficiency <= 1.0


class TestKanbanInsightsOrchestrator:
    """GIVEN kanban insights orchestrator and the scenario: compute kanban insights complete"""
    def test_compute_kanban_insights_complete(self):
        """WHEN the code under test is exercised for: compute kanban insights complete"""
        issues = [
            _make_issue("K-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("K-2", StatusCategory.IN_PROGRESS, created_days_ago=10),
            _make_issue("K-3", StatusCategory.TODO, created_days_ago=3),
        ]
        insights = compute_kanban_insights(issues, wip_limit=3)

        """THEN the expected behaviour holds: compute kanban insights complete"""
        assert isinstance(insights, KanbanInsights)
        assert isinstance(insights.flow_metrics, FlowMetrics)
        assert len(insights.cycle_times) >= 1
        assert len(insights.throughput) > 0
        assert len(insights.cfd_data) > 0
        assert insights.wip_snapshot.wip_count == 1


# ===================================================================
# Phase 4: Kanban UI Components
# ===================================================================


class TestKanbanComponents:
    def _get_insights(self) -> KanbanInsights:
        issues = [
            _make_issue("K-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("K-2", StatusCategory.DONE, created_days_ago=15, resolved_days_ago=3),
            _make_issue("K-3", StatusCategory.IN_PROGRESS, created_days_ago=10),
        ]
        return compute_kanban_insights(issues)

    """GIVEN kanban components and the scenario: flow metrics cards render"""
    def test_flow_metrics_cards_render(self):
        """WHEN the code under test is exercised for: flow metrics cards render"""
        from flowboard.presentation.html.components_kanban import flow_metrics_cards

        t = Translator("en")
        html = flow_metrics_cards(self._get_insights(), t=t)

        """THEN the expected behaviour holds: flow metrics cards render"""
        assert "kanban-metrics-grid" in html
        assert "metric-card" in html
        assert "Avg Cycle Time" in html

    """GIVEN kanban components and the scenario: flow metrics cards none"""
    def test_flow_metrics_cards_none(self):
        """WHEN the code under test is exercised for: flow metrics cards none"""
        from flowboard.presentation.html.components_kanban import flow_metrics_cards

        t = Translator("en")
        html = flow_metrics_cards(None, t=t)

        """THEN the expected behaviour holds: flow metrics cards none"""
        assert "empty-state" in html

    """GIVEN kanban components and the scenario: wip monitor render"""
    def test_wip_monitor_render(self):
        """WHEN the code under test is exercised for: wip monitor render"""
        from flowboard.presentation.html.components_kanban import wip_monitor

        t = Translator("en")
        html = wip_monitor(self._get_insights(), t=t)

        """THEN the expected behaviour holds: wip monitor render"""
        assert "wip-monitor" in html or "empty-state" in html

    """GIVEN kanban components and the scenario: cycle time table render"""
    def test_cycle_time_table_render(self):
        """WHEN the code under test is exercised for: cycle time table render"""
        from flowboard.presentation.html.components_kanban import cycle_time_table

        t = Translator("en")
        html = cycle_time_table(self._get_insights(), t=t)

        """THEN the expected behaviour holds: cycle time table render"""
        assert "cycle-time-table" in html
        assert "K-1" in html

    """GIVEN kanban components and the scenario: throughput chart data json"""
    def test_throughput_chart_data_json(self):
        """WHEN the code under test is exercised for: throughput chart data json"""
        from flowboard.presentation.html.components_kanban import throughput_chart_data

        t = Translator("en")
        data = throughput_chart_data(self._get_insights(), t=t)

        """THEN the expected behaviour holds: throughput chart data json"""
        assert data != "null"
        assert "Items Completed" in data

    """GIVEN kanban components and the scenario: cfd chart data json"""
    def test_cfd_chart_data_json(self):
        """WHEN the code under test is exercised for: cfd chart data json"""
        from flowboard.presentation.html.components_kanban import cfd_chart_data

        t = Translator("en")
        data = cfd_chart_data(self._get_insights(), t=t)

        """THEN the expected behaviour holds: cfd chart data json"""
        assert data != "null"
        assert "Done" in data

    """GIVEN kanban components and the scenario: flow tab html complete"""
    def test_flow_tab_html_complete(self):
        """WHEN the code under test is exercised for: flow tab html complete"""
        from flowboard.presentation.html.components_kanban import flow_tab_html

        t = Translator("en")
        html = flow_tab_html(self._get_insights(), t=t)

        """THEN the expected behaviour holds: flow tab html complete"""
        assert "flow-metrics" in html
        assert "wip-monitor" in html or "empty-state" in html
        assert "throughputChart" in html
        assert "cfdChart" in html
        assert "cycle-times" in html


# ===================================================================
# Phase 6: Adaptive Tab System
# ===================================================================


class TestBoardSnapshotKanban:
    """GIVEN board snapshot kanban and the scenario: kanban insights field exists"""
    def test_kanban_insights_field_exists(self):
        """WHEN the code under test is exercised for: kanban insights field exists"""
        snap = BoardSnapshot(title="Test")

        """THEN the expected behaviour holds: kanban insights field exists"""
        assert snap.kanban_insights is None

    """GIVEN board snapshot kanban and the scenario: kanban insights can be set"""
    def test_kanban_insights_can_be_set(self):
        """WHEN the code under test is exercised for: kanban insights can be set"""
        ki = KanbanInsights()
        snap = BoardSnapshot(title="Test", kanban_insights=ki)

        """THEN the expected behaviour holds: kanban insights can be set"""
        assert snap.kanban_insights is ki


# ===================================================================
# CSS: Kanban component styles
# ===================================================================


class TestKanbanCSS:
    """GIVEN kanban c s s and the scenario: kanban metrics grid css"""
    def test_kanban_metrics_grid_css(self):
        """WHEN the code under test is exercised for: kanban metrics grid css"""
        from pathlib import Path

        css = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "flowboard"
            / "presentation"
            / "html"
            / "templates"
            / "_styles_base.html"
        ).read_text()

        """THEN the expected behaviour holds: kanban metrics grid css"""
        assert ".kanban-metrics-grid" in css
        assert ".metric-card" in css
        assert ".wip-bar-fill" in css
        assert ".wip-monitor" in css


# ===================================================================
# Waterfall Domain Analytics
# ===================================================================


class TestWaterfallModels:
    """GIVEN waterfall models and the scenario: waterfall insights dataclass"""
    def test_waterfall_insights_dataclass(self):
        """WHEN the code under test is exercised for: waterfall insights dataclass"""
        from flowboard.domain.waterfall_models import WaterfallInsights

        wi = WaterfallInsights()

        """THEN the expected behaviour holds: waterfall insights dataclass"""
        assert wi.phases == []
        assert wi.milestones == []
        assert wi.critical_path == []
        assert wi.phase_progress.total_phases == 0

    """GIVEN waterfall models and the scenario: phase dataclass"""
    def test_phase_dataclass(self):
        """WHEN the code under test is exercised for: phase dataclass"""
        from flowboard.domain.waterfall_models import Phase

        p = Phase(key="v1.0", name="Release 1.0", progress_pct=75.0)

        """THEN the expected behaviour holds: phase dataclass"""
        assert p.progress_pct == 75.0


class TestWaterfallCompute:
    def _make_waterfall_issues(self):
        from flowboard.domain.models import Issue, Person
        from flowboard.shared.types import StatusCategory

        now = datetime.now(tz=UTC)
        return [
            Issue(
                key="WF-1",
                summary="Design spec",
                status_category=StatusCategory.DONE,
                fix_versions=["v1.0"],
                created=now - timedelta(days=30),
                resolved=now - timedelta(days=10),
                assignee=Person(account_id="a1", display_name="Alice", team="Design"),
                story_points=5,
            ),
            Issue(
                key="WF-2",
                summary="Implement feature",
                status_category=StatusCategory.IN_PROGRESS,
                fix_versions=["v1.0"],
                created=now - timedelta(days=20),
                assignee=Person(account_id="a2", display_name="Bob", team="Dev"),
                story_points=8,
            ),
            Issue(
                key="WF-3",
                summary="Write tests",
                status_category=StatusCategory.TODO,
                fix_versions=["v2.0"],
                created=now - timedelta(days=5),
                assignee=Person(account_id="a3", display_name="Charlie", team="QA"),
                story_points=3,
            ),
        ]

    """GIVEN waterfall compute and the scenario: compute waterfall insights"""
    def test_compute_waterfall_insights(self):
        """WHEN the code under test is exercised for: compute waterfall insights"""
        from flowboard.domain.waterfall_compute import compute_waterfall_insights

        issues = self._make_waterfall_issues()
        insights = compute_waterfall_insights(issues)

        """THEN the expected behaviour holds: compute waterfall insights"""
        assert len(insights.phases) == 2  # v1.0 and v2.0
        assert insights.phase_progress.total_phases == 2

    """GIVEN waterfall compute and the scenario: phases have progress"""
    def test_phases_have_progress(self):
        """WHEN the code under test is exercised for: phases have progress"""
        from flowboard.domain.waterfall_compute import compute_waterfall_insights

        issues = self._make_waterfall_issues()
        insights = compute_waterfall_insights(issues)
        v1 = next(p for p in insights.phases if p.key == "v1.0")

        """THEN the expected behaviour holds: phases have progress"""
        assert v1.progress_pct == 50.0  # 1 of 2 done
        assert v1.done_issues == 1
        assert v1.total_issues == 2


# ===================================================================
# Waterfall UI Components
# ===================================================================


class TestWaterfallComponents:
    def _get_insights(self):
        from flowboard.domain.models import Issue, Person
        from flowboard.domain.waterfall_compute import compute_waterfall_insights
        from flowboard.shared.types import StatusCategory

        now = datetime.now(tz=UTC)
        issues = [
            Issue(
                key="WF-1",
                summary="Done item",
                status_category=StatusCategory.DONE,
                fix_versions=["Phase 1"],
                created=now - timedelta(days=30),
                resolved=now - timedelta(days=10),
                assignee=Person(account_id="a1", display_name="Alice", team="Dev"),
            ),
            Issue(
                key="WF-2",
                summary="WIP item",
                status_category=StatusCategory.IN_PROGRESS,
                fix_versions=["Phase 1"],
                created=now - timedelta(days=20),
                assignee=Person(account_id="a2", display_name="Bob", team="Dev"),
            ),
        ]
        return compute_waterfall_insights(issues)

    """GIVEN waterfall components and the scenario: phase progress cards render"""
    def test_phase_progress_cards_render(self):
        """WHEN the code under test is exercised for: phase progress cards render"""
        from flowboard.presentation.html.components_waterfall import phase_progress_cards

        t = Translator("en")
        html = phase_progress_cards(self._get_insights(), t=t)

        """THEN the expected behaviour holds: phase progress cards render"""
        assert "metric-card" in html
        assert "Overall Progress" in html

    """GIVEN waterfall components and the scenario: phase progress cards none"""
    def test_phase_progress_cards_none(self):
        """WHEN the code under test is exercised for: phase progress cards none"""
        from flowboard.presentation.html.components_waterfall import phase_progress_cards

        t = Translator("en")
        html = phase_progress_cards(None, t=t)

        """THEN the expected behaviour holds: phase progress cards none"""
        assert "empty-state" in html

    """GIVEN waterfall components and the scenario: phase table render"""
    def test_phase_table_render(self):
        """WHEN the code under test is exercised for: phase table render"""
        from flowboard.presentation.html.components_waterfall import phase_table

        t = Translator("en")
        html = phase_table(self._get_insights(), t=t)

        """THEN the expected behaviour holds: phase table render"""
        assert "phase-table" in html
        assert "Phase 1" in html

    """GIVEN waterfall components and the scenario: milestone timeline render"""
    def test_milestone_timeline_render(self):
        """WHEN the code under test is exercised for: milestone timeline render"""
        from flowboard.presentation.html.components_waterfall import milestone_timeline

        t = Translator("en")
        html = milestone_timeline(self._get_insights(), t=t)
        # May have milestones if phases have end dates

        """THEN the expected behaviour holds: milestone timeline render"""
        assert "milestone" in html or "empty-state" in html

    """GIVEN waterfall components and the scenario: phases tab html complete"""
    def test_phases_tab_html_complete(self):
        """WHEN the code under test is exercised for: phases tab html complete"""
        from flowboard.presentation.html.components_waterfall import phases_tab_html

        t = Translator("en")
        html = phases_tab_html(self._get_insights(), t=t)

        """THEN the expected behaviour holds: phases tab html complete"""
        assert "phase-progress" in html
        assert "phase-details" in html
        assert "milestones" in html
        assert "critical-path" in html


# ===================================================================
# Waterfall Adaptive Tabs
# ===================================================================


class TestWaterfallTabs:
    """GIVEN waterfall tabs and the scenario: waterfall renders phases no sprints"""
    def test_waterfall_renders_phases_no_sprints(self):
        """WHEN the code under test is exercised for: waterfall renders phases no sprints"""
        html = _render("waterfall")

        """THEN the expected behaviour holds: waterfall renders phases no sprints"""
        assert "tab-phases" in html
        assert "tab-sprints" not in html
        assert "tab-flow" not in html

    """GIVEN waterfall tabs and the scenario: waterfall has phases button"""
    def test_waterfall_has_phases_button(self):
        """WHEN the code under test is exercised for: waterfall has phases button"""
        html = _render("waterfall")

        """THEN the expected behaviour holds: waterfall has phases button"""
        assert "tab-phases-btn" in html

    """GIVEN waterfall tabs and the scenario: waterfall pl renders"""
    def test_waterfall_pl_renders(self):
        """WHEN the code under test is exercised for: waterfall pl renders"""
        html = _render("waterfall", "pl")

        """THEN the expected behaviour holds: waterfall pl renders"""
        assert "Fazy" in html


# ===================================================================
# Waterfall i18n
# ===================================================================


class TestWaterfallI18n:
    """GIVEN waterfall i18n and the scenario: en has waterfall keys"""
    def test_en_has_waterfall_keys(self):
        """WHEN the code under test is exercised for: en has waterfall keys"""
        t = Translator("en")

        """THEN the expected behaviour holds: en has waterfall keys"""
        assert t.has("waterfall.phases")
        assert t.has("waterfall.milestones")
        assert t.has("waterfall.critical_path")
        assert t.has("tab.phases")

    """GIVEN waterfall i18n and the scenario: pl has waterfall keys"""
    def test_pl_has_waterfall_keys(self):
        """WHEN the code under test is exercised for: pl has waterfall keys"""
        t = Translator("pl")

        """THEN the expected behaviour holds: pl has waterfall keys"""
        assert t.has("waterfall.phases")
        assert t.has("waterfall.milestones")
        assert t.has("tab.phases")

    """GIVEN waterfall i18n and the scenario: en waterfall labels"""
    def test_en_waterfall_labels(self):
        """WHEN the code under test is exercised for: en waterfall labels"""
        t = Translator("en")

        """THEN the expected behaviour holds: en waterfall labels"""
        assert t("waterfall.phases") == "Phases"
        assert t("tab.phases") == "📋 Phases"

    """GIVEN waterfall i18n and the scenario: pl waterfall labels"""
    def test_pl_waterfall_labels(self):
        """WHEN the code under test is exercised for: pl waterfall labels"""
        t = Translator("pl")

        """THEN the expected behaviour holds: pl waterfall labels"""
        assert t("waterfall.phases") == "Fazy"
        assert t("tab.phases") == "📋 Fazy"


# ===================================================================
# Waterfall CSS
# ===================================================================


class TestWaterfallCSS:
    """GIVEN waterfall c s s and the scenario: milestone css exists"""
    def test_milestone_css_exists(self):
        """WHEN the code under test is exercised for: milestone css exists"""
        from pathlib import Path

        css = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "flowboard"
            / "presentation"
            / "html"
            / "templates"
            / "_styles_base.html"
        ).read_text()

        """THEN the expected behaviour holds: milestone css exists"""
        assert ".milestone-list" in css
        assert ".milestone-item" in css
        assert ".milestone-name" in css


# ===================================================================
# BoardSnapshot Waterfall
# ===================================================================


class TestBoardSnapshotWaterfall:
    """GIVEN board snapshot waterfall and the scenario: waterfall insights field exists"""
    def test_waterfall_insights_field_exists(self):
        """WHEN the code under test is exercised for: waterfall insights field exists"""
        snap = BoardSnapshot(title="Test")

        """THEN the expected behaviour holds: waterfall insights field exists"""
        assert snap.waterfall_insights is None

    """GIVEN board snapshot waterfall and the scenario: waterfall insights can be set"""
    def test_waterfall_insights_can_be_set(self):
        """WHEN the code under test is exercised for: waterfall insights can be set"""
        from flowboard.domain.waterfall_models import WaterfallInsights

        wi = WaterfallInsights()
        snap = BoardSnapshot(title="Test", waterfall_insights=wi)

        """THEN the expected behaviour holds: waterfall insights can be set"""
        assert snap.waterfall_insights is wi


# ===================================================================
# Phase 8: Hybrid, Custom, Auto-detect
# ===================================================================
