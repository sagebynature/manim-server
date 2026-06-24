# Session Template Design

## Goal

Add session templates: named file-backed Manim Python script assets. A template is a full generated scene script that can include imports, `GeneratedScene`, `construct()`, and boilerplate before user sections. The default template adds a title header.

## Scope

- Add optional `templateId` to session creation over REST and MCP.
- Resolve templates from `TEMPLATE_DIR/<templateId>.py`.
- Fall back to the default template when the requested id is missing or omitted.
- Store the resolved template id on each session.
- Render by loading the full template script, replacing reserved quoted literals, then appending generated user sections at the bottom.
- Preserve the selected template across reset.

Out of scope:

- Template CRUD APIs.
- Template validation beyond normal render-time Python/Manim errors.
- Parsing section markers.
- New dependencies.

## Chosen approach

Use full-wrapper Python template files. Authors write the same shape as the generated Manim script:

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)
```

The renderer performs exact replacement of reserved quoted literals, then appends user sections at the file bottom. No marker is parsed. Template authors control everything above the appended sections.

## Template assets

Template files live under:

```text
TEMPLATE_DIR/<templateId>.py
```

The default template id is:

```text
default
```

If `TEMPLATE_DIR/default.py` exists, it is the default template asset. The repository ships `template/default.py`; if the configured default template is missing, session creation fails until the template directory is fixed.

Default file contents:

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)
```

Template ids are path-safe asset names only. Invalid ids, missing ids, and unknown ids resolve to `default` for session creation.

## Template authoring guide

A template is a complete Python file. It should define the scene class that Manim renders:

```python
class GeneratedScene(Scene):
    def construct(self):
        ...
```

Authoring rules:

- Keep the class name `GeneratedScene`; the renderer invokes Manim with that scene name.
- Put boilerplate inside `GeneratedScene.construct()`.
- End the file while still inside `construct()` indentation. User sections are appended at EOF using the same construct indentation.
- Do not call `self.next_section(...)` for user sections; the renderer appends those for each saved section.
- Use the reserved quoted literals only in the injection block.

Recommended injection block:

```python
# DO NOT EDIT: replaced by manim-server before render.
session_id = "__SESSION_ID__"
session_title = "__SESSION_TITLE__"
template_id = "__TEMPLATE_ID__"
```

Template implementation starts after that block:

```python
title = Text(session_title or "Untitled").to_edge(UP)
self.add(title)
self.wait(0.25)
```

Full authoring example:

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        # Template implementation goes here.
        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)

        # User sections are appended below this file by manim-server.
```

## Injection and append mechanism

The renderer does not parse Python and does not search for a section marker. It performs two simple operations:

1. Replace exact reserved quoted literals:
   - `"__SESSION_ID__"` -> `repr(session_id)`
   - `"__SESSION_TITLE__"` -> `repr(session_title)`
   - `"__TEMPLATE_ID__"` -> `repr(template_id)`
2. Append generated section code at the bottom of the template file, indented for `GeneratedScene.construct()`.

Generated result:

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "demo"
        session_title = "Demo"
        template_id = "default"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)

        self.next_section("0001")
        self.wait(1)
```

Using `repr(...)` keeps quotes, newlines, and `None` valid Python values.

## Data model

`CreateSessionRequest` gains:

```python
templateId: str | None = None
```

`SessionDetail` and `SessionSummary` gain:

```python
templateId: str = "default"
```

Existing session JSON without `templateId` should continue to load as `default` through the model default.

## Service behavior

`SessionService.create_session(title, session_id=None, template_id=None)` resolves and stores the template id.

Rules:

1. If `template_id` is omitted, use `default`.
2. If `template_id` points to an existing template file, use it.
3. If `template_id` is invalid or missing, use `default`.
4. If `default.py` is missing, raise a configuration error until `TEMPLATE_DIR/default.py` exists.

`reset_session(session_id)` clears sections and latest render, but preserves `templateId` and title.

## Rendering behavior

`ManimRenderer.render(...)` receives enough session context to call:

```python
build_scene_script(
    sections,
    template_code=resolved_template.code,
    session_id=session_id,
    session_title=session.title,
    template_id=session.templateId,
)
```

`build_scene_script(...)` replaces reserved quoted literals in `template_code`, appends generated user sections at EOF, and returns the complete script. If there are no user sections, the template still renders; the renderer appends the existing short wait only if needed to keep Manim output valid.

## API and MCP

REST:

```http
POST /sessions
{
  "title": "Demo",
  "templateId": "lecture-title"
}
```

MCP:

```python
create_session(title: str | None = None, template_id: str | None = None)
```

MCP uses snake_case because existing MCP tool parameters are Pythonic. It maps to the same service argument.

## Errors

Unknown templates do not fail session creation; they fall back to `default` as requested.

Render-time errors from template Python are treated like section code errors: the Manim render fails and returns the existing render error behavior.

Malformed templates are not rejected at session creation. If a template omits `GeneratedScene`, moves out of `construct()` before EOF, or has invalid Python, render fails with the existing Manim error path.

## Tests

Add focused tests:

- Creating a session without `templateId` stores `default`.
- Creating with an unknown `templateId` stores `default`.
- Creating with a file-backed template stores that template id.
- Generated script replaces reserved quoted literals with valid Python values.
- Generated script appends user sections at EOF after template boilerplate.
- Reset preserves `templateId`.
- Existing session JSON without `templateId` loads as `default`.

## Non-goals and deliberate shortcuts

No CRUD API for template assets in this version. Operators can add files directly under `TEMPLATE_DIR`. Add CRUD later only when a client needs to manage templates remotely.

No marker parser in this version. Appending at EOF is the contract; templates that need code after user sections are a later feature.
