# Session Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add named file-backed full-wrapper session templates that inject session metadata by replacing reserved quoted literals and append saved sections at EOF.

**Architecture:** Add a tiny template asset loader beside the session service, store the resolved `templateId` on session models, and pass the resolved template script into the renderer. The renderer treats the template as the complete Manim script, performs exact literal replacement, and appends generated section code at the file bottom.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Manim Community, pytest, FastMCP.

## Global Constraints

- No new dependencies.
- Template files live at `TEMPLATE_DIR/<templateId>.py`.
- Missing, omitted, invalid, or unknown template ids resolve to `default`.
- Repository ships `template/default.py`; missing configured `default.py` is a configuration error.
- Template script must define `GeneratedScene`; malformed templates fail at render time through the existing Manim error path.
- Renderer replaces only exact quoted literals: `"__SESSION_ID__"`, `"__SESSION_TITLE__"`, `"__TEMPLATE_ID__"`.
- Renderer appends user sections at EOF; no section marker parsing.
- Reset preserves `templateId`.
- Existing session JSON without `templateId` loads as `default`.
- Shell commands use `rtk` prefix.

---

## File Structure

- Create `app/templates.py`: path-safe template id validation and file-backed template resolution.
- Modify `app/models.py`: add `templateId` to create request, detail, and summary models.
- Modify `app/sessions.py`: own a `TemplateStore`, resolve template id during session creation, preserve template id on reset, pass template script/context into renderer.
- Modify `app/renderer.py`: turn `build_scene_script()` into full-wrapper template injection plus EOF section append.
- Modify `app/main.py`: pass `body.templateId` into session creation.
- Modify `app/mcp.py`: expose `template_id` on `create_session()`.
- Modify `app/docs.py`: document `templateId` and fallback behavior.
- Modify `README.md`: add operator authoring notes for full-wrapper template assets.
- Modify tests in `tests/test_sessions.py`, `tests/test_renderer.py`, `tests/test_api.py`, and `tests/test_mcp.py`.

---

### Task 1: Template Asset Resolution And Session Models

**Files:**

- Create: `app/templates.py`
- Modify: `app/models.py`
- Modify: `app/sessions.py`
- Test: `tests/test_sessions.py`

**Interfaces:**

- Produces: `DEFAULT_TEMPLATE_ID = "default"`.
- Produces: `DEFAULT_TEMPLATE_SCRIPT: str` full-wrapper Manim script containing the reserved quoted literals.
- Produces: `TemplateAsset(templateId: str, code: str)` dataclass.
- Produces: `TemplateStore(data_dir: Path).resolve(template_id: str | None) -> TemplateAsset`.
- Changes: `CreateSessionRequest.templateId: str | None = None`.
- Changes: `SessionDetail.templateId: str = "default"`.
- Changes: `SessionSummary.templateId: str = "default"`.
- Changes: `SessionService.create_session(title, session_id=None, template_id=None) -> SessionDetail`.

- [ ] **Step 1: Write failing session/template tests**

Add these tests to `tests/test_sessions.py`:

```python
import json

from app.models import SessionDetail


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
    template_dir = tmp_path / "template"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text(
        'from manim import *\n\nclass GeneratedScene(Scene):\n'
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
    template_dir = tmp_path / "template"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text("# valid enough for resolution\n", encoding="utf-8")
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
```

- [ ] **Step 2: Run tests and verify they fail for missing feature**

Run:

```bash
rtk pytest tests/test_sessions.py -q
```

Expected: FAIL because `SessionDetail` has no `templateId` and `SessionService.create_session()` does not accept `template_id`.

- [ ] **Step 3: Add template asset store**

Create `app/templates.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_TEMPLATE_ID = "default"
DEFAULT_TEMPLATE_SCRIPT = '''from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)
'''


@dataclass(frozen=True)
class TemplateAsset:
    templateId: str
    code: str


class TemplateStore:
    def __init__(self, data_dir: Path):
        self.templates_dir = template_dir

    def resolve(self, template_id: str | None) -> TemplateAsset:
        template_id = template_id if self._safe_id(template_id) else DEFAULT_TEMPLATE_ID
        path = self.templates_dir / f"{template_id}.py"
        if path.exists():
            return TemplateAsset(template_id, path.read_text(encoding="utf-8"))

        default_path = self.templates_dir / f"{DEFAULT_TEMPLATE_ID}.py"
        if default_path.exists():
            return TemplateAsset(
                DEFAULT_TEMPLATE_ID, default_path.read_text(encoding="utf-8")
            )

        return TemplateAsset(DEFAULT_TEMPLATE_ID, DEFAULT_TEMPLATE_SCRIPT)

    @staticmethod
    def _safe_id(template_id: str | None) -> bool:
        return bool(template_id) and template_id.replace("-", "_").isidentifier()
```

