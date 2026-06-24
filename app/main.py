import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.config import load_settings
from app.models import (
    AppendOperationRequest,
    AppendOperationResponse,
    CreateSessionRequest,
    ListSessionsResponse,
    OkResponse,
    RenderRequest,
    RenderSummary,
    SessionDetail,
)
from app.renderer import ManimRenderer
from app.sessions import SessionService, SessionStore


def create_app(data_dir: Path | None = None, renderer=None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="manim-server")
    settings = load_settings()
    root = (data_dir or settings.data_dir).resolve()
    service = SessionService(
        SessionStore(root),
        renderer
        or ManimRenderer(
            root,
            cli_flags=settings.manim_cli_flags,
            timeout_seconds=settings.manim_timeout_seconds,
        ),
    )
    app.state.service = service
    app.state.data_dir = root

    @app.get("/health", response_model=OkResponse)
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/ready", response_model=OkResponse)
    def ready() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/sessions", response_model=SessionDetail)
    def create_session(body: CreateSessionRequest):
        return service.create_session(body.title)

    @app.get("/sessions", response_model=ListSessionsResponse)
    def list_sessions():
        return {"sessions": service.list_sessions()}

    @app.get("/sessions/{session_id}", response_model=SessionDetail)
    def get_session(session_id: str):
        try:
            return service.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/sessions/{session_id}", response_model=OkResponse)
    def close_session(session_id: str):
        try:
            return service.close_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/operations", response_model=AppendOperationResponse)
    def append_operation(session_id: str, body: AppendOperationRequest):
        try:
            operation = service.append_operation(session_id, body.code)
            latest = service.render_scene(session_id, body.cache) if body.render else None
            return AppendOperationResponse(sessionId=session_id, operation=operation, latestRender=latest)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/render", response_model=RenderSummary)
    def render_scene(session_id: str, body: RenderRequest):
        try:
            return service.render_scene(session_id, body.cache)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/reset", response_model=SessionDetail)
    def reset_session(session_id: str):
        try:
            return service.reset_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/sessions/{session_id}/video",
        response_class=FileResponse,
        responses={200: {"content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}}}},
    )
    def get_video(session_id: str):
        service.get_session(session_id)
        return file_response(root / "sessions" / session_id / "render" / "GeneratedScene.mp4")

    @app.get(
        "/sessions/{session_id}/sections/{operation_id}/video",
        response_class=FileResponse,
        responses={200: {"content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}}}},
    )
    def get_section_video(session_id: str, operation_id: str):
        service.get_session(session_id)
        return file_response(root / "sessions" / session_id / "render" / "sections" / f"{operation_id}.mp4")

    from app.mcp import mount_mcp

    mount_mcp(app)
    return app


def file_response(path: Path) -> FileResponse:
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path, media_type="video/mp4")


app = create_app()
