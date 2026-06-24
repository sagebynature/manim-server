# Session Template Design

## Goal

Add session templates: named file-backed assets that inject boilerplate Manim scene-body Python before any user section runs. The first built-in/default template always adds a title header.

## Scope

- Add optional `templateId` to session creation over REST and MCP.
- Resolve templates from `DATA_DIR/assets/session-templates/<templateId>.py`.
- Fall back to the default template when the requested id is missing or omitted.
- Store the resolved template id on each session.
- Inject template Python before the first generated Manim section.
- Preserve the selected template across reset.

Out of scope:

- Template CRUD APIs.
- Template validation beyond normal render-time Python/Manim errors.
- Full scene wrapper templates.
- New dependencies.

## Chosen approach

Use plain Python template files. A template is authored as normal Manim scene-body code and inserted into the generated `GeneratedScene.construct()` method before any `self.next_section(...)` call.

This keeps authoring simple: no JSON escaping, no mini-language, no extra execution model. It matches existing section behavior, where trusted Python snippets become part of the generated scene script.

## Template assets

Template files live under:

```text
DATA_DIR/assets/session-templates/<templateId>.py
```

The default template id is:

```text
default
```

If `DATA_DIR/assets/session-templates/default.py` exists, it is the default template asset. If it does not exist, the service uses this built-in fallback:

```python
title = Text(session_title or "Untitled").to_edge(UP)
self.add(title)
```

Template ids are path-safe asset names only. Invalid ids, missing ids, and unknown ids resolve to `default` for session creation.

## Template authoring guide

Template files are scene-body Python. Authors start with the first statement they want to run inside `GeneratedScene.construct()`.

They should not include:

- `from manim import *`
- `class GeneratedScene(Scene):`
- `def construct(self):`
- manual indentation for construct scope

Example template file:

```python
# DATA_DIR/assets/session-templates/title-card.py
title = Text(session_title or "Untitled").to_edge(UP)
self.add(title)
self.wait(0.25)
```

Reserved local names available to templates:

```python
session_id: str
session_title: str | None
template_id: str
```

Template code also has access to:

- `self`, the active `GeneratedScene` instance.
- `from manim import *`.
- `from manim.opengl import *`.

Template authors may read the reserved locals. They should not assign to them.

## Injection mechanism

The renderer does not replace placeholder text inside template files. It generates valid Python local assignments before the template body, then indents the template source into `construct()`.

This avoids brittle string replacement in comments, strings, and quoted Python expressions. The reserved names are normal Python locals, so template code stays valid in an editor.

Generated order:

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        session_id = "demo"
        session_title = "Demo"
        template_id = "default"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)

        self.next_section("0001")
        self.wait(1)
```

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
4. If `default.py` is missing, use the built-in default code.

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

`build_scene_script(...)` emits the injected locals, then template code, then user sections. If there are no user sections, the template still renders, followed by the existing short wait if needed to keep Manim output valid.

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

## Tests

Add focused tests:

- Creating a session without `templateId` stores `default`.
- Creating with an unknown `templateId` stores `default`.
- Creating with a file-backed template stores that template id.
- Generated script injects `session_id`, `session_title`, and `template_id` as locals before template code.
- Generated script places template code before first `self.next_section(...)`.
- Reset preserves `templateId`.
- Existing session JSON without `templateId` loads as `default`.

## Non-goals and deliberate shortcuts

No CRUD API for template assets in this version. Operators can add files directly under `DATA_DIR/assets/session-templates`. Add CRUD later only when a client needs to manage templates remotely.
