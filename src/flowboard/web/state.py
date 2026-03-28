"""Runtime state management for the FlowBoard web application."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

_MAX_SSE_SUBSCRIBERS = 50


class AnalysisPhase(StrEnum):
    IDLE = "idle"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AnalysisProgress:
    phase: AnalysisPhase = AnalysisPhase.IDLE
    detail: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"phase": self.phase.value, "detail": self.detail, "error": self.error}


@dataclass
class AppState:
    config_path: Path | None = None
    analysis_progress: AnalysisProgress = field(default_factory=AnalysisProgress)
    analysis_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_dashboard_html: str | None = None
    last_snapshot_json: dict | None = None
    _sse_subscribers: list[asyncio.Queue[dict]] = field(default_factory=list)
    _sse_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _analysis_task: asyncio.Task | None = field(default=None, repr=False)  # type: ignore[type-arg]
    # Thread-safe snapshot cache for CSV export (Blocker #22)
    _snapshot_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _snapshot_obj: object | None = field(default=None, repr=False)

    def subscribe(self) -> asyncio.Queue[dict]:
        """Synchronous subscribe — kept for backward compatibility."""
        if len(self._sse_subscribers) >= _MAX_SSE_SUBSCRIBERS:
            old = self._sse_subscribers.pop(0)
            with contextlib.suppress(asyncio.QueueFull):
                old.put_nowait({"event": "evicted", "data": {"error": "Too many subscribers"}})
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
        self._sse_subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict]) -> None:
        """Synchronous unsubscribe — kept for backward compatibility."""
        if q in self._sse_subscribers:
            self._sse_subscribers.remove(q)

    async def subscribe_async(self) -> asyncio.Queue[dict]:
        """Thread-safe subscribe using asyncio.Lock (Blocker #5)."""
        async with self._sse_lock:
            if len(self._sse_subscribers) >= _MAX_SSE_SUBSCRIBERS:
                old = self._sse_subscribers.pop(0)
                with contextlib.suppress(asyncio.QueueFull):
                    old.put_nowait({"event": "evicted", "data": {"error": "Too many subscribers"}})
            q: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
            self._sse_subscribers.append(q)
            return q

    async def unsubscribe_async(self, q: asyncio.Queue[dict]) -> None:
        """Thread-safe unsubscribe using asyncio.Lock (Blocker #5)."""
        async with self._sse_lock:
            if q in self._sse_subscribers:
                self._sse_subscribers.remove(q)

    async def broadcast(self, event_type: str, data: dict) -> None:
        async with self._sse_lock:
            stale: list[asyncio.Queue[dict]] = []
            for q in list(self._sse_subscribers):
                try:
                    q.put_nowait({"event": event_type, "data": data})
                except asyncio.QueueFull:
                    stale.append(q)
            for q in stale:
                self._sse_subscribers.remove(q)

    async def set_snapshot(self, obj: object) -> None:
        """Thread-safe snapshot update (Blocker #22)."""
        async with self._snapshot_lock:
            self._snapshot_obj = obj

    async def get_snapshot(self) -> object | None:
        """Thread-safe snapshot read (Blocker #22)."""
        async with self._snapshot_lock:
            return self._snapshot_obj
