from typing import NamedTuple


class EndpointDoc(NamedTuple):
    summary: str
    description: str


DOCS: dict[str, EndpointDoc] = {
    "create_session": EndpointDoc(
        "Create session",
        "Start here: create new Manim scene session. Use this before append_section "
        "or render_scene building new animation. Optional title labels "
        "session in later list/get calls. Manim-Session-ID header or "
        "sessionId cookie may set the session id. Returns sessionId, title, section count, and render metadata.",
    ),
    "list_sessions": EndpointDoc(
        "List sessions",
        "List existing Manim scene sessions. Use to find prior sessionId values "
        "before get_session, append_section, render_scene, reset_session, or "
        "close_session. Returns summary metadata only; call get_session for the "
        "full section log.",
    ),
    "get_session": EndpointDoc(
        "Get session",
        "Get one Manim session by sessionId. Use after create_session or "
        "list_sessions to inspect the current section log, render status, and "
        "generated media URLs before deciding whether to append, render, reset, "
        "or close the session.",
    ),
    "close_session": EndpointDoc(
        "Close session",
        "Close one Manim session by sessionId. Use when the client is finished "
        "with a session and wants the server to remove active session storage. "
        "Returns whether the session closed; closed sessions cannot be appended "
        "or rendered.",
    ),
    "append_section": EndpointDoc(
        "Append section",
        "Use tool append one logical animation step to an existing Manim session. "
        "The code parameter is trusted Python Manim scene-body code, written as "
        "statements run inside the current Scene construct method. Sections are "
        "appended in order, so use this for incremental scene construction after "
        "create_session. Prefer render=False while batching multiple small edits; "
        "use render=True when the client needs an immediate video update after the "
        "append. cache controls rendering when render=True: use reuses existing "
        "Manim cache, refresh rerenders with cache refresh, disable renders without "
        "cache. Returns the appended section and latestRender only when render=True.",
    ),
    "render_scene": EndpointDoc(
        "Render scene",
        "Render an existing Manim session synchronously. Use after one or more "
        "append_section calls with render=False when the client needs a fresh "
        "video URL. cache may be use, refresh, or disable. Returns the full video "
        "URL and section metadata.",
    ),
    "reset_session": EndpointDoc(
        "Reset session",
        "Reset an existing Manim session section log. Use to keep the same "
        "sessionId but remove all appended Manim sections before rebuilding the "
        "scene. This does not create a new session; call append_section next with "
        "replacement scene-body code.",
    ),
}
