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
        """Create a Manim session."""
        return tools["create_session"](title)

    @mcp.tool()
    def list_sessions() -> dict[str, Any]:
        """List Manim sessions."""
        return tools["list_sessions"]()

    @mcp.tool()
    def get_session(sessionId: str) -> dict[str, Any]:
        """Get a Manim session."""
        return tools["get_session"](sessionId)

    @mcp.tool()
    def close_session(sessionId: str) -> dict[str, bool]:
        """Close a Manim session."""
        return tools["close_session"](sessionId)

    @mcp.tool()
    def append_operation(sessionId: str, code: str, render: bool = False, cache: str = "use") -> dict[str, Any]:
        """Append trusted Python Manim code to a session."""
        return tools["append_operation"](sessionId, code, render, cache)

    @mcp.tool()
    def render_scene(sessionId: str, cache: str = "use") -> dict[str, Any]:
        """Render a Manim session synchronously."""
        return tools["render_scene"](sessionId, cache)

    @mcp.tool()
    def reset_session(sessionId: str) -> dict[str, Any]:
        """Reset a Manim session operation log."""
        return tools["reset_session"](sessionId)

    return mcp


def mount_mcp(app: FastAPI) -> None:
    mcp = create_mcp_server(app.state.service)
    app.state.mcp = mcp
    app.mount("/mcp", mcp.streamable_http_app())