- [ ] **Step 4: Add model fields**

Modify `app/models.py`:

```python
class CreateSessionRequest(BaseModel):
    title: str | None = None
    templateId: str | None = None
```

```python
class SessionDetail(BaseModel):
    sessionId: str
    title: str | None = None
    templateId: str = "default"
    sectionCount: int
    sections: list[Section]
    latestRender: RenderSummary | None = None
```

```python
class SessionSummary(BaseModel):
    sessionId: str
    title: str | None = None
    templateId: str = "default"
    sectionCount: int
    latestRender: RenderSummary | None = None
```

- [ ] **Step 5: Resolve template ids in the session service**

Modify `app/sessions.py` imports:

```python
from app.templates import TemplateStore
```

Modify `SessionService.__init__` and `create_session`:

```python
class SessionService:
    def __init__(self, store: SessionStore, renderer=None, templates: TemplateStore | None = None):
        self.store = store
        self.renderer = renderer
        self.templates = templates or TemplateStore(store.data_dir)

    def create_session(
        self,
        title: str | None,
        session_id: str | None = None,
        template_id: str | None = None,
    ) -> SessionDetail:
        session_id = session_id or str(uuid4())
        if "/" in session_id or ".." in session_id:
            raise ValueError(f"invalid sessionId: {session_id}")
        if self.store.path(session_id).exists():
            raise ValueError(f"sessionId already exists: {session_id}")
        template = self.templates.resolve(template_id)
        detail = SessionDetail(
            sessionId=session_id,
            title=title,
            templateId=template.templateId,
            sectionCount=0,
            sections=[],
        )
        self.store.save(detail)
        return detail
```

`reset_session()` needs no new code beyond preserving the existing `detail.templateId` field.

- [ ] **Step 6: Run task tests and verify they pass**

Run:

```bash
rtk pytest tests/test_sessions.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
rtk git add app/templates.py app/models.py app/sessions.py tests/test_sessions.py
rtk git commit -m "feat: resolve session template assets"
```

---

### Task 2: Full-Wrapper Renderer Injection

**Files:**

- Modify: `app/renderer.py`
- Test: `tests/test_renderer.py`

**Interfaces:**

- Consumes: `DEFAULT_TEMPLATE_SCRIPT` from `app.templates`.
- Changes: `build_scene_script(sections, template_code=DEFAULT_TEMPLATE_SCRIPT, session_id="", session_title=None, template_id="default") -> str`.
- Produces: section append still emits title comments, `self.next_section(sectionId)`, and section code in order.
- Keeps: `ManimRenderer.render(session_id, sections, cache, template_code=DEFAULT_TEMPLATE_SCRIPT, session_title=None, template_id="default") -> RenderSummary` defaults so current direct renderer tests still call it with three args.

- [ ] **Step 1: Write failing renderer tests**

Modify `tests/test_renderer.py` by adding tests:

```python
FULL_TEMPLATE = '''from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)
'''


def test_build_scene_script_replaces_template_literals_and_appends_sections():
    script = build_scene_script(
        [op("0001", "self.wait(1)")],
        template_code=FULL_TEMPLATE,
        session_id="s1",
        session_title='A "quoted" title',
        template_id="lecture",
    )

    assert "session_id = 's1'" in script
    assert 'session_title = \'A "quoted" title\'' in script
    assert "template_id = 'lecture'" in script
    assert "__SESSION_ID__" not in script
    assert script.index("self.add(title)") < script.index("self.next_section('0001')")
    assert script.rstrip().endswith("self.wait(1)")


def test_build_scene_script_turns_missing_title_into_python_none():
    script = build_scene_script(
        [], template_code=FULL_TEMPLATE, session_id="s1", session_title=None
    )

    assert "session_title = None" in script
    assert script.rstrip().endswith("self.wait(0.1)")
```

Update existing `test_build_scene_script_adds_section_title_comment()` and `test_build_scene_script_names_sections_before_sections()` only if needed; their substring assertions should still hold.

- [ ] **Step 2: Run renderer tests and verify failure**

Run:

```bash
rtk pytest tests/test_renderer.py -q
```

Expected: FAIL because `build_scene_script()` does not accept template context.

- [ ] **Step 3: Implement template injection and EOF append**

