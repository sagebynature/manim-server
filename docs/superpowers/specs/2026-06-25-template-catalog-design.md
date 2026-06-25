# Template Catalog Design

## Goal

Expose every Manim template asset with enough human-readable metadata for an MCP client or REST client to choose the best template before creating a session.

## Scope

- Add descriptive module docstrings to each existing file in `template/`.
- Parse template docstrings without executing template code.
- Add an MCP `list_templates` tool.
- Add a REST `GET /templates` endpoint.
- Keep session creation behavior unchanged: unknown or omitted `templateId` still falls back to `default`.

Out of scope:

- Template CRUD.
- Template rendering validation during listing.
- Sidecar metadata files.
- Ranking, search, or LLM selection logic inside the server.

## Chosen approach

Use module-level Python docstrings as template metadata. The docstring lives at the top of each template file, so metadata moves with the code it describes. `TemplateStore` reads each safe `*.py` file from `TEMPLATE_DIR`, parses the module with `ast.parse`, and extracts `ast.get_docstring(module)`.

No template file is imported or executed during listing.

## Template metadata shape

Return a compact summary per template:

```json
{
  "templateId": "dark-grid",
  "description": "Dark background with a blue coordinate grid and title label.",
  "useCases": "Math explainers, graph-heavy scenes, coordinate geometry, and technical diagrams."
}
```

`description` is the first non-empty docstring line. `useCases` is the remaining docstring text, joined and trimmed. If a template has only one docstring line, `useCases` is an empty string.

## Store behavior

Add a `TemplateSummary` data object and a `TemplateStore.list_templates()` method.

Rules:

1. Only direct `*.py` children of `TEMPLATE_DIR` are listed.
2. File stems must pass the existing safe template-id rule.
3. Results are sorted by `templateId` for deterministic clients and tests.
4. Missing `TEMPLATE_DIR` returns an empty list.
5. Invalid Python syntax does not execute; parsing errors surface as configuration errors in tests and local development.

## REST API

Add:

```http
GET /templates
```

Response:

```json
{
  "templates": [
    {
      "templateId": "default",
      "description": "...",
      "useCases": "..."
    }
  ]
}
```

Add `TemplateSummary` and `ListTemplatesResponse` Pydantic models.

## MCP API

Add `list_templates` to `create_tool_functions()` and `create_mcp_server()`.

Tool description should explicitly tell clients to call it before `create_session` when they need to choose a `template_id`.

## Existing templates

Add concise docstrings to:

- `default.py`: basic title header and general-purpose scenes.
- `clean-title.py`: title with underline for simple structured videos.
- `dark-grid.py`: dark grid background for graph/math scenes.
- `presentation-card.py`: animated intro/title card.
- `three-d.py`: `ThreeDScene` base for camera and 3D object scenes.

## Tests

Follow TDD:

1. `TemplateStore.list_templates()` returns parsed docstring metadata for fixture templates and does not execute code.
2. MCP `list_templates` returns the same template catalog shape.
3. REST `GET /templates` returns the complete list.
4. Existing MCP tool-description test includes the new tool guidance.

## Risks

- Docstrings can drift from template behavior. Keeping metadata in the template file minimizes this risk versus hardcoded registries.
- Multi-paragraph docstrings need deterministic splitting. The first line is description; remaining lines are use cases.
