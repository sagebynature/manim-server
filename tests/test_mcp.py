from fastapi.routing import Mount

from app.main import create_app
from app.mcp import create_tool_functions
from app.models import RenderSummary
from app.sessions import SessionService, SessionStore


class FakeRenderer:
    def render(self, session_id, operations, cache):
        return RenderSummary(fullVideoUrl=f"/sessions/{session_id}/video", sections=[])


def test_mcp_tools_call_shared_service(tmp_path):
    tools = create_tool_functions(SessionService(SessionStore(tmp_path), FakeRenderer()))

    session = tools["create_session"]("Demo")
    appended = tools["append_operation"](session["sessionId"], "self.wait(1)", True)

    assert appended["latestRender"]["fullVideoUrl"] == f"/sessions/{session['sessionId']}/video"
    assert tools["get_session"](session["sessionId"])["operationCount"] == 1


def test_app_mounts_mcp_route(tmp_path):
    app = create_app(data_dir=tmp_path, renderer=FakeRenderer())

    assert app.state.mcp is not None
    assert any(isinstance(route, Mount) and route.path == "/mcp" for route in app.routes)
