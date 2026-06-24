from typing import Any

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from app.models import RenderCacheMode
from app.sessions import SessionService


def dump(value) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def create_tool_functions(service: SessionService):
    def create_session(title: str | None = None):
        return dump(service.create_session(title))

    def list_sessions():
        return {"sessions": [dump(item) for item in service.list_sessions()]}

    def get_session(session_id: str):
        return dump(service.get_session(session_id))

    def close_session(session_id: str):
        return service.close_session(session_id)

    def append_operation(session_id: str, code: str, render: bool = False, cache: str = "use"):
        operation = service.append_operation(session_id, code)
        latest = service.render_scene(session_id, RenderCacheMode(cache)) if render else None
        return {"sessionId": session_id, "operation": dump(operation), "latestRender": dump(latest) if latest else None}

    def render_scene(session_id: str, cache: str = "use"):
        return dump(service.render_scene(session_id, RenderCacheMode(cache)))

    def reset_session(session_id: str):
        return dump(service.reset_session(session_id))

    return {
        "create_session": create_session,
        "list_sessions": list_sessions,
        "get_session": get_session,
        "close_session": close_session,
        "append_operation": append_operation,
        "render_scene": render_scene,
        "reset_session": reset_session,
    }


def create_mcp_server(service: SessionService) -> FastMCP:
    mcp = FastMCP("manim-server", json_response=True, streamable_http_path="/")
    tools = create_tool_functions(service)

    @mcp.tool()
    def create_session(title: str | None = None) -> dict[str, Any]:
        """Start here to create a new Manim scene session.

        Use this before append_operation or render_scene when building a new
        animation. Optional title labels the session for later list/get calls.
        Returns sessionId, title, operation count, and render metadata.
        """
        return tools["create_session"](title)

    @mcp.tool()
    def list_sessions() -> dict[str, Any]:
        """List existing Manim scene sessions.

        Use to find prior sessionId values before get_session, append_operation,
        render_scene, reset_session, or close_session. Returns summary metadata
        only; call get_session for the full operation log.
        """
        return tools["list_sessions"]()

    @mcp.tool()
    def get_session(sessionId: str) -> dict[str, Any]:
        """Get one Manim session by sessionId.

        Use after create_session or list_sessions to inspect the current
        operation log, render status, and generated media URLs before deciding
        whether to append, render, reset, or close the session.
        """
        return tools["get_session"](sessionId)

    @mcp.tool()
    def close_session(sessionId: str) -> dict[str, bool]:
        """Close one Manim session by sessionId.

        Use when the client is finished with a session and wants the server to
        remove it from active session storage. Returns whether a session was
        closed; closed sessions cannot be appended to or rendered.
        """
        return tools["close_session"](sessionId)

    @mcp.tool()
    def append_operation(sessionId: str, code: str, render: bool = False, cache: str = "use") -> dict[str, Any]:
        """Use this tool to append one logical animation step to an existing Manim session.

        The code parameter is trusted Python Manim scene-body code, written as
        statements that run inside the current Scene construct method. Operations
        are appended in order, so use this for incremental scene construction
        after create_session. Prefer render=False while batching multiple small
        edits; use render=True when the client needs an immediate video update
        after this append. cache controls rendering when render=True: use reuses
        existing Manim cache, refresh rerenders with cache refresh, and disable
        renders without cache. Returns the appended operation and latestRender
        only when render=True.
        """
        return tools["append_operation"](sessionId, code, render, cache)

    @mcp.tool()
    def render_scene(sessionId: str, cache: str = "use") -> dict[str, Any]:
        """Render an existing Manim session synchronously.

        Use after one or more append_operation calls when render=False was used
        or when the client needs a fresh video URL. cache may be use, refresh, or
        disable. Returns the full video URL and section metadata.
        """
        return tools["render_scene"](sessionId, cache)

    @mcp.tool()
    def reset_session(sessionId: str) -> dict[str, Any]:
        """Reset an existing Manim session operation log.

        Use to keep the same sessionId but remove all appended Manim operations
        before rebuilding a scene. This does not create a new session; call
        append_operation next to add replacement scene-body code.
        """
        return tools["reset_session"](sessionId)

    return mcp


def mount_mcp(app: FastAPI) -> None:
    mcp = create_mcp_server(app.state.service)
    app.state.mcp = mcp
    app.mount("/mcp", mcp.streamable_http_app())
