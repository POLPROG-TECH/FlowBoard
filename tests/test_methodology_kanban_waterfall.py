"""Kanban and Waterfall methodology tests — cycle time, throughput, WIP, CFD, flow metrics, waterfall phases."""

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
    def test_compute_cycle_times_for_done_issues(self):
        issues = [
            _make_issue("KAN-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("KAN-2", StatusCategory.DONE, created_days_ago=10, resolved_days_ago=2),
            _make_issue("KAN-3", StatusCategory.IN_PROGRESS, created_days_ago=5),
        ]
        records = compute_cycle_times(issues)
        assert len(records) == 2  # only done issues
        assert all(r.cycle_time_days > 0 for r in records)
        assert all(r.lead_time_days > 0 for r in records)

    def test_cycle_time_is_fraction_of_lead_time(self):
        issues = [
            _make_issue("KAN-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=0)
        ]
        records = compute_cycle_times(issues)
        assert len(records) == 1
        assert records[0].cycle_time_days < records[0].lead_time_days

    def test_empty_issues_returns_empty(self):
        assert compute_cycle_times([]) == []


class TestThroughput:
    def test_compute_throughput_buckets(self):
        issues = [
            _make_issue("KAN-1", StatusCategory.DONE, created_days_ago=10, resolved_days_ago=3),
            _make_issue("KAN-2", StatusCategory.DONE, created_days_ago=12, resolved_days_ago=3),
            _make_issue("KAN-3", StatusCategory.DONE, created_days_ago=15, resolved_days_ago=10),
        ]
        records = compute_throughput(issues, weeks=4)
        assert len(records) > 0
        assert all(isinstance(r, ThroughputRecord) for r in records)
        total = sum(r.count for r in records)
        assert total == 3

    def test_empty_issues_returns_zero_throughput(self):
        records = compute_throughput([], weeks=2)
        assert all(r.count == 0 for r in records)


class TestWIPSnapshot:
    def test_wip_counts_in_progress(self):
        issues = [
            _make_issue("W-1", StatusCategory.IN_PROGRESS, assignee_name="Alice"),
            _make_issue("W-2", StatusCategory.IN_PROGRESS, assignee_name="Alice"),
            _make_issue("W-3", StatusCategory.IN_PROGRESS, assignee_name="Bob"),
            _make_issue("W-4", StatusCategory.TODO),
            _make_issue("W-5", StatusCategory.DONE, resolved_days_ago=1),
        ]
        wip = compute_wip_snapshot(issues, wip_limit=1)
        assert wip.wip_count == 3
        assert wip.wip_by_person["Alice"] == 2
        assert wip.wip_by_person["Bob"] == 1
        assert "Alice" in wip.violations  # over limit of 1
        assert "Bob" not in wip.violations  # exactly at limit

    def test_no_violations_when_under_limit(self):
        issues = [_make_issue("W-1", StatusCategory.IN_PROGRESS)]
        wip = compute_wip_snapshot(issues, wip_limit=5)
        assert wip.violations == []


class TestCFD:
    def test_cfd_returns_data_points(self):
        issues = [
            _make_issue("C-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("C-2", StatusCategory.IN_PROGRESS, created_days_ago=10),
            _make_issue("C-3", StatusCategory.TODO, created_days_ago=3),
        ]
        cfd = compute_cfd(issues, days=15)
        assert len(cfd) == 16  # 15 days + today
        assert all(isinstance(pt, CFDDataPoint) for pt in cfd)
        # Last point should have at least 1 done
        last = cfd[-1]
        assert last.done >= 1


class TestFlowMetrics:
    def test_aggregate_metrics(self):
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
        assert fm.avg_cycle_time == 4.0
        assert fm.throughput_per_week == 5.0
        assert fm.current_wip == 3
        assert fm.wip_violations == 1
        assert 0 < fm.flow_efficiency <= 1.0


class TestKanbanInsightsOrchestrator:
    def test_compute_kanban_insights_complete(self):
        issues = [
            _make_issue("K-1", StatusCategory.DONE, created_days_ago=20, resolved_days_ago=5),
            _make_issue("K-2", StatusCategory.IN_PROGRESS, created_days_ago=10),
            _make_issue("K-3", StatusCategory.TODO, created_days_ago=3),
        ]
        insights = compute_kanban_insights(issues, wip_limit=3)
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

    def test_flow_metrics_cards_render(self):
        from flowboard.presentation.html.components_kanban import flow_metrics_cards

        t = Translator("en")
        html = flow_metrics_cards(self._get_insights(), t=t)
        assert "kanban-metrics-grid" in html
        assert "metric-card" in html
        assert "Avg Cycle Time" in html

    def test_flow_metrics_cards_none(self):
        from flowboard.presentation.html.components_kanban import flow_metrics_cards

        t = Translator("en")
        html = flow_metrics_cards(None, t=t)
        assert "empty-state" in html

    def test_wip_monitor_render(self):
        from flowboard.presentation.html.components_kanban import wip_monitor

        t = Translator("en")
        html = wip_monitor(self._get_insights(), t=t)
        assert "wip-monitor" in html or "empty-state" in html

    def test_cycle_time_table_render(self):
        from flowboard.presentation.html.components_kanban import cycle_time_table

        t = Translator("en")
        html = cycle_time_table(self._get_insights(), t=t)
        assert "cycle-time-table" in html
        assert "K-1" in html

    def test_throughput_chart_data_json(self):
        from flowboard.presentation.html.components_kanban import throughput_chart_data

        t = Translator("en")
        data = throughput_chart_data(self._get_insights(), t=t)
        assert data != "null"
        assert "Items Completed" in data

    def test_cfd_chart_data_json(self):
        from flowboard.presentation.html.components_kanban import cfd_chart_data

        t = Translator("en")
        data = cfd_chart_data(self._get_insights(), t=t)
        assert data != "null"
        assert "Done" in data

    def test_flow_tab_html_complete(self):
        from flowboard.presentation.html.components_kanban import flow_tab_html

        t = Translator("en")
        html = flow_tab_html(self._get_insights(), t=t)
        assert "flow-metrics" in html
        assert "wip-monitor" in html or "empty-state" in html
        assert "throughputChart" in html
        assert "cfdChart" in html
        assert "cycle-times" in html


# ===================================================================
# Phase 6: Adaptive Tab System
# ===================================================================


class TestBoardSnapshotKanban:
    def test_kanban_insights_field_exists(self):
        snap = BoardSnapshot(title="Test")
        assert snap.kanban_insights is None

    def test_kanban_insights_can_be_set(self):
        ki = KanbanInsights()
        snap = BoardSnapshot(title="Test", kanban_insights=ki)
        assert snap.kanban_insights is ki


# ===================================================================
# CSS: Kanban component styles
# ===================================================================


class TestKanbanCSS:
    def test_kanban_metrics_grid_css(self):
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
        assert ".kanban-metrics-grid" in css
        assert ".metric-card" in css
        assert ".wip-bar-fill" in css
        assert ".wip-monitor" in css


# ===================================================================
# Waterfall Domain Analytics
# ===================================================================


class TestWaterfallModels:
    def test_waterfall_insights_dataclass(self):
        from flowboard.domain.waterfall_models import WaterfallInsights

        wi = WaterfallInsights()
        assert wi.phases == []
        assert wi.milestones == []
        assert wi.critical_path == []
        assert wi.phase_progress.total_phases == 0

    def test_phase_dataclass(self):
        from flowboard.domain.waterfall_models import Phase

        p = Phase(key="v1.0", name="Release 1.0", progress_pct=75.0)
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

    def test_compute_waterfall_insights(self):
        from flowboard.domain.waterfall_compute import compute_waterfall_insights

        issues = self._make_waterfall_issues()
        insights = compute_waterfall_insights(issues)
        assert len(insights.phases) == 2  # v1.0 and v2.0
        assert insights.phase_progress.total_phases == 2

    def test_phases_have_progress(self):
        from flowboard.domain.waterfall_compute import compute_waterfall_insights

        issues = self._make_waterfall_issues()
        insights = compute_waterfall_insights(issues)
        v1 = next(p for p in insights.phases if p.key == "v1.0")
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

    def test_phase_progress_cards_render(self):
        from flowboard.presentation.html.components_waterfall import phase_progress_cards

        t = Translator("en")
        html = phase_progress_cards(self._get_insights(), t=t)
        assert "metric-card" in html
        assert "Overall Progress" in html

    def test_phase_progress_cards_none(self):
        from flowboard.presentation.html.components_waterfall import phase_progress_cards

        t = Translator("en")
        html = phase_progress_cards(None, t=t)
        assert "empty-state" in html

    def test_phase_table_render(self):
        from flowboard.presentation.html.components_waterfall import phase_table

        t = Translator("en")
        html = phase_table(self._get_insights(), t=t)
        assert "phase-table" in html
        assert "Phase 1" in html

    def test_milestone_timeline_render(self):
        from flowboard.presentation.html.components_waterfall import milestone_timeline

        t = Translator("en")
        html = milestone_timeline(self._get_insights(), t=t)
        # May have milestones if phases have end dates
        assert "milestone" in html or "empty-state" in html

    def test_phases_tab_html_complete(self):
        from flowboard.presentation.html.components_waterfall import phases_tab_html

        t = Translator("en")
        html = phases_tab_html(self._get_insights(), t=t)
        assert "phase-progress" in html
        assert "phase-details" in html
        assert "milestones" in html
        assert "critical-path" in html


# ===================================================================
# Waterfall Adaptive Tabs
# ===================================================================


class TestWaterfallTabs:
    def test_waterfall_renders_phases_no_sprints(self):
        html = _render("waterfall")
        assert "tab-phases" in html
        assert "tab-sprints" not in html
        assert "tab-flow" not in html

    def test_waterfall_has_phases_button(self):
        html = _render("waterfall")
        assert "tab-phases-btn" in html

    def test_waterfall_pl_renders(self):
        html = _render("waterfall", "pl")
        assert "Fazy" in html


# ===================================================================
# Waterfall i18n
# ===================================================================


class TestWaterfallI18n:
    def test_en_has_waterfall_keys(self):
        t = Translator("en")
        assert t.has("waterfall.phases")
        assert t.has("waterfall.milestones")
        assert t.has("waterfall.critical_path")
        assert t.has("tab.phases")

    def test_pl_has_waterfall_keys(self):
        t = Translator("pl")
        assert t.has("waterfall.phases")
        assert t.has("waterfall.milestones")
        assert t.has("tab.phases")

    def test_en_waterfall_labels(self):
        t = Translator("en")
        assert t("waterfall.phases") == "Phases"
        assert t("tab.phases") == "📋 Phases"

    def test_pl_waterfall_labels(self):
        t = Translator("pl")
        assert t("waterfall.phases") == "Fazy"
        assert t("tab.phases") == "📋 Fazy"


# ===================================================================
# Waterfall CSS
# ===================================================================


class TestWaterfallCSS:
    def test_milestone_css_exists(self):
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
        assert ".milestone-list" in css
        assert ".milestone-item" in css
        assert ".milestone-name" in css


# ===================================================================
# BoardSnapshot Waterfall
# ===================================================================


class TestBoardSnapshotWaterfall:
    def test_waterfall_insights_field_exists(self):
        snap = BoardSnapshot(title="Test")
        assert snap.waterfall_insights is None

    def test_waterfall_insights_can_be_set(self):
        from flowboard.domain.waterfall_models import WaterfallInsights

        wi = WaterfallInsights()
        snap = BoardSnapshot(title="Test", waterfall_insights=wi)
        assert snap.waterfall_insights is wi


# ===================================================================
# Phase 8: Hybrid, Custom, Auto-detect
# ===================================================================
