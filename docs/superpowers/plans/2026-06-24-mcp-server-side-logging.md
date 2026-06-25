# MCP Server-Side Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add server-side logs for MCP tool invocations with sanitized request data, outcomes, duration, and failure details.

**Architecture:** Keep logging at the MCP tool boundary in `app/mcp.py`. Wrap the functions returned by `create_tool_functions` so direct tests and mounted FastMCP routes share the same behavior. Use standard Python logging and bounded argument sanitization.

**Tech Stack:** Python 3.11, FastAPI, MCP Python SDK FastMCP, pytest `caplog`, standard library `logging`, `inspect.signature`, `time.perf_counter`, `functools.wraps`.

## Global Constraints

- Log sanitized values, not full raw arguments.
- Always redact the `code` argument as `<redacted code len=N>`.
- Log tool name, sanitized arguments, status, duration in milliseconds, and error type on failure.
- Re-raise exceptions unchanged.
- Do not change MCP tool names, parameters, descriptions, or response schemas.
- Do not add request IDs, telemetry export, structured JSON logging, config toggles, or REST route logging changes.
- Follow TDD: write a failing focused test before production changes for each behavior.
- Shell commands must be prefixed with `rtk`.

---

## File Structure

- Modify `tests/test_mcp.py`: add focused `caplog` coverage for success/redaction and failure logging.
- Modify `app/mcp.py`: add logger, sanitizers, wrapper, and apply wrapper to the tool map returned by `create_tool_functions`.

---

### Task 1: Successful tool invocation logging and code redaction

**Files:**
- Modify: `tests/test_mcp.py`
- Modify: `app/mcp.py`

**Interfaces:**
- Consumes: `create_tool_functions(service: SessionService) -> dict[str, Callable[..., Any]]`.
- Produces: wrapped tool functions that preserve existing return values and emit `app.mcp` success logs.

- [ ] **Step 1: Write failing success/redaction test**

Add imports at the top of `tests/test_mcp.py`:

```python
import logging
```

Add this test after `test_mcp_create_session_accepts_template_id`:

```python
def test_mcp_tool_success_logs_sanitized_arguments(tmp_path, caplog):
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), FakeRenderer())
    )
    session = tools["create_session"]("Demo")
    caplog.clear()

    code = "self.play(Create(Circle()))"
    with caplog.at_level(logging.INFO, logger="app.mcp"):
        result = tools["append_section"](session["sessionId"], code, render=True)

    assert result["sessionId"] == session["sessionId"]
    messages = [record.getMessage() for record in caplog.records]
    message = next(
        message for message in messages if "mcp tool invoked" in message
    )
    assert "tool=append_section" in message
    assert "status=ok" in message
    assert "duration_ms=" in message
    assert f"<redacted code len={len(code)}>" in message
    assert code not in message
```

- [ ] **Step 2: Run test and verify it fails**

```bash
rtk uv run pytest tests/test_mcp.py::test_mcp_tool_success_logs_sanitized_arguments -q
```

Expected: FAIL because no `mcp tool invoked` log exists yet.

- [ ] **Step 3: Implement minimal success logging wrapper**

In `app/mcp.py`, add imports:

```python
import logging
from functools import wraps
from inspect import signature
from time import perf_counter
```

Add module constants and helpers after `dump`:

```python
logger = logging.getLogger("app.mcp")
MAX_LOG_STRING = 120
MAX_LOG_ITEMS = 5


def sanitize_log_value(value, *, key: str | None = None):
    if key == "code" and isinstance(value, str):
        return f"<redacted code len={len(value)}>"
    if isinstance(value, str):
        if len(value) <= MAX_LOG_STRING:
            return value
        return f"{value[:MAX_LOG_STRING]}...<truncated len={len(value)}>"
    if isinstance(value, int | float | bool) or value is None:
        return value
    if isinstance(value, dict):
        items = list(value.items())[:MAX_LOG_ITEMS]
        sanitized = {
            str(item_key): sanitize_log_value(item_value, key=str(item_key))
            for item_key, item_value in items
        }
        if len(value) > MAX_LOG_ITEMS:
            sanitized["..."] = f"<truncated items={len(value) - MAX_LOG_ITEMS}>"
        return sanitized
    if isinstance(value, list | tuple):
        items = value[:MAX_LOG_ITEMS]
        sanitized = [sanitize_log_value(item) for item in items]
        if len(value) > MAX_LOG_ITEMS:
            sanitized.append(f"<truncated items={len(value) - MAX_LOG_ITEMS}>")
        return sanitized
    return f"<{type(value).__name__}>"


def sanitize_tool_arguments(func, args, kwargs) -> dict[str, Any]:
    bound = signature(func).bind_partial(*args, **kwargs)
    return {
        name: sanitize_log_value(value, key=name)
        for name, value in bound.arguments.items()
    }


def log_tool_requests(name, func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        start = perf_counter()
        arguments = sanitize_tool_arguments(func, args, kwargs)
        result = func(*args, **kwargs)
        duration_ms = (perf_counter() - start) * 1000
        logger.info(
            "mcp tool invoked tool=%s status=ok duration_ms=%.2f arguments=%s",
            name,
            duration_ms,
            arguments,
        )
        return result

    return wrapped
```

