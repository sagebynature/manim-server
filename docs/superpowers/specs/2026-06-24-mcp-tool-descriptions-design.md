# MCP Tool Descriptions Design

## Goal
Improve MCP client tool selection by replacing terse FastMCP tool docstrings with actionable descriptions. Tool names, parameters, return shapes, and service behavior stay unchanged.

## Scope
Update only `app/mcp.py` tool docstrings and focused tests. The change covers these MCP tools: `create_session`, `list_sessions`, `get_session`, `close_session`, `append_operation`, `render_scene`, and `reset_session`.

## Design
Use FastMCP function docstrings as the single source of tool descriptions. Each docstring will describe:

- when the client should call the tool,
- required or recommended call order,
- parameter meaning,
- return content,
- important side effects.

`append_operation` gets extra guidance because it is the highest-risk and most frequently misused tool. Its description will state that `code` is trusted Python Manim scene-body code appended in order, that clients should call it for incremental scene construction, that `render=False` batches edits, and that `render=True` immediately renders after appending.

`render_scene` and `append_operation` will both explain cache modes: `use`, `refresh`, and `disable`, matching existing `RenderCacheMode` behavior. No validation or enum changes are part of this design.

## Testing
Add focused coverage that proves the descriptions exposed by MCP source functions are substantial and include critical client guidance. Tests should avoid depending on private FastMCP internals unless the public API exposes tool metadata cleanly. At minimum, test the wrapper function docstrings because FastMCP derives descriptions from them.

## Non-goals
Do not rename tools, change parameter names, alter response schemas, add new tools, add retries, or change rendering behavior.
