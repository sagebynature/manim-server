# Template Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let MCP and REST clients list every template with docstring-derived guidance before creating a session.

**Architecture:** Template metadata lives in module docstrings inside `template/*.py`. `TemplateStore` parses those files with `ast` and exposes deterministic summaries. REST and MCP call the same `SessionService.list_templates()` path.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, FastMCP, pytest, standard-library `ast` and `pathlib` only.

## Global Constraints

- Use `rtk` before shell commands.
- Do not import or execute template files while listing metadata.
- No new dependencies.
- Preserve existing `create_session` fallback behavior for missing or invalid `templateId`.
- Keep `templateId` spelling in public JSON models.
- Tests first: each production behavior needs a failing pytest before implementation.

---

## File Structure

- Modify `template/default.py`, `template/clean-title.py`, `template/dark-grid.py`, `template/presentation-card.py`, `template/three-d.py`: add module docstrings.
- Modify `app/templates.py`: add `TemplateSummary` dataclass and docstring parsing/listing.
- Modify `app/sessions.py`: expose `SessionService.list_templates()`.
- Modify `app/models.py`: add `TemplateSummary` and `ListTemplatesResponse` Pydantic response models.
- Modify `app/docs.py`: add `list_templates` endpoint/tool documentation and update `create_session` guidance.
- Modify `app/main.py`: add `GET /templates` route.
- Modify `app/mcp.py`: add MCP `list_templates` tool.
- Modify `tests/test_three_d_template.py` or create `tests/test_templates.py`: template docstring and store tests.
- Modify `tests/test_api.py`: REST/OpenAPI tests.
- Modify `tests/test_mcp.py`: MCP tool tests.

---

## Task 1: Template docstrings and store listing

**Files:**
- Modify: `template/default.py`
- Modify: `template/clean-title.py`
- Modify: `template/dark-grid.py`
- Modify: `template/presentation-card.py`
- Modify: `template/three-d.py`
- Modify: `app/templates.py`
- Create or modify: `tests/test_templates.py`

**Interfaces:**
- Produces: `app.templates.TemplateSummary(templateId: str, description: str, useCases: str)`
- Produces: `TemplateStore.list_templates() -> list[TemplateSummary]`
- Consumed by: Task 2 REST and Task 3 MCP via `SessionService.list_templates()`.

- [ ] **Step 1: Write failing template metadata tests**

Add `tests/test_templates.py`:

```python
import ast
from pathlib import Path

from app.templates import TemplateStore


def test_all_builtin_templates_have_docstrings():
    template_paths = sorted(Path("template").glob("*.py"))

    assert template_paths
    for path in template_paths:
        module = ast.parse(path.read_text(encoding="utf-8"))
        assert ast.get_docstring(module), f"{path} needs a module docstring"


def test_template_store_lists_docstring_metadata_without_executing_code(tmp_path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "alpha.py").write_text(
        '\n'.join(
            [
                '"""Alpha template.',
                '',
                'Use for algebra explainers and quick title cards.',
                'Best when the user wants a simple 2D scene.',
                '"""',
                'raise RuntimeError("must not execute")',
            ]
        ),
        encoding="utf-8",
    )
    (template_dir / "bad/name.py").parent.mkdir(exist_ok=True)
    (template_dir / "bad/name.py").write_text('"""Ignored nested template."""', encoding="utf-8")

    templates = TemplateStore(template_dir).list_templates()

    assert [template.templateId for template in templates] == ["alpha"]
    assert templates[0].description == "Alpha template."
    assert templates[0].useCases == (
        "Use for algebra explainers and quick title cards. "
        "Best when the user wants a simple 2D scene."
    )
```

- [ ] **Step 2: Run tests verify fail**

Run:

```bash
rtk pytest tests/test_templates.py -q
```

Expected: `test_all_builtin_templates_have_docstrings` fails because current template files have no module docstrings, and `test_template_store_lists_docstring_metadata_without_executing_code` fails because `TemplateStore.list_templates` does not exist.

- [ ] **Step 3: Add template docstrings**

Add these exact module docstrings as the first statement in each template, before imports:

`template/default.py`:

```python
"""Default title template.

Use for general-purpose 2D Manim scenes that need a simple title anchored at the top before user-authored animation sections begin.
"""
```

`template/clean-title.py`:

```python
"""Clean title template with underline.

Use for tutorials, lecture snippets, and structured explainer videos that need a restrained title treatment without a background grid.
"""
```

`template/dark-grid.py`:

```python
"""Dark grid template.

Use for math explainers, graph-heavy scenes, coordinate geometry, and technical diagrams that benefit from a persistent dark coordinate plane.
"""
```

`template/presentation-card.py`:

```python
"""Animated presentation card template.

Use for opening title cards, chapter breaks, and short presentation-style intros before the main user-authored animation begins.
"""
```

