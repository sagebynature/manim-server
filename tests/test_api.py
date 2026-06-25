import logging
import shutil
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app, file_response
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


def test_append_section_uses_section_route_numeric_id_and_title(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))
    session_id = client.post("/sessions", json={"title": "Demo"}).json()["sessionId"]

    response = client.post(
        f"/sessions/{session_id}/section",
        json={"title": "Intro", "code": "self.wait(0.1)"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["section"]["sectionId"] == "0001"
    assert body["section"]["title"] == "Intro"
    assert "operation" not in body
    assert "operationId" not in body["section"]
    assert (
        client.post(
            f"/sessions/{session_id}/operations", json={"code": "self.wait(0.1)"}
        ).status_code
        == 404
    )


def test_create_session_accepts_manim_session_id_header(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post(
        "/sessions",
        json={"title": "Header session"},
        headers={"Manim-Session-ID": "browser-session-1"},
    )

    assert response.status_code == 200
    assert response.json()["sessionId"] == "browser-session-1"
    assert client.get("/sessions/browser-session-1").json()["title"] == "Header session"


def test_create_session_accepts_template_id(tmp_path: Path, monkeypatch):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "lecture.py").write_text("# lecture template\n", encoding="utf-8")
    monkeypatch.setenv("TEMPLATE_DIR", str(template_dir))
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post("/sessions", json={"title": "Demo", "templateId": "lecture"})

    assert response.status_code == 200
    assert response.json()["templateId"] == "lecture"


def test_create_session_unknown_template_falls_back_to_default(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post("/sessions", json={"title": "Demo", "templateId": "missing"})

    assert response.status_code == 200
    assert response.json()["templateId"] == "default"


def test_list_templates_returns_builtin_template_catalog(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.get("/templates")

    assert response.status_code == 200
    templates = response.json()["templates"]
    ids = {template["templateId"] for template in templates}
    assert {"default", "clean-title", "dark-grid", "presentation-card", "three-d"} <= ids
    dark_grid = next(template for template in templates if template["templateId"] == "dark-grid")
    assert dark_grid["description"] == "Dark grid template."
    assert "coordinate" in dark_grid["useCases"]


def test_openapi_documents_request_and_response_payloads(tmp_path: Path):
    app = create_app(data_dir=tmp_path)
    schema = app.openapi()

    def json_schema(method: str, path: str, status: str = "200") -> dict:
        return schema["paths"][path][method]["responses"][status]["content"][
            "application/json"
        ]["schema"]

    shared_routes = [
        ("list_templates", "get", "/templates"),
        ("create_session", "post", "/sessions"),
        ("list_sessions", "get", "/sessions"),
        ("get_session", "get", "/sessions/{session_id}"),
        ("close_session", "delete", "/sessions/{session_id}"),
        ("append_section", "post", "/sessions/{session_id}/section"),
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
    assert json_schema("get", "/templates") == {
        "$ref": "#/components/schemas/ListTemplatesResponse"
    }
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
    assert json_schema("post", "/sessions/{session_id}/section") == {
        "$ref": "#/components/schemas/AppendSectionResponse"
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
    assert schema["paths"]["/sessions/{session_id}/sections/{section_id}/video"]["get"][
        "responses"
    ]["200"]["content"]["video/mp4"]["schema"] == {
        "type": "string",
        "format": "binary",
    }


class FakeRenderer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def render(
        self,
        session_id,
        sections,
        cache,
        template_code="",
        session_title=None,
        template_id="default",
    ):
        render_dir = self.data_dir / "sessions" / session_id / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        (render_dir / "GeneratedScene.mp4").write_bytes(b"mp4")
        return RenderSummary(fullVideoUrl=f"/sessions/{session_id}/video", sections=[])


def test_file_response_rejects_existing_file_outside_allowed_root(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.mp4"
    outside.write_bytes(b"mp4")

    with pytest.raises(HTTPException) as exc:
        file_response(outside, tmp_path)

    assert exc.value.status_code == 404


def test_session_append_render_and_video(tmp_path: Path):
    app = create_app(data_dir=tmp_path, renderer=FakeRenderer(tmp_path))
    client = TestClient(app)

    session_id = client.post("/sessions", json={"title": "Demo"}).json()["sessionId"]
    response = client.post(
        f"/sessions/{session_id}/section",
        json={"code": "self.wait(1)", "render": True},
    )

    assert response.status_code == 200
    assert (
        response.json()["latestRender"]["fullVideoUrl"]
        == f"/sessions/{session_id}/video"
    )
    assert client.get(f"/sessions/{session_id}/video").content == b"mp4"
    assert (
        client.get(
            f"/sessions/{session_id}/sections/..%2FGeneratedScene/video"
        ).status_code
        == 404
    )
    assert client.get(f"/sessions/{session_id}").json()["sectionCount"] == 1


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
        f"/sessions/{session_id}/section",
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
