import logging
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import RenderSummary


def test_health_ready(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))

    assert client.get("/health").json() == {"ok": True}
    assert client.get("/ready").json() == {"ok": True}




def test_route_invocation_is_logged(tmp_path: Path, caplog):
    client = TestClient(create_app(data_dir=tmp_path))

    with caplog.at_level(logging.INFO, logger="app.routes"):
        response = client.get("/health")

    assert response.status_code == 200
    assert "route invoked method=GET path=/health status_code=200" in caplog.text


def test_openapi_documents_request_and_response_payloads(tmp_path: Path):
    app = create_app(data_dir=tmp_path)
    schema = app.openapi()

    def json_schema(method: str, path: str, status: str = "200") -> dict:
        return schema["paths"][path][method]["responses"][status]["content"][
            "application/json"
        ]["schema"]

    shared_routes = [
        ("create_session", "post", "/sessions"),
        ("list_sessions", "get", "/sessions"),
        ("get_session", "get", "/sessions/{session_id}"),
        ("close_session", "delete", "/sessions/{session_id}"),
        ("append_operation", "post", "/sessions/{session_id}/operations"),
        ("render_scene", "post", "/sessions/{session_id}/render"),
        ("reset_session", "post", "/sessions/{session_id}/reset"),
    ]
    mcp_tools = app.state.mcp._tool_manager._tools
    for tool_name, method, path in shared_routes:
        assert (
            schema["paths"][path][method]["description"]
            == mcp_tools[tool_name].description
        )

    assert json_schema("get", "/health") == {"$ref": "#/components/schemas/OkResponse"}
    assert json_schema("get", "/ready") == {"$ref": "#/components/schemas/OkResponse"}
    assert json_schema("post", "/sessions") == {
        "$ref": "#/components/schemas/SessionDetail"
    }
    assert json_schema("get", "/sessions") == {
        "$ref": "#/components/schemas/ListSessionsResponse"
    }
    assert json_schema("get", "/sessions/{session_id}") == {
        "$ref": "#/components/schemas/SessionDetail"
    }
    assert json_schema("delete", "/sessions/{session_id}") == {
        "$ref": "#/components/schemas/OkResponse"
    }
    assert json_schema("post", "/sessions/{session_id}/operations") == {
        "$ref": "#/components/schemas/AppendOperationResponse"
    }
    assert json_schema("post", "/sessions/{session_id}/render") == {
        "$ref": "#/components/schemas/RenderSummary"
    }
    assert json_schema("post", "/sessions/{session_id}/reset") == {
        "$ref": "#/components/schemas/SessionDetail"
    }
    assert schema["paths"]["/sessions/{session_id}/video"]["get"]["responses"]["200"][
        "content"
    ]["video/mp4"]["schema"] == {"type": "string", "format": "binary"}
    assert schema["paths"]["/sessions/{session_id}/sections/{operation_id}/video"][
        "get"
    ]["responses"]["200"]["content"]["video/mp4"]["schema"] == {
        "type": "string",
        "format": "binary",
    }


class FakeRenderer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def render(self, session_id, operations, cache):
        render_dir = self.data_dir / "sessions" / session_id / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        (render_dir / "GeneratedScene.mp4").write_bytes(b"mp4")
        return RenderSummary(fullVideoUrl=f"/sessions/{session_id}/video", sections=[])


def test_session_append_render_and_video(tmp_path: Path):
    app = create_app(data_dir=tmp_path, renderer=FakeRenderer(tmp_path))
    client = TestClient(app)

    session_id = client.post("/sessions", json={"title": "Demo"}).json()["sessionId"]
    response = client.post(
        f"/sessions/{session_id}/operations",
        json={"code": "self.wait(1)", "render": True},
    )

    assert response.status_code == 200
    assert (
        response.json()["latestRender"]["fullVideoUrl"]
        == f"/sessions/{session_id}/video"
    )
    assert client.get(f"/sessions/{session_id}/video").content == b"mp4"
    assert client.get(f"/sessions/{session_id}").json()["operationCount"] == 1


def test_missing_session_returns_404(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))

    assert client.get("/sessions/missing").status_code == 404


def test_relative_data_dir_is_resolved(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    app = create_app(data_dir=Path("relative-data"))
    expected = (tmp_path / "relative-data").resolve()

    assert app.state.data_dir == expected
    assert app.state.service.store.data_dir == expected
    assert app.state.service.renderer.data_dir == expected


@pytest.mark.skipif(shutil.which("manim") is None, reason="manim CLI not installed")
def test_api_real_manim_render_smoke(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))
    session_id = client.post("/sessions", json={"title": "Smoke"}).json()["sessionId"]

    response = client.post(
        f"/sessions/{session_id}/operations",
        json={
            "code": "self.add(Circle())\nself.wait(0.1)",
            "render": True,
            "cache": "disable",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["latestRender"]["fullVideoUrl"] == f"/sessions/{session_id}/video"
    assert client.get(body["latestRender"]["fullVideoUrl"]).status_code == 200