`template/three-d.py`:

```python
"""Three-dimensional scene template.

Use for 3D axes, camera movement, surfaces, spheres, and other scenes that require Manim's ThreeDScene instead of the default 2D Scene.
"""
```

- [ ] **Step 4: Implement store listing**

In `app/templates.py`, add imports and code equivalent to:

```python
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TEMPLATE_ID: str = "default"


@dataclass(frozen=True)
class TemplateAsset:
    templateId: str
    code: str


@dataclass(frozen=True)
class TemplateSummary:
    templateId: str
    description: str
    useCases: str


class TemplateStore:
    def __init__(self, template_dir: Path):
        self.templates_dir = template_dir

    def resolve(self, template_id: str | None) -> TemplateAsset:
        if template_id is None or not self._safe_id(template_id):
            template_id = DEFAULT_TEMPLATE_ID
        path = self.templates_dir / f"{template_id}.py"
        if path.exists():
            return TemplateAsset(template_id, path.read_text(encoding="utf-8"))

        default_path = self.templates_dir / f"{DEFAULT_TEMPLATE_ID}.py"
        if default_path.exists():
            return TemplateAsset(
                DEFAULT_TEMPLATE_ID, default_path.read_text(encoding="utf-8")
            )

        raise FileNotFoundError(f"missing default template: {default_path}")

    def list_templates(self) -> list[TemplateSummary]:
        if not self.templates_dir.exists():
            return []

        summaries = []
        for path in sorted(self.templates_dir.glob("*.py")):
            template_id = path.stem
            if not self._safe_id(template_id):
                continue
            summaries.append(self._summarize(template_id, path))
        return summaries

    def _summarize(self, template_id: str, path: Path) -> TemplateSummary:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring = ast.get_docstring(module) or ""
        lines = [line.strip() for line in docstring.splitlines() if line.strip()]
        description = lines[0] if lines else ""
        use_cases = " ".join(lines[1:])
        return TemplateSummary(template_id, description, use_cases)

    @staticmethod
    def _safe_id(template_id: str | None) -> bool:
        return bool(template_id) and template_id.replace("-", "_").isidentifier()
```

- [ ] **Step 5: Run tests verify pass**

Run:

```bash
rtk pytest tests/test_templates.py -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit task**

Run:

```bash
rtk git add app/templates.py template/default.py template/clean-title.py template/dark-grid.py template/presentation-card.py template/three-d.py tests/test_templates.py && rtk git commit -m "feat: list template metadata"
```

---

## Task 2: REST template catalog endpoint

**Files:**
- Modify: `app/models.py`
- Modify: `app/sessions.py`
- Modify: `app/docs.py`
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `TemplateStore.list_templates() -> list[app.templates.TemplateSummary]`
- Produces: `SessionService.list_templates() -> list[app.templates.TemplateSummary]`
- Produces: `GET /templates -> ListTemplatesResponse`

- [ ] **Step 1: Write failing REST test**

Add to `tests/test_api.py`:

```python
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
```

Extend `test_openapi_documents_request_and_response_payloads`:

```python
shared_routes = (
    ("list_templates", "get", "/templates"),
    ("create_session", "post", "/sessions"),
    ("list_sessions", "get", "/sessions"),
    ("get_session", "get", "/sessions/{session_id}"),
    ("close_session", "delete", "/sessions/{session_id}"),
    ("append_section", "post", "/sessions/{session_id}/section"),
    ("render_scene", "post", "/sessions/{session_id}/render"),
    ("reset_session", "post", "/sessions/{session_id}/reset"),
)
```

Add schema assertion:

```python
assert json_schema("get", "/templates") == {
    "$ref": "#/components/schemas/ListTemplatesResponse"
}
```

- [ ] **Step 2: Run tests verify fail**

Run:

```bash
rtk pytest tests/test_api.py::test_list_templates_returns_builtin_template_catalog tests/test_api.py::test_openapi_documents_request_and_response_payloads -q
```

Expected: `/templates` is missing and `list_templates` docs/tool mapping is missing.

- [ ] **Step 3: Add Pydantic models**

In `app/models.py`, add before `ListSessionsResponse`:

```python
class TemplateSummary(BaseModel):
    templateId: str
    description: str
    useCases: str


class ListTemplatesResponse(BaseModel):
    templates: list[TemplateSummary]
```

- [ ] **Step 4: Add service method**

In `app/sessions.py`, add to `SessionService`:

```python
def list_templates(self):
    return self.templates.list_templates()
