import logging
from functools import wraps
from inspect import signature
from time import perf_counter
from typing import Any

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from app.docs import DOCS
from app.models import RenderCacheMode
from app.sessions import SessionService


def dump(value) -> dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


logger = logging.getLogger("app.mcp")
MAX_LOG_STRING = 120
MAX_LOG_ITEMS = 5


def sanitize_log_value(value, *, key: str | None = None):
    if key == "code" and isinstance(value, str):
        return f"<redacted code len={len(value)}>"
    if isinstance(value, str):
        if len(value) <= MAX_LOG_STRING:
            return value
        return f"{value[:MAX_LOG_STRING]}...<truncated len={len(value)}>"
    if isinstance(value, int | float | bool) or value is None:
        return value
    if isinstance(value, dict):
        items = list(value.items())[:MAX_LOG_ITEMS]
        sanitized = {
            str(item_key): sanitize_log_value(item_value, key=str(item_key))
            for item_key, item_value in items
        }
        if len(value) > MAX_LOG_ITEMS:
            sanitized["..."] = f"<truncated items={len(value) - MAX_LOG_ITEMS}>"
        return sanitized
    if isinstance(value, list | tuple):
        items = value[:MAX_LOG_ITEMS]
        sanitized = [sanitize_log_value(item) for item in items]
        if len(value) > MAX_LOG_ITEMS:
            sanitized.append(f"<truncated items={len(value) - MAX_LOG_ITEMS}>")
        return sanitized
    return f"<{type(value).__name__}>"


def sanitize_tool_arguments(func, args, kwargs) -> dict[str, Any]:
    bound = signature(func).bind_partial(*args, **kwargs)
    return {
        name: sanitize_log_value(value, key=name)
        for name, value in bound.arguments.items()
    }


def log_tool_requests(name, func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        start = perf_counter()
        arguments = sanitize_tool_arguments(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000
            logger.error(
                "mcp tool failed tool=%s status=failed duration_ms=%.2f "
                "error_type=%s arguments=%s",
                name,
                duration_ms,
                type(exc).__name__,
                arguments,
            )
            raise
        duration_ms = (perf_counter() - start) * 1000
        logger.info(
            "mcp tool invoked tool=%s status=ok duration_ms=%.2f arguments=%s",
            name,
            duration_ms,
            arguments,
        )
        return result

    return wrapped


def create_tool_functions(service: SessionService):
    def create_session(title: str | None = None, template_id: str | None = None):
        return dump(service.create_session(title, template_id=template_id))

    def list_sessions():
        return {"sessions": [dump(item) for item in service.list_sessions()]}

    def get_session(session_id: str):
        return dump(service.get_session(session_id))

    def close_session(session_id: str):
        return service.close_session(session_id)

    def append_section(
        session_id: str,
        code: str,
        title: str | None = None,
        render: bool = False,
        cache: str = "use",
    ):
        section = service.append_section(session_id, code, title)
        latest = (
            service.render_scene(session_id, RenderCacheMode(cache)) if render else None
        )
        return {
            "sessionId": session_id,
            "section": dump(section),
            "latestRender": dump(latest) if latest else None,
        }

    def render_scene(session_id: str, cache: str = "use"):
        return dump(service.render_scene(session_id, RenderCacheMode(cache)))

    def reset_session(session_id: str):
        return dump(service.reset_session(session_id))

    tools = {
        "create_session": create_session,
        "list_sessions": list_sessions,
        "get_session": get_session,
        "close_session": close_session,
        "append_section": append_section,
        "render_scene": render_scene,
        "reset_session": reset_session,
    }
    return {name: log_tool_requests(name, tool) for name, tool in tools.items()}


def create_mcp_server(service: SessionService) -> FastMCP:
    mcp = FastMCP("manim-server", json_response=True, streamable_http_path="/")
    tools = create_tool_functions(service)

    @mcp.tool(description=DOCS["create_session"].description)
    def create_session(
        title: str | None = None, template_id: str | None = None
    ) -> dict[str, Any]:
        return tools["create_session"](title, template_id)

    @mcp.tool(description=DOCS["list_sessions"].description)
    def list_sessions() -> dict[str, Any]:
        return tools["list_sessions"]()

    @mcp.tool(description=DOCS["get_session"].description)
    def get_session(sessionId: str) -> dict[str, Any]:
        return tools["get_session"](sessionId)

    @mcp.tool(description=DOCS["close_session"].description)
    def close_session(sessionId: str) -> dict[str, bool]:
        return tools["close_session"](sessionId)

    @mcp.tool(description=DOCS["append_section"].description)
    def append_section(
        sessionId: str,
        code: str,
        title: str | None = None,
        render: bool = False,
        cache: str = "use",
    ) -> dict[str, Any]:
        return tools["append_section"](sessionId, code, title, render, cache)

    @mcp.tool(description=DOCS["render_scene"].description)
    def render_scene(sessionId: str, cache: str = "use") -> dict[str, Any]:
        return tools["render_scene"](sessionId, cache)

    @mcp.tool(description=DOCS["reset_session"].description)
    def reset_session(sessionId: str) -> dict[str, Any]:
        return tools["reset_session"](sessionId)

    return mcp


def mount_mcp(app: FastAPI) -> None:
    mcp = create_mcp_server(app.state.service)
    app.state.mcp = mcp
    app.mount("/mcp", mcp.streamable_http_app())
