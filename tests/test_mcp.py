import logging
import pytest

from fastapi.routing import Mount
from starlette.testclient import TestClient

from app.main import create_app
from app.mcp import create_mcp_server, create_tool_functions
from app.models import RenderSummary
from app.sessions import SessionService, SessionStore
from app.templates import TemplateStore


class FakeRenderer:
    def render(
        self,
        session_id,
        sections,
        cache,
        template_code="",
        session_title=None,
        template_id="default",
    ):
        return RenderSummary(fullVideoUrl=f"/sessions/{session_id}/video", sections=[])


def test_mcp_tools_call_shared_service(tmp_path):
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), FakeRenderer())
    )

    session = tools["create_session"]("Demo")
    appended = tools["append_section"](
        session["sessionId"], "self.wait(1)", render=True
    )

    assert (
        appended["latestRender"]["fullVideoUrl"]
        == f"/sessions/{session['sessionId']}/video"
    )
    assert tools["get_session"](session["sessionId"])["sectionCount"] == 1


def test_mcp_create_session_accepts_template_id(tmp_path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "lecture.py").write_text("# lecture template\n", encoding="utf-8")
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), templates=TemplateStore(template_dir))
    )

    session = tools["create_session"]("Demo", template_id="lecture")

    assert session["templateId"] == "lecture"


def test_mcp_tool_success_logs_sanitized_arguments(tmp_path, caplog):
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), FakeRenderer())
    )
    session = tools["create_session"]("Demo")
    caplog.clear()

    code = "self.play(Create(Circle()))"
    with caplog.at_level(logging.INFO, logger="app.mcp"):
        result = tools["append_section"](session["sessionId"], code, render=True)

    assert result["sessionId"] == session["sessionId"]
    messages = [record.getMessage() for record in caplog.records]
    message = next(
        message for message in messages if "mcp tool invoked" in message
    )

    assert "tool=append_section" in message
    assert "status=ok" in message
    assert "duration_ms=" in message
    assert f"<redacted code len={len(code)}>" in message
    assert code not in message

def test_mcp_tool_failure_logs_error_details(tmp_path, caplog):
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), FakeRenderer())
    )

    with caplog.at_level(logging.INFO, logger="app.mcp"):
        with pytest.raises(ValueError):
            tools["render_scene"]("missing-session", cache="invalid")

    failure_records = [
        record for record in caplog.records if "mcp tool failed" in record.getMessage()
    ]
    assert len(failure_records) == 1
    failure_record = failure_records[0]
    message = failure_record.getMessage()
    assert failure_record.exc_info is None
    assert "tool=render_scene" in message
    assert "status=failed" in message
    assert "duration_ms=" in message
    assert "error_type=ValueError" in message


def test_app_mounts_mcp_route(tmp_path):
    app = create_app(data_dir=tmp_path, renderer=FakeRenderer())

    assert app.state.mcp is not None
    assert any(
        isinstance(route, Mount) and route.path == "/mcp" for route in app.routes
    )


def test_mcp_http_endpoint_initializes_without_lifespan_error(tmp_path):
    app = create_app(data_dir=tmp_path, renderer=FakeRenderer())

    with TestClient(
        app, base_url="http://127.0.0.1:3000", raise_server_exceptions=False
    ) as client:
        response = client.post(
            "/mcp/",
            headers={
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"},
                },
            },
        )

    assert response.status_code == 200


def test_mcp_tool_descriptions_guide_clients(tmp_path):
    mcp = create_mcp_server(SessionService(SessionStore(tmp_path), FakeRenderer()))
    tools = mcp._tool_manager._tools

    assert "Start here" in tools["create_session"].description
    assert "Use this before append_section" in tools["create_session"].description

    append_description = tools["append_section"].description
    assert "trusted Python Manim scene-body code" in append_description
    assert "append one logical animation step" in append_description
    assert "render=False" in append_description
    assert "render=True" in append_description
    assert "cache" in append_description
    assert "defaults to use" in append_description
    assert "flush" in append_description
    assert "disable" in append_description
