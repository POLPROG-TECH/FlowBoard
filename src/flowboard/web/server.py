"""FlowBoard FastAPI web application.

Single ``create_app()`` factory that wires all routes, middleware, and state
into a self-contained ASGI application.

Pure helper functions (SSE formatting, demo config, loading page HTML) live in
``server_helpers`` to keep this module focused on the application factory.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from flowboard import __version__
from flowboard.web.logging import get_logger
from flowboard.web.middleware import (
    AuthMiddleware,
    BodySizeLimitMiddleware,
    CorrelationIdMiddleware,
    CSRFMiddleware,
    ErrorHandlerMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from flowboard.web.server_helpers import (
    build_demo_config_dict,
    build_loading_page,
    locate_demo_fixture,
    sse_format,
)
from flowboard.web.state import AnalysisPhase, AnalysisProgress, AppState

_log = get_logger("server")

# Pipeline timeout: max seconds for a full analysis run.
_ANALYSIS_TIMEOUT = int(os.environ.get("FLOWBOARD_ANALYSIS_TIMEOUT", "300"))

# Transparent 1x1 PNG favicon
_FAVICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQABNl7BcQAAAABJRU5ErkJggg=="
)
_FAVICON_BYTES = base64.b64decode(_FAVICON_B64)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app(
    config_path: Path | str | None = None,
    *,
    first_run: bool = False,
    root_path: str = "",
) -> FastAPI:
    """Create and return the FlowBoard FastAPI application."""

    startup_time = time.time()

    # -- State (pre-allocated so lifespan and routes share the same object) --

    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path) if not isinstance(config_path, Path) else config_path

    state = AppState(config_path=resolved_path)

    # We also cache the BoardSnapshot object for CSV export (not just JSON)
    _snapshot_cache: dict[str, Any] = {"obj": None}

    @contextlib.asynccontextmanager
    async def _lifespan(_app: FastAPI):
        yield
        # Shutdown logic
        _log.info("Shutting down — cancelling in-flight tasks")
        if state._analysis_task and not state._analysis_task.done():
            state._analysis_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state._analysis_task
        for q in list(state._sse_subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait({"event": "server_shutdown", "data": {}})
        state._sse_subscribers.clear()
        _log.info("Shutdown complete")

    app = FastAPI(
        title="FlowBoard",
        description="Jira-Based Delivery & Workload Intelligence Dashboard",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        root_path=root_path,
        lifespan=_lifespan,
    )

    # Expose state on app for wizard routes
    app.state._flowboard_state = state
    app.state._flowboard_first_run = first_run

    # -- CORS (Blocker #2) --
    cors_origins = os.getenv("FLOWBOARD_CORS_ORIGINS", "").strip()
    if cors_origins:
        from starlette.middleware.cors import CORSMiddleware

        origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "X-Requested-With", "Content-Type"],
            allow_credentials=True,
        )

    # -- Middleware (order: outermost → innermost) ----------------------------

    app.add_middleware(RequestLoggingMiddleware)  # type: ignore[arg-type]
    app.add_middleware(CorrelationIdMiddleware)  # type: ignore[arg-type]
    app.add_middleware(SecurityHeadersMiddleware)  # type: ignore[arg-type]
    app.add_middleware(BodySizeLimitMiddleware)  # type: ignore[arg-type]
    app.add_middleware(RateLimitMiddleware)  # type: ignore[arg-type]
    app.add_middleware(AuthMiddleware)  # type: ignore[arg-type]
    app.add_middleware(CSRFMiddleware)  # type: ignore[arg-type]
    app.add_middleware(ErrorHandlerMiddleware)  # type: ignore[arg-type]

    # -- Wizard routes -------------------------------------------------------

    from flowboard.web.routes_wizard import router as wizard_router

    app.include_router(wizard_router)

    from flowboard.web.routes_extended import router as extended_router

    app.include_router(extended_router)

    # -- Internal helpers ----------------------------------------------------

    def _load_config():
        from flowboard.infrastructure.config.loader import load_config

        if state.config_path is None:
            raise ValueError("No configuration file loaded.")
        return load_config(state.config_path)

    async def _run_analysis_pipeline() -> None:
        """Execute the full Jira fetch → analyse → render pipeline in a thread."""
        from flowboard.application.orchestrator import Orchestrator
        from flowboard.presentation.export.json_export import export_json
        from flowboard.presentation.html.renderer import render_dashboard

        state.analysis_progress = AnalysisProgress(
            phase=AnalysisPhase.FETCHING,
            detail="Loading configuration and connecting to Jira…",
            started_at=time.time(),
        )
        await state.broadcast("analysis_progress", state.analysis_progress.to_dict())

        try:
            # Blocker #10: wrap entire pipeline in a timeout
            await asyncio.wait_for(
                _do_pipeline(Orchestrator, export_json, render_dashboard),
                timeout=_ANALYSIS_TIMEOUT,
            )
        except TimeoutError:
            _log.error("Analysis pipeline timed out after %ds", _ANALYSIS_TIMEOUT)
            state.analysis_progress.phase = AnalysisPhase.FAILED
            state.analysis_progress.error = "Analysis timed out."
            state.analysis_progress.completed_at = time.time()
            await state.broadcast("analysis_failed", state.analysis_progress.to_dict())
        except asyncio.CancelledError:
            state.analysis_progress.phase = AnalysisPhase.FAILED
            state.analysis_progress.error = "Analysis cancelled."
            await state.broadcast("analysis_failed", state.analysis_progress.to_dict())
        except Exception:
            _log.exception("Analysis pipeline failed")
            state.analysis_progress.phase = AnalysisPhase.FAILED
            # Blocker #7: mask internal details from client
            state.analysis_progress.error = "Analysis failed. Check server logs for details."
            state.analysis_progress.completed_at = time.time()
            await state.broadcast("analysis_failed", state.analysis_progress.to_dict())

    async def _do_pipeline(orchestrator_cls, export_json, render_dashboard) -> None:
        """Inner pipeline logic separated for timeout wrapping."""
        cfg = await asyncio.to_thread(_load_config)
        orch = orchestrator_cls(cfg)

        # Fetch
        state.analysis_progress.detail = "Fetching data from Jira…"
        await state.broadcast("analysis_progress", state.analysis_progress.to_dict())
        raw = await asyncio.to_thread(orch._fetch)

        # Analyse
        state.analysis_progress.phase = AnalysisPhase.ANALYZING
        state.analysis_progress.detail = "Running analytics…"
        await state.broadcast("analysis_progress", state.analysis_progress.to_dict())
        snapshot = await asyncio.to_thread(orch._analyse, raw)

        # Render
        state.analysis_progress.phase = AnalysisPhase.RENDERING
        state.analysis_progress.detail = "Rendering dashboard…"
        await state.broadcast("analysis_progress", state.analysis_progress.to_dict())
        html = await asyncio.to_thread(render_dashboard, snapshot, cfg)

        # Store results
        state.last_dashboard_html = html
        state.last_snapshot_json = json.loads(export_json(snapshot))
        _snapshot_cache["obj"] = snapshot

        # Done
        state.analysis_progress.phase = AnalysisPhase.COMPLETED
        state.analysis_progress.detail = f"Done — {len(snapshot.issues)} issues analysed."
        state.analysis_progress.completed_at = time.time()
        await state.broadcast(
            "analysis_complete",
            {**state.analysis_progress.to_dict(), "issue_count": len(snapshot.issues)},
        )

    # -- Routes --------------------------------------------------------------

    # ---- Health ----

    @app.get("/health/live")
    async def health_live() -> dict:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def health_ready() -> JSONResponse:
        is_ready = (
            state.last_dashboard_html is not None or state.config_path is not None or first_run
        )
        if is_ready:
            return JSONResponse({"status": "ready"})
        return JSONResponse({"status": "not_ready"}, status_code=503)

    # ---- Metrics (Blocker #19) ----

    @app.get("/metrics")
    async def metrics() -> Response:
        from flowboard.web.middleware import _metrics

        lines = []
        for key, val in _metrics.items():
            lines.append(f"flowboard_{key} {val}")
        lines.append(f"flowboard_uptime_seconds {round(time.time() - startup_time, 1)}")
        return Response(
            content="\n".join(lines) + "\n",
            media_type="text/plain; version=0.0.4",
        )

    # ---- Status ----

    @app.get("/api/status")
    async def api_status() -> dict:
        # Blocker #19: data freshness indicator
        freshness = None
        if state.analysis_progress.completed_at > 0:
            age_s = round(time.time() - state.analysis_progress.completed_at, 1)
            freshness = {
                "completed_at": state.analysis_progress.completed_at,
                "age_seconds": age_s,
                "stale": age_s > 3600,
            }
        return {
            "version": __version__,
            "uptime_seconds": round(time.time() - startup_time, 1),
            "analysis": state.analysis_progress.to_dict(),
            "config_loaded": state.config_path is not None,
            "has_dashboard": state.last_dashboard_html is not None,
            "first_run": first_run,
            "data_freshness": freshness,
        }

    # ---- Dashboard (main page) ----

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> Response:
        # Reset flag: clear demo state and return to wizard
        if request.query_params.get("reset") == "1":
            state.last_dashboard_html = None
            state.last_snapshot_json = None
            _snapshot_cache.pop("obj", None)
            from flowboard.presentation.html.renderer import render_first_run

            lang = request.query_params.get("lang", "en")
            html = render_first_run(
                config_path=str(state.config_path or "config.json"), locale=lang
            )
            return HTMLResponse(html)

        if state.last_dashboard_html:
            import hashlib

            etag = hashlib.md5(state.last_dashboard_html.encode()).hexdigest()[:16]
            if_none = request.headers.get("if-none-match")
            if if_none and if_none.strip('"') == etag:
                return Response(status_code=304)
            return HTMLResponse(
                state.last_dashboard_html,
                headers={"ETag": f'"{etag}"', "Cache-Control": "private, max-age=60"},
            )

        if state.config_path is None or first_run:
            from flowboard.presentation.html.renderer import render_first_run

            lang = request.query_params.get("lang", "en")
            html = render_first_run(
                config_path=str(state.config_path or "config.json"), locale=lang
            )
            return HTMLResponse(html)

        return HTMLResponse(
            build_loading_page(),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    # ---- Analysis ----

    @app.post("/api/analyze")
    async def api_analyze() -> JSONResponse:
        if state.config_path is None:
            return JSONResponse(
                {"ok": False, "error": "No configuration file loaded."}, status_code=400
            )
        if state.analysis_lock.locked():
            return JSONResponse(
                {"ok": False, "error": "Analysis already in progress."}, status_code=409
            )
        async with state.analysis_lock:
            state._analysis_task = asyncio.create_task(_run_analysis_pipeline())
            try:
                await state._analysis_task
            finally:
                state._analysis_task = None
        return JSONResponse({"ok": True, "analysis": state.analysis_progress.to_dict()})

    @app.post("/api/analyze/cancel")
    async def api_analyze_cancel() -> JSONResponse:
        if state._analysis_task and not state._analysis_task.done():
            state._analysis_task.cancel()
            return JSONResponse({"ok": True, "detail": "Cancellation requested."})
        return JSONResponse({"ok": False, "error": "No analysis running."}, status_code=400)

    @app.get("/api/analyze/stream")
    async def api_analyze_stream() -> StreamingResponse:
        queue = await state.subscribe_async()

        async def event_generator():
            try:
                yield sse_format("current_state", state.analysis_progress.to_dict())
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield sse_format(msg["event"], msg["data"])
                        if msg["event"] in ("analysis_complete", "analysis_failed"):
                            break
                    except TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                await state.unsubscribe_async(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/analyze/results")
    async def api_analyze_results() -> JSONResponse:
        if state.last_snapshot_json is None:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "No analysis results available. Run /api/analyze or /api/demo first.",
                },
                status_code=404,
            )
        return JSONResponse({"ok": True, "results": state.last_snapshot_json})

    # ---- Export ----

    @app.get("/api/export/html")
    async def api_export_html() -> Response:
        if not state.last_dashboard_html:
            return JSONResponse(
                {"ok": False, "error": "No dashboard available. Run analysis first."},
                status_code=404,
            )
        return Response(
            content=state.last_dashboard_html,
            media_type="text/html",
            headers={"Content-Disposition": "attachment; filename=flowboard_dashboard.html"},
        )

    @app.get("/api/export/csv")
    async def api_export_csv(dataset: str = "issues") -> Response:
        # Blocker #8: validate dataset parameter
        allowed_datasets = {"issues", "workload", "risks"}
        if dataset not in allowed_datasets:
            return JSONResponse(
                {
                    "ok": False,
                    "error": f"Unknown dataset '{dataset}'. Use: issues, workload, risks.",
                },
                status_code=400,
            )
        snapshot = _snapshot_cache.get("obj")
        if snapshot is None:
            return JSONResponse(
                {"ok": False, "error": "No analysis data. Run analysis first."}, status_code=404
            )
        try:
            from flowboard.presentation.export.csv_export import (
                export_issues_csv,
                export_risks_csv,
                export_workload_csv,
            )

            exporters = {
                "issues": export_issues_csv,
                "workload": export_workload_csv,
                "risks": export_risks_csv,
            }
            exporter = exporters[dataset]
            try:
                csv_str = await asyncio.wait_for(
                    asyncio.to_thread(exporter, snapshot),
                    timeout=30.0,
                )
            except TimeoutError:
                _log.error("CSV export timed out for dataset=%s", dataset)
                return JSONResponse({"ok": False, "error": "Export timed out."}, status_code=504)
            return Response(
                content=csv_str,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename=flowboard_{dataset}.csv"},
            )
        except Exception:
            _log.exception("CSV export failed for dataset=%s", dataset)
            return JSONResponse(
                {"ok": False, "error": "Export failed. Check server logs."}, status_code=500
            )

    @app.get("/api/export/json")
    async def api_export_json() -> Response:
        if state.last_snapshot_json is None:
            return JSONResponse(
                {"ok": False, "error": "No analysis results available."}, status_code=404
            )
        return JSONResponse(
            state.last_snapshot_json,
            headers={"Content-Disposition": "attachment; filename=flowboard_snapshot.json"},
        )

    # ---- Demo ----

    @app.post("/api/demo")
    async def api_demo(request: Request) -> JSONResponse:
        try:
            from flowboard.application.orchestrator import Orchestrator
            from flowboard.infrastructure.config.loader import load_config_from_dict
            from flowboard.presentation.export.json_export import export_json
            from flowboard.presentation.html.renderer import render_dashboard

            # Parse optional methodology from request body
            methodology = "scrum"
            locale = "en"
            try:
                body = await request.json()
                methodology = body.get("methodology", "scrum")
                locale = body.get("locale", "en")
            except (ValueError, UnicodeDecodeError):
                pass

            from flowboard.infrastructure.config.config_models import SUPPORTED_METHODOLOGIES

            if methodology not in SUPPORTED_METHODOLOGIES:
                methodology = "scrum"

            fixture_path = locate_demo_fixture()
            with fixture_path.open() as f:
                mock_payload = json.load(f)

            cfg = load_config_from_dict(
                build_demo_config_dict(methodology=methodology, locale=locale)
            )
            orch = Orchestrator(cfg)

            snapshot = await asyncio.to_thread(orch.snapshot_from_payload, mock_payload)
            html = await asyncio.to_thread(render_dashboard, snapshot, cfg, is_demo=True)

            state.last_dashboard_html = html
            state.last_snapshot_json = json.loads(export_json(snapshot))
            _snapshot_cache["obj"] = snapshot

            state.analysis_progress = AnalysisProgress(
                phase=AnalysisPhase.COMPLETED,
                detail="Demo dashboard generated.",
                completed_at=time.time(),
            )
            return JSONResponse({"ok": True, "detail": "Demo dashboard generated."})
        except Exception:
            _log.exception("Demo generation failed")
            return JSONResponse(
                {"ok": False, "error": "Demo generation failed. Check server logs."},
                status_code=500,
            )

    # ---- Verify Jira ----

    @app.post("/api/verify")
    async def api_verify() -> JSONResponse:
        if state.config_path is None:
            return JSONResponse(
                {"ok": False, "error": "No configuration file loaded."}, status_code=400
            )
        try:
            from flowboard.application.services import verify_jira_connection

            cfg = await asyncio.to_thread(_load_config)
            info = await asyncio.to_thread(verify_jira_connection, cfg)
            return JSONResponse({"ok": True, **info})
        except Exception:
            _log.exception("Jira verification failed")
            return JSONResponse(
                {"ok": False, "error": "Verification failed. Check server logs."}, status_code=500
            )

    # ---- Config ----

    @app.get("/api/config")
    async def api_config() -> JSONResponse:
        if state.config_path is None:
            return JSONResponse(
                {"ok": False, "error": "No configuration file loaded.", "first_run": True},
                status_code=400,
            )
        try:
            from flowboard.application.services import describe_config

            cfg = await asyncio.to_thread(_load_config)
            info = describe_config(cfg)
            return JSONResponse({"ok": True, "config": info})
        except Exception:
            _log.exception("Config read failed")
            return JSONResponse(
                {"ok": False, "error": "Failed to read configuration."}, status_code=500
            )

    # ---- Hot config reload (Improvement #7) ----

    @app.post("/api/config/reload")
    async def api_config_reload() -> JSONResponse:
        """Reload configuration from disk without restarting server."""
        if state.config_path is None:
            return JSONResponse(
                {"ok": False, "error": "No configuration file to reload."}, status_code=400
            )
        try:
            await asyncio.to_thread(_load_config)
            state._cached_html = None  # Invalidate cached dashboard
            _snapshot_cache["obj"] = None
            _log.info("Configuration reloaded from %s", state.config_path)
            return JSONResponse({"ok": True, "message": "Configuration reloaded successfully."})
        except Exception as exc:
            _log.exception("Config reload failed")
            return JSONResponse({"ok": False, "error": f"Reload failed: {exc}"}, status_code=500)

    # ---- Favicon ----

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        return Response(content=_FAVICON_BYTES, media_type="image/png")

    return app
