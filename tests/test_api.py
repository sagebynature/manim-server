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
    response = client.post(f"/sessions/{session_id}/operations", json={"code": "self.wait(1)", "render": True})

    assert response.status_code == 200
    assert response.json()["latestRender"]["fullVideoUrl"] == f"/sessions/{session_id}/video"
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
        json={"code": "self.add(Circle())\nself.wait(0.1)", "render": True, "cache": "disable"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["latestRender"]["fullVideoUrl"] == f"/sessions/{session_id}/video"
    assert client.get(body["latestRender"]["fullVideoUrl"]).status_code == 200
