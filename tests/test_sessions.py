import json

from app.models import RenderCacheMode, RenderSummary, SectionArtifact, SessionDetail
from app.sessions import SessionService, SessionStore


def test_create_session_defaults_to_default_template(tmp_path):
    service = SessionService(SessionStore(tmp_path))

    session = service.create_session("Demo")

    assert session.templateId == "default"
    assert service.get_session(session.sessionId).templateId == "default"


def test_create_session_falls_back_to_default_when_template_missing(tmp_path):
    service = SessionService(SessionStore(tmp_path))

    session = service.create_session("Demo", template_id="missing-template")

    assert session.templateId == "default"


def test_create_session_uses_file_backed_template_id(tmp_path):
    template_dir = tmp_path / "assets" / "session-templates"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text(
        'from manim import *\n\n'
        'class GeneratedScene(Scene):\n'
        '    def construct(self):\n'
        '        session_id = "__SESSION_ID__"\n'
        '        session_title = "__SESSION_TITLE__"\n'
        '        template_id = "__TEMPLATE_ID__"\n',
        encoding="utf-8",
    )

    service = SessionService(SessionStore(tmp_path))

    session = service.create_session("Demo", template_id="lecture")

    assert session.templateId == "lecture"


def test_reset_preserves_template_id(tmp_path):
    template_dir = tmp_path / "assets" / "session-templates"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text("# valid enough resolution\n", encoding="utf-8")
    service = SessionService(SessionStore(tmp_path))
    session = service.create_session("Demo", template_id="lecture")
    service.append_section(session.sessionId, "self.wait(1)")

    reset = service.reset_session(session.sessionId)

    assert reset.templateId == "lecture"
    assert reset.sections == []


def test_existing_session_json_without_template_id_loads_default(tmp_path):
    session_dir = tmp_path / "sessions" / "legacy"
    session_dir.mkdir(parents=True)
    (session_dir / "session.json").write_text(
        json.dumps(
            {
                "sessionId": "legacy",
                "title": "Old",
                "sectionCount": 0,
                "sections": [],
                "latestRender": None,
            }
        ),
        encoding="utf-8",
    )

    loaded = SessionService(SessionStore(tmp_path)).get_session("legacy")

    assert loaded.templateId == "default"
    assert SessionDetail.model_validate_json((session_dir / "session.json").read_text()).templateId == "default"


def test_session_store_persists_sections(tmp_path):
    service = SessionService(SessionStore(tmp_path))
    session = service.create_session("Demo")

    op1 = service.append_section(session.sessionId, "self.add(Circle())")
    op2 = service.append_section(session.sessionId, "self.wait(1)")

    reloaded = SessionService(SessionStore(tmp_path)).get_session(session.sessionId)
    assert [op.sectionId for op in reloaded.sections] == [
        op1.sectionId,
        op2.sectionId,
    ]
    assert reloaded.sectionCount == 2


def test_reset_keeps_session_but_clears_sections(tmp_path):
    service = SessionService(SessionStore(tmp_path))
    session = service.create_session(None)
    service.append_section(session.sessionId, "self.wait(1)")

    reset = service.reset_session(session.sessionId)

    assert reset.sessionId == session.sessionId
    assert reset.sections == []
    assert reset.latestRender is None


class RecordingRenderer:
    def render(self, session_id, sections, cache):
        sections = [
            SectionArtifact(
                sectionId=section.sectionId,
                videoUrl=f"/sessions/{session_id}/sections/{section.sectionId}/video",
            )
            for section in sections
        ]
        return RenderSummary(
            fullVideoUrl=f"/sessions/{session_id}/video", sections=sections
        )


def test_render_is_single_current_snapshot_with_sections(tmp_path):
    service = SessionService(SessionStore(tmp_path), RecordingRenderer())
    session = service.create_session("Demo")

    service.append_section(session.sessionId, "self.wait(1)")
    first = service.render_scene(session.sessionId, RenderCacheMode.USE)
    service.append_section(session.sessionId, "self.wait(2)")
    second = service.render_scene(session.sessionId, RenderCacheMode.USE)

    assert first.fullVideoUrl == f"/sessions/{session.sessionId}/video"
    assert second.fullVideoUrl == f"/sessions/{session.sessionId}/video"
    assert [section.sectionId for section in second.sections] == [
        "0001",
        "0002",
    ]
    assert [section.videoUrl for section in second.sections] == [
        f"/sessions/{session.sessionId}/sections/0001/video",
        f"/sessions/{session.sessionId}/sections/0002/video",
    ]
    assert service.get_session(session.sessionId).latestRender == second