```

Use the existing `self.templates` field; do not alter create/reset/render behavior.

- [ ] **Step 5: Add docs entry**

In `app/docs.py`, add:

```python
"list_templates": EndpointDoc(
    "List templates",
    "Fetch the complete Manim template catalog before creating a session. "
    "Use this to compare templateId, description, and useCases values, then "
    "pass the selected templateId to create_session. Returns all file-backed "
    "templates available under TEMPLATE_DIR.",
),
```

Update `create_session` description to mention calling `list_templates` first when choosing a template.

- [ ] **Step 6: Add route**

In `app/main.py`, import `ListTemplatesResponse` and add near health/ready or before `/sessions`:

```python
@app.get(
    "/templates",
    response_model=ListTemplatesResponse,
    summary=DOCS["list_templates"].summary,
    description=DOCS["list_templates"].description,
)
def list_templates():
    return ListTemplatesResponse(templates=service.list_templates())
```

- [ ] **Step 7: Run tests verify pass**

Run:

```bash
rtk pytest tests/test_api.py::test_list_templates_returns_builtin_template_catalog tests/test_api.py::test_openapi_documents_request_and_response_payloads -q
```

Expected: both tests pass.

- [ ] **Step 8: Commit task**

Run:

```bash
rtk git add app/models.py app/sessions.py app/docs.py app/main.py tests/test_api.py && rtk git commit -m "feat: expose template catalog over rest"
```

---

## Task 3: MCP template catalog tool

**Files:**
- Modify: `app/mcp.py`
- Modify: `tests/test_mcp.py`

**Interfaces:**
- Consumes: `SessionService.list_templates() -> list[app.templates.TemplateSummary]`
- Produces: MCP tool `list_templates() -> {"templates": list[dict[str, str]]}`

- [ ] **Step 1: Write failing MCP tests**

Add to `tests/test_mcp.py`:

```python
def test_mcp_list_templates_returns_template_catalog(tmp_path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "alpha.py").write_text(
        '"""Alpha template.\n\nUse for concise 2D scenes."""\n', encoding="utf-8"
    )
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), templates=TemplateStore(template_dir))
    )

    result = tools["list_templates"]()

    assert result == {
        "templates": [
            {
                "templateId": "alpha",
                "description": "Alpha template.",
                "useCases": "Use for concise 2D scenes.",
            }
        ]
    }
```

Extend `test_mcp_tool_descriptions_guide_clients`:

```python
list_description = tools["list_templates"].description
assert "complete Manim template catalog" in list_description
assert "before creating a session" in list_description
assert "templateId" in list_description
```

- [ ] **Step 2: Run tests verify fail**

Run:

```bash
rtk pytest tests/test_mcp.py::test_mcp_list_templates_returns_template_catalog tests/test_mcp.py::test_mcp_tool_descriptions_guide_clients -q
```

Expected: `list_templates` tool is missing.

- [ ] **Step 3: Add MCP tool function**

In `app/mcp.py` inside `create_tool_functions`, add:

```python
def list_templates():
    return {"templates": [dump(item) for item in service.list_templates()]}
```

Add it to the `tools` dict before `create_session`:

```python
tools = {
    "list_templates": list_templates,
    "create_session": create_session,
    "list_sessions": list_sessions,
    "get_session": get_session,
    "close_session": close_session,
    "append_section": append_section,
    "render_scene": render_scene,
    "reset_session": reset_session,
}
```

- [ ] **Step 4: Register MCP server tool**

In `create_mcp_server`, bind the wrapped tool from `tools` the same way existing tools are bound:

```python
mcp.tool(description=DOCS["list_templates"].description)(tools["list_templates"])
```

Place it before `create_session` so clients see discovery guidance first.

- [ ] **Step 5: Run tests verify pass**

Run:

```bash
rtk pytest tests/test_mcp.py::test_mcp_list_templates_returns_template_catalog tests/test_mcp.py::test_mcp_tool_descriptions_guide_clients -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit task**

Run:

```bash
rtk git add app/mcp.py tests/test_mcp.py && rtk git commit -m "feat: expose template catalog over mcp"
```

---

## Task 4: Integration verification

**Files:**
- Modify only if verification reveals a bug in files touched by Tasks 1-3.

**Interfaces:**
- Verifies: template metadata, REST route, MCP tool, existing session behavior.

- [ ] **Step 1: Run focused tests**

Run:

```bash
rtk pytest tests/test_templates.py tests/test_api.py tests/test_mcp.py tests/test_three_d_template.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run type and lint gates**

Run:

```bash
rtk ty check .
rtk ruff check .
```

Expected: both pass. If `ty` is unavailable outside the project environment, use the Makefile or project virtual environment command already used by this repo.

- [ ] **Step 3: Commit verification fixes if any**

If Step 1 or Step 2 required fixes, commit only those fixes:

```bash
rtk git add app tests template && rtk git commit -m "fix: stabilize template catalog"
```

If no fixes were needed, do not create an empty commit.