Modify `app/renderer.py` imports:

```python
from app.templates import DEFAULT_TEMPLATE_ID, DEFAULT_TEMPLATE_SCRIPT
```

Replace `build_scene_script()` with:

```python
def build_scene_script(
    sections: Sequence[Section],
    template_code: str = DEFAULT_TEMPLATE_SCRIPT,
    session_id: str = "",
    session_title: str | None = None,
    template_id: str = DEFAULT_TEMPLATE_ID,
) -> str:
    script = (
        template_code.replace('"__SESSION_ID__"', repr(session_id))
        .replace('"__SESSION_TITLE__"', repr(session_title))
        .replace('"__TEMPLATE_ID__"', repr(template_id))
        .rstrip()
    )
    lines = script.splitlines()

    if not sections:
        lines.append("        self.wait(0.1)")
        return "\n".join(lines) + "\n"

    for section in sections:
        if not section.code.strip():
            raise ValueError("section code is empty")
        if section.title is not None:
            for title_line in section.title.splitlines() or [""]:
                lines.append(f"        # {title_line}")
        lines.append(f"        self.next_section({section.sectionId!r})")
        lines.extend(
            f"        {line}" if line.strip() else ""
            for line in section.code.strip("\n").splitlines()
        )

    return "\n".join(lines) + "\n"
```

Modify `ManimRenderer.render()` signature and scene write:

```python
def render(
    self,
    session_id: str,
    sections: list[Section],
    cache: RenderCacheMode,
    template_code: str = DEFAULT_TEMPLATE_SCRIPT,
    session_title: str | None = None,
    template_id: str = DEFAULT_TEMPLATE_ID,
) -> RenderSummary:
    ...
    scene_path.write_text(
        build_scene_script(
            sections,
            template_code=template_code,
            session_id=session_id,
            session_title=session_title,
            template_id=template_id,
        ),
        encoding="utf-8",
    )
```

Keep the rest of `render()` unchanged.

- [ ] **Step 4: Run renderer tests and verify pass**

Run:

```bash
rtk pytest tests/test_renderer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add app/renderer.py tests/test_renderer.py
rtk git commit -m "feat: render full wrapper session templates"
```

---

### Task 3: Wire REST, MCP, And Render Context

**Files:**

- Modify: `app/sessions.py`
- Modify: `app/main.py`
- Modify: `app/mcp.py`
- Modify: `app/docs.py`
- Test: `tests/test_api.py`
- Test: `tests/test_mcp.py`
- Test: `tests/test_sessions.py`

**Interfaces:**

- Consumes: `TemplateStore.resolve()` and `TemplateAsset.code`.
- Changes: `SessionService.render_scene(session_id, cache)` resolves the stored template before calling renderer.
- Changes: REST `POST /sessions` accepts JSON `templateId`.
- Changes: MCP `create_session(title=None, template_id=None)` accepts snake_case `template_id`.

- [ ] **Step 1: Write failing service render-context test**

Modify `RecordingRenderer` in `tests/test_sessions.py`:

```python
class RecordingRenderer:
    def __init__(self):
        self.calls = []

    def render(
        self,
        session_id,
        sections,
        cache,
        template_code,
        session_title=None,
        template_id="default",
    ):
        self.calls.append(
            {
                "session_id": session_id,
                "template_code": template_code,
                "session_title": session_title,
                "template_id": template_id,
            }
        )
        artifacts = [
            SectionArtifact(
                sectionId=section.sectionId,
                videoUrl=f"/sessions/{session_id}/sections/{section.sectionId}/video",
            )
            for section in sections
        ]
        return RenderSummary(fullVideoUrl=f"/sessions/{session_id}/video", sections=artifacts)
```

Add:

```python
def test_render_passes_resolved_template_context(tmp_path):
    template_dir = tmp_path / "template"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text("# lecture template\n", encoding="utf-8")
    renderer = RecordingRenderer()
    service = SessionService(SessionStore(tmp_path), renderer)
    session = service.create_session("Demo", template_id="lecture")

    service.render_scene(session.sessionId, RenderCacheMode.USE)

    assert renderer.calls[-1] == {
        "session_id": session.sessionId,
        "template_code": "# lecture template\n",
        "session_title": "Demo",
        "template_id": "lecture",
    }
```

- [ ] **Step 2: Write failing REST/MCP tests**

Add to `tests/test_api.py`:

