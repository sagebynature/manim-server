from app.models import RenderCacheMode, RenderSummary, SectionArtifact
from app.sessions import SessionService, SessionStore


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