At the end of `create_tool_functions`, replace the direct return with a raw map and wrapper application:

```python
    tools = {
        "create_session": create_session,
        "list_sessions": list_sessions,
        "get_session": get_session,
        "close_session": close_session,
        "append_section": append_section,
        "render_scene": render_scene,
        "reset_session": reset_session,
    }
    return {name: log_tool_requests(name, tool) for name, tool in tools.items()}
```

- [ ] **Step 4: Run test and verify it passes**

```bash
rtk uv run pytest tests/test_mcp.py::test_mcp_tool_success_logs_sanitized_arguments -q
```

Expected: PASS.

- [ ] **Step 5: Run existing MCP tests for regression**

```bash
rtk uv run pytest tests/test_mcp.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit success logging**

```bash
rtk git add app/mcp.py tests/test_mcp.py
rtk git commit -m "feat: log MCP tool invocations"
```

---

### Task 2: Failed tool invocation logging

**Files:**
- Modify: `tests/test_mcp.py`
- Modify: `app/mcp.py`

**Interfaces:**
- Consumes: `log_tool_requests(name, func)` from Task 1.
- Produces: failure logging that includes `status=failed`, `error_type`, and `duration_ms`, then re-raises the original exception.

- [ ] **Step 1: Write failing failure-log test**

Add import at the top of `tests/test_mcp.py`:

```python
import pytest
```

Add this test after `test_mcp_tool_success_logs_sanitized_arguments`:

```python
def test_mcp_tool_failure_logs_error_details(tmp_path, caplog):
    tools = create_tool_functions(
        SessionService(SessionStore(tmp_path), FakeRenderer())
    )

    with caplog.at_level(logging.INFO, logger="app.mcp"):
        with pytest.raises(ValueError):
            tools["render_scene"]("missing-session", cache="invalid")

    messages = [record.getMessage() for record in caplog.records]
    message = next(message for message in messages if "mcp tool failed" in message)
    assert "tool=render_scene" in message
    assert "status=failed" in message
    assert "duration_ms=" in message
    assert "error_type=ValueError" in message
```

- [ ] **Step 2: Run test and verify it fails**

```bash
rtk uv run pytest tests/test_mcp.py::test_mcp_tool_failure_logs_error_details -q
```

Expected: FAIL because `log_tool_requests` does not log exceptions yet.

- [ ] **Step 3: Extend wrapper to log failures**

Replace `log_tool_requests` in `app/mcp.py` with:

```python
def log_tool_requests(name, func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        start = perf_counter()
        arguments = sanitize_tool_arguments(func, args, kwargs)
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000
            logger.exception(
                "mcp tool failed tool=%s status=failed duration_ms=%.2f "
                "error_type=%s arguments=%s",
                name,
                duration_ms,
                type(exc).__name__,
                arguments,
            )
            raise
        duration_ms = (perf_counter() - start) * 1000
        logger.info(
            "mcp tool invoked tool=%s status=ok duration_ms=%.2f arguments=%s",
            name,
            duration_ms,
            arguments,
        )
        return result

    return wrapped
```

- [ ] **Step 4: Run failure test and verify it passes**

```bash
rtk uv run pytest tests/test_mcp.py::test_mcp_tool_failure_logs_error_details -q
```

Expected: PASS.

- [ ] **Step 5: Run focused MCP suite**

```bash
rtk uv run pytest tests/test_mcp.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit failure logging**

```bash
rtk git add app/mcp.py tests/test_mcp.py
rtk git commit -m "feat: log failed MCP tool invocations"
```

---

### Task 3: Final verification

**Files:**
- Modify: none expected.
- Test: `tests/test_mcp.py`, project Python checks.

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: verified branch ready for completion.

- [ ] **Step 1: Run MCP tests**

```bash
rtk uv run pytest tests/test_mcp.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

```bash
rtk uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run lint/type checks if configured**

```bash
rtk uv run ruff check .
rtk uv run ty check
```

Expected: PASS.

- [ ] **Step 4: Inspect final diff summary**

```bash
rtk git status --short
rtk git diff --stat HEAD~2..HEAD
```

Expected: only `app/mcp.py` and `tests/test_mcp.py` changed by implementation commits, plus the already committed design/plan docs if they are part of the branch.