```python
def test_create_session_accepts_template_id(tmp_path: Path):
    template_dir = tmp_path / "template"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text("# lecture template\n", encoding="utf-8")
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post("/sessions", json={"title": "Demo", "templateId": "lecture"})

    assert response.status_code == 200
    assert response.json()["templateId"] == "lecture"


def test_create_session_unknown_template_falls_back_to_default(tmp_path: Path):
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post("/sessions", json={"title": "Demo", "templateId": "missing"})

    assert response.status_code == 200
    assert response.json()["templateId"] == "default"
```

Add to `tests/test_mcp.py`:

```python
def test_mcp_create_session_accepts_template_id(tmp_path):
    template_dir = tmp_path / "template"
    template_dir.mkdir(parents=True)
    (template_dir / "lecture.py").write_text("# lecture template\n", encoding="utf-8")
    tools = create_tool_functions(SessionService(SessionStore(tmp_path)))

    session = tools["create_session"]("Demo", template_id="lecture")

    assert session["templateId"] == "lecture"
```

- [ ] **Step 3: Run targeted tests and verify failure**

Run:

```bash
rtk pytest tests/test_sessions.py::test_render_passes_resolved_template_context tests/test_api.py::test_create_session_accepts_template_id tests/test_api.py::test_create_session_unknown_template_falls_back_to_default tests/test_mcp.py::test_mcp_create_session_accepts_template_id -q
```

Expected: FAIL because render context, REST `templateId`, and MCP `template_id` are not wired yet.

- [ ] **Step 4: Pass template context through the service**

Modify `SessionService.render_scene()` in `app/sessions.py`:

```python
def render_scene(self, session_id: str, cache: RenderCacheMode) -> RenderSummary:
    if self.renderer is None:
        raise RuntimeError("renderer not configured")
    detail = self.store.load(session_id)
    template = self.templates.resolve(detail.templateId)
    summary = self.renderer.render(
        detail.sessionId,
        detail.sections,
        cache,
        template.code,
        session_title=detail.title,
        template_id=template.templateId,
    )
    detail.latestRender = summary
    self.store.save(detail)
    return summary
```

- [ ] **Step 5: Wire REST and MCP create session**

Modify `app/main.py` create route:

```python
return service.create_session(
    body.title, manim_session_id or sessionId, body.templateId
)
```

Modify `app/mcp.py` create tool:

```python
def create_session(title: str | None = None, template_id: str | None = None):
    return dump(service.create_session(title, template_id=template_id))
```

- [ ] **Step 6: Update endpoint docs**

Modify `app/docs.py` `create_session` text to include:

```python
"Optional templateId selects a file-backed template asset from "
"TEMPLATE_DIR; missing or unknown templateId "
"falls back to default. "
```

Keep the existing `Manim-Session-ID` wording.

- [ ] **Step 7: Run targeted tests and verify pass**

Run:

```bash
rtk pytest tests/test_sessions.py tests/test_api.py tests/test_mcp.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
rtk git add app/sessions.py app/main.py app/mcp.py app/docs.py tests/test_sessions.py tests/test_api.py tests/test_mcp.py
rtk git commit -m "feat: expose session templates in API and MCP"
```

---

### Task 4: README And Final Verification

**Files:**

- Modify: `README.md`
- Test: full focused suite for session templates and existing session/render/API/MCP behavior.

**Interfaces:**

- Consumes: all code from Tasks 1-3.
- Produces: operator-facing instructions for full-wrapper template authoring.

- [ ] **Step 1: Update README template documentation**

Add section before `## MCP endpoint`:

````markdown
## Session templates

`POST /sessions` accepts optional `templateId`:

```bash
curl -sS -X POST http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Lecture","templateId":"lecture"}'
```

Templates are Python files under `TEMPLATE_DIR/<templateId>.py`.
Unknown or missing template ids fall back to `default`. If `default.py` is absent,
the server uses the built-in title-header template.

Template files are full Manim scripts. Keep the scene class named
`GeneratedScene`; user sections are appended at EOF inside `construct()`.

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)

        # user sections are appended here by EOF contract
```
````

- [ ] **Step 2: Run focused test suite**

Run:

```bash
rtk pytest tests/test_sessions.py tests/test_renderer.py tests/test_api.py tests/test_mcp.py -q
```

Expected: PASS.

- [ ] **Step 3: Run formatting/lint/type checks if present in Makefile**

Run:

```bash
rtk make lint
rtk make typecheck
```

Expected: PASS. If a command fails because the project lacks the tool locally, capture the exact failure and do not claim that gate passed.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
rtk git add README.md
rtk git commit -m "docs: document session templates"
```
