from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.models import Operation, RenderCacheMode, RenderSummary, SessionDetail, SessionSummary


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.sessions_dir = data_dir / "sessions"
        # ponytail: one process-wide lock is enough for v1; use SQLite if multi-process writes matter.
        self._lock = Lock()

    def list_ids(self) -> list[str]:
        if not self.sessions_dir.exists():
            return []
        return sorted(path.name for path in self.sessions_dir.iterdir() if (path / "session.json").exists())

    def path(self, session_id: str) -> Path:
        if "/" in session_id or ".." in session_id:
            raise KeyError(f"unknown sessionId: {session_id}")
        return self.sessions_dir / session_id / "session.json"

    def load(self, session_id: str) -> SessionDetail:
        path = self.path(session_id)
        if not path.exists():
            raise KeyError(f"unknown sessionId: {session_id}")
        return SessionDetail.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, detail: SessionDetail) -> None:
        with self._lock:
            path = self.path(detail.sessionId)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(detail.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(path)

    def delete(self, session_id: str) -> None:
        self.load(session_id)
        self.path(session_id).unlink()


class SessionService:
    def __init__(self, store: SessionStore, renderer=None):
        self.store = store
        self.renderer = renderer

    def create_session(self, title: str | None) -> SessionDetail:
        detail = SessionDetail(sessionId=str(uuid4()), title=title, operationCount=0, operations=[])
        self.store.save(detail)
        return detail

    def list_sessions(self) -> list[SessionSummary]:
        return [SessionSummary(**self.store.load(session_id).model_dump(exclude={"operations"})) for session_id in self.store.list_ids()]

    def get_session(self, session_id: str) -> SessionDetail:
        return self.store.load(session_id)

    def close_session(self, session_id: str) -> dict[str, bool]:
        self.store.delete(session_id)
        return {"ok": True}

    def append_operation(self, session_id: str, code: str) -> Operation:
        if not code.strip():
            raise ValueError("operation code is empty")
        detail = self.store.load(session_id)
        number = len(detail.operations) + 1
        operation = Operation(
            operationId=f"op-{number:04d}",
            sectionName=f"op-{number:04d}",
            code=code,
            createdAt=now_iso(),
        )
        detail.operations.append(operation)
        detail.operationCount = len(detail.operations)
        detail.latestRender = None
        self.store.save(detail)
        return operation

    def reset_session(self, session_id: str) -> SessionDetail:
        detail = self.store.load(session_id)
        detail.operations = []
        detail.operationCount = 0
        detail.latestRender = None
        self.store.save(detail)
        return detail

    def render_scene(self, session_id: str, cache: RenderCacheMode) -> RenderSummary:
        if self.renderer is None:
            raise RuntimeError("renderer is not configured")
        detail = self.store.load(session_id)
        summary = self.renderer.render(detail.sessionId, detail.operations, cache)
        detail.latestRender = summary
        self.store.save(detail)
        return summary
