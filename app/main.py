import logging
from contextlib import asynccontextmanager
import os
from pathlib import Path
from time import perf_counter

from fastapi import Cookie, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from app.config import load_settings
from app.docs import DOCS
from app.models import (
    AppendSectionRequest,
    AppendSectionResponse,
    CreateSessionRequest,
    ListSessionsResponse,
    OkResponse,
    RenderRequest,
    RenderSummary,
    SessionDetail,
)
from app.renderer import ManimRenderer
from app.sessions import SessionService, SessionStore
from app.templates import TemplateStore


def create_app(data_dir: Path | None = None, renderer=None) -> FastAPI:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with app.state.mcp.session_manager.run():
            yield

    app = FastAPI(title="manim-server", lifespan=lifespan)
    route_logger = logging.getLogger("app.routes")

    @app.middleware("http")
    async def log_route_invocation(request, call_next):
        start = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - start) * 1000
            route_logger.exception(
                "route failed method=%s path=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (perf_counter() - start) * 1000
        route_logger.info(
            "route invoked method=%s path=%s status_code=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

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
        TemplateStore(settings.template_dir),
    )
    app.state.service = service
    app.state.data_dir = root

    @app.get("/health", response_model=OkResponse)
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/ready", response_model=OkResponse)
    def ready() -> dict[str, bool]:
        return {"ok": True}

    @app.post(
        "/sessions",
        response_model=SessionDetail,
        summary=DOCS["create_session"].summary,
        description=DOCS["create_session"].description,
    )
    def create_session(
        body: CreateSessionRequest,
        sessionId: str | None = Cookie(None),
        manim_session_id: str | None = Header(None, alias="Manim-Session-ID"),
    ):
        try:
            return service.create_session(
                body.title, manim_session_id or sessionId, body.templateId
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/sessions",
        response_model=ListSessionsResponse,
        summary=DOCS["list_sessions"].summary,
        description=DOCS["list_sessions"].description,
    )
    def list_sessions():
        return {"sessions": service.list_sessions()}

    @app.get(
        "/sessions/{session_id}",
        response_model=SessionDetail,
        summary=DOCS["get_session"].summary,
        description=DOCS["get_session"].description,
    )
    def get_session(session_id: str):
        try:
            return service.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete(
        "/sessions/{session_id}",
        response_model=OkResponse,
        summary=DOCS["close_session"].summary,
        description=DOCS["close_session"].description,
    )
    def close_session(session_id: str):
        try:
            return service.close_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/sessions/{session_id}/section",
        response_model=AppendSectionResponse,
        summary=DOCS["append_section"].summary,
        description=DOCS["append_section"].description,
    )
    def append_section(session_id: str, body: AppendSectionRequest):
        try:
            section = service.append_section(session_id, body.code, body.title)
            latest = (
                service.render_scene(session_id, body.cache) if body.render else None
            )
            return AppendSectionResponse(
                sessionId=session_id, section=section, latestRender=latest
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/sessions/{session_id}/render",
        response_model=RenderSummary,
        summary=DOCS["render_scene"].summary,
        description=DOCS["render_scene"].description,
    )
    def render_scene(session_id: str, body: RenderRequest):
        try:
            return service.render_scene(session_id, body.cache)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/sessions/{session_id}/reset",
        response_model=SessionDetail,
        summary=DOCS["reset_session"].summary,
        description=DOCS["reset_session"].description,
    )
    def reset_session(session_id: str):
        try:
            return service.reset_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/sessions/{session_id}/video",
        response_class=FileResponse,
        responses={
            200: {
                "content": {
                    "video/mp4": {"schema": {"type": "string", "format": "binary"}}
                }
            }
        },
    )
    def get_video(session_id: str):
        service.get_session(session_id)
        render_dir = root / "sessions" / session_id / "render"
        return file_response(render_dir / "GeneratedScene.mp4", render_dir)

    @app.get(
        "/sessions/{session_id}/sections/{section_id}/video",
        response_class=FileResponse,
        responses={
            200: {
                "content": {
                    "video/mp4": {"schema": {"type": "string", "format": "binary"}}
                }
            }
        },
    )
    def get_section_video(session_id: str, section_id: str):
        service.get_session(session_id)
        sections_dir = root / "sessions" / session_id / "render" / "sections"
        return file_response(sections_dir / f"{section_id}.mp4", sections_dir)

    from app.mcp import mount_mcp

    mount_mcp(app)
    return app


def file_response(path: Path, root: Path) -> FileResponse:
    resolved_root = os.path.realpath(root)
    resolved_path = os.path.realpath(path)
    if os.path.commonpath([resolved_root, resolved_path]) != resolved_root:
        raise HTTPException(status_code=404, detail="artifact not found")
    safe_path = Path(resolved_path)
    # Path was normalized and checked against resolved_root above.
    # codeql[py/path-injection]
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    # codeql[py/path-injection]
    return FileResponse(safe_path, media_type="video/mp4")


app = create_app()
