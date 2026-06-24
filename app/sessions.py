from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.models import (
    Section,
    RenderCacheMode,
    RenderSummary,
    SessionDetail,
    SessionSummary,
)
from app.templates import TemplateStore


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
        return sorted(
            path.name
            for path in self.sessions_dir.iterdir()
            if (path / "session.json").exists()
        )

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
    def __init__(
        self, store: SessionStore, renderer=None, templates: TemplateStore | None = None
    ):
        self.store = store
        self.renderer = renderer
        self.templates = templates or TemplateStore(store.data_dir)

    def create_session(
        self,
        title: str | None,
        session_id: str | None = None,
        template_id: str | None = None,
    ) -> SessionDetail:
        session_id = session_id or str(uuid4())
        if "/" in session_id or ".." in session_id:
            raise ValueError(f"invalid sessionId: {session_id}")
        if self.store.path(session_id).exists():
            raise ValueError(f"sessionId already exists: {session_id}")
        template = self.templates.resolve(template_id)
        detail = SessionDetail(
            sessionId=session_id,
            title=title,
            templateId=template.templateId,
            sectionCount=0,
            sections=[],
        )
        self.store.save(detail)
        return detail

    def list_sessions(self) -> list[SessionSummary]:
        return [
            SessionSummary(
                **self.store.load(session_id).model_dump(exclude={"sections"})
            )
            for session_id in self.store.list_ids()
        ]

    def get_session(self, session_id: str) -> SessionDetail:
        return self.store.load(session_id)

    def close_session(self, session_id: str) -> dict[str, bool]:
        self.store.delete(session_id)
        return {"ok": True}

    def append_section(
        self, session_id: str, code: str, title: str | None = None
    ) -> Section:
        if not code.strip():
            raise ValueError("section code is empty")
        detail = self.store.load(session_id)
        number = len(detail.sections) + 1
        section = Section(
            sectionId=f"{number:04d}",
            title=title,
            code=code,
            createdAt=now_iso(),
        )
        detail.sections.append(section)
        detail.sectionCount = len(detail.sections)
        detail.latestRender = None
        self.store.save(detail)
        return section

    def reset_session(self, session_id: str) -> SessionDetail:
        detail = self.store.load(session_id)
        detail.sections = []
        detail.sectionCount = 0
        detail.latestRender = None
        self.store.save(detail)
        return detail

    def render_scene(self, session_id: str, cache: RenderCacheMode) -> RenderSummary:
        if self.renderer is None:
            raise RuntimeError("renderer is not configured")
        detail = self.store.load(session_id)
        summary = self.renderer.render(detail.sessionId, detail.sections, cache)
        detail.latestRender = summary
        self.store.save(detail)
        return summary
