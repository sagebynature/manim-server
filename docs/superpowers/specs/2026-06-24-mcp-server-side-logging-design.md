# MCP Server-Side Logging Design

## Goal
Enhance server-side logging for MCP tool requests so operators can see which tool was invoked, sanitized inputs, outcome, duration, and failure details without exposing large submitted Manim code blocks.

## Current State
`app/main.py` logs HTTP route method, path, status code, and duration for every request, including `/mcp`. That proves traffic reached the service but does not show which MCP tool ran or what sanitized request payload was involved. `app/mcp.py` centralizes MCP tool functions through `create_tool_functions`, so one wrapper there can cover all MCP tools.

## Decision
Wrap the tool functions returned by `create_tool_functions` with a small logging decorator in `app/mcp.py`.

Each MCP tool invocation logs:

- tool name,
- sanitized positional and keyword arguments,
- status (`ok` or `failed`),
- duration in milliseconds,
- error type on failure.

The wrapper re-raises exceptions unchanged so existing MCP error behavior and response schemas remain unchanged.

## Sanitization
Log sanitized values, not full raw arguments.

Rules:

- `str`, `int`, `float`, `bool`, and `None` are logged directly when small.
- Long strings are truncated with their original length preserved.
- The `code` argument is always redacted as a code summary such as `<redacted code len=1234>`.
- Lists, tuples, and dictionaries are summarized recursively with bounded length.
- Unknown objects are represented by type name.

This keeps debugging useful while preventing submitted Manim source from flooding or leaking through server logs.

## Logging Shape
Use the standard Python `logging` module. Logger name: `app.mcp`.

Success example:

```text
INFO app.mcp: mcp tool invoked tool=append_section status=ok duration_ms=12.34 args=[] kwargs={'session_id': 'abc', 'code': '<redacted code len=42>', 'render': True}
```

Failure example:

```text
ERROR app.mcp: mcp tool failed tool=render_scene status=failed duration_ms=8.91 error_type=ValueError args=[] kwargs={'session_id': 'abc', 'cache': 'bad'}
```

## Alternatives Considered

1. HTTP middleware only: already present and insufficient because it cannot identify MCP tool calls.
2. MCP SDK middleware: possible, but more coupled to SDK request internals and less direct to test.
3. Tool wrapper: selected because `app/mcp.py` already owns the tool map, every tool is covered in one place, and tests can exercise real tool functions without protocol transport setup.

## Testing
Add focused tests in `tests/test_mcp.py` using `caplog`:

1. Successful MCP tool invocation emits `app.mcp` log with tool name, `status=ok`, and `duration_ms`.
2. Failed MCP tool invocation emits exception log with tool name, `status=failed`, `error_type`, and `duration_ms`.
3. `append_section` logging redacts the `code` argument while preserving a code length summary.

Tests use existing `SessionService`, `SessionStore`, and `FakeRenderer` helpers. No mocks are introduced.

## Non-Goals

- Do not change MCP tool names, parameters, descriptions, or response schemas.
- Do not add request IDs, telemetry export, structured JSON logging, or config toggles.
- Do not change REST route logging.
- Do not log full Manim code bodies.
