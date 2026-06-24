from fastapi.routing import Mount

from app.main import create_app
from app.mcp import create_mcp_server, create_tool_functions
from app.models import RenderSummary
from app.sessions import SessionService, SessionStore


class FakeRenderer:
    def render(self, session_id, operations, cache):
        return RenderSummary(fullVideoUrl=f"/sessions/{session_id}/video", sections=[])


def test_mcp_tools_call_shared_service(tmp_path):
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), FakeRenderer())
    )

    session = tools["create_session"]("Demo")
    appended = tools["append_operation"](session["sessionId"], "self.wait(1)", True)

    assert (
        appended["latestRender"]["fullVideoUrl"]
        == f"/sessions/{session['sessionId']}/video"
    )
    assert tools["get_session"](session["sessionId"])["operationCount"] == 1


def test_app_mounts_mcp_route(tmp_path):
    app = create_app(data_dir=tmp_path, renderer=FakeRenderer())

    assert app.state.mcp is not None
    assert any(
        isinstance(route, Mount) and route.path == "/mcp" for route in app.routes
    )


def test_mcp_tool_descriptions_guide_clients(tmp_path):
    mcp = create_mcp_server(SessionService(SessionStore(tmp_path), FakeRenderer()))
    tools = mcp._tool_manager._tools

    assert "Start here" in tools["create_session"].description
    assert "Use this before append_operation" in tools["create_session"].description

    append_description = tools["append_operation"].description
    assert "trusted Python Manim scene-body code" in append_description
    assert "append one logical animation step" in append_description
    assert "render=False" in append_description
    assert "render=True" in append_description
    assert "cache" in append_description
    assert "use" in append_description
    assert "refresh" in append_description
    assert "disable" in append_description
