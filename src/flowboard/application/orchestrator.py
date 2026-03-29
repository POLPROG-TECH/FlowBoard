"""Application orchestrator — the main pipeline controller.

Connects the infrastructure (Jira fetch), domain (normalisation + analytics),
and presentation (HTML rendering) layers into a single coherent workflow.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

from flowboard.domain.analytics import build_board_snapshot
from flowboard.domain.models import BoardSnapshot
from flowboard.infrastructure.config.loader import FlowBoardConfig
from flowboard.infrastructure.jira.client import JiraClient
from flowboard.infrastructure.jira.connector import JiraConnector
from flowboard.infrastructure.jira.normalizer import JiraNormalizer
from flowboard.presentation.html.renderer import render_dashboard

logger = logging.getLogger(__name__)


def _timed(stage: str):
    """Log pipeline stage timing at INFO level."""

    class _Timer:
        def __enter__(self):
            self.start = time.monotonic()
            logger.info("Pipeline stage '%s' started.", stage)
            return self

        def __exit__(self, *exc):
            elapsed = time.monotonic() - self.start
            logger.info(
                "Pipeline stage '%s' completed in %.2fs.",
                stage,
                elapsed,
            )

    return _Timer()


class Orchestrator:
    """Top-level pipeline: fetch → normalise → analyse → render."""

    def __init__(self, config: FlowBoardConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run(self) -> Path:
        """Execute the full pipeline and return the path to the generated dashboard."""
        pipeline_start = time.monotonic()
        logger.info("Starting FlowBoard pipeline…")

        # 1. Fetch
        with _timed("fetch"):
            raw = self._fetch()

        # 2. Normalise + analyse
        with _timed("analyse"):
            snapshot = self._analyse(raw)

        # 3. Render
        with _timed("render"):
            output_path = self._render(snapshot)

        total = time.monotonic() - pipeline_start
        logger.info(
            "Dashboard generated: %s (total pipeline: %.2fs, issues: %d)",
            output_path,
            total,
            len(snapshot.issues),
        )
        return output_path

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _fetch(self) -> dict[str, Any]:
        with JiraClient(self._config.jira) as client:
            connector = JiraConnector(client, self._config)
            logger.info("Fetching data from Jira…")
            return connector.fetch_all()

    def _analyse(self, raw: dict[str, Any]) -> BoardSnapshot:
        return analyse_raw_payload(raw, self._config)

    def _render(self, snapshot: BoardSnapshot) -> Path:
        html = render_dashboard(snapshot, self._config)
        output_path = Path(self._config.output.path)
        # Blocker #16: pre-check output directory writability
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not os.access(output_path.parent, os.W_OK):
            raise PermissionError(f"Output directory is not writable: {output_path.parent}")
        output_path.write_text(html, encoding="utf-8")
        return output_path

    # ------------------------------------------------------------------
    # From pre-fetched data (useful for demos / tests)
    # ------------------------------------------------------------------

    def run_from_payload(self, raw: dict[str, Any]) -> Path:
        """Run analytics + render from an already-fetched payload."""
        snapshot = self._analyse(raw)
        return self._render(snapshot)

    def snapshot_from_payload(self, raw: dict[str, Any]) -> BoardSnapshot:
        """Return a BoardSnapshot without rendering."""
        return self._analyse(raw)


# ------------------------------------------------------------------
# Standalone analysis helper (no orchestrator instance needed)
# ------------------------------------------------------------------


def analyse_raw_payload(
    raw: dict[str, Any],
    config: FlowBoardConfig,
    *,
    today: date | None = None,
) -> BoardSnapshot:
    """Normalise a raw Jira payload and run all analytics."""
    normalizer = JiraNormalizer(config)

    issues = normalizer.normalize_issues(raw.get("issues", []))
    sprints = normalizer.normalize_sprints(raw.get("sprints", []))

    if not issues:
        logger.warning(
            "No issues returned from Jira. Check your project keys, JQL filter, "
            "and authentication. The dashboard will be generated with no data."
        )
    teams = normalizer.build_teams(issues)
    roadmap_items = normalizer.build_roadmap_items(issues)
    dependencies = normalizer.extract_dependencies(issues)
    people = normalizer.get_all_people()

    snapshot = build_board_snapshot(
        issues=issues,
        sprints=sprints,
        teams=teams,
        roadmap_items=roadmap_items,
        dependencies=dependencies,
        people=people,
        config=config,
        today=today,
    )
    return snapshot
