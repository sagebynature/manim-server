# MCP Tool Descriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve MCP client tool selection by making existing Manim MCP tool descriptions actionable.

**Architecture:** Keep FastMCP tool functions as the source of MCP metadata. Change only docstrings in `app/mcp.py` and add a focused regression test that inspects the descriptions exposed by the MCP server/tool manager or, if public metadata is unavailable, the wrapper source docstrings.

**Tech Stack:** Python 3.11+, FastMCP from `mcp`, pytest, existing `SessionService` test fakes.

## Global Constraints

- Do not rename tools, parameters, or response fields.
- Do not change rendering, session, or cache behavior.
- Use docstrings only for descriptions.
- Give `append_operation` extra guidance on incremental usage, trusted Manim code, render batching, and cache modes.
- No new dependencies.

---

### Task 1: Description Regression Test

**Files:**
- Modify: `tests/test_mcp.py`

**Interfaces:**
- Consumes: `create_mcp_server(service: SessionService) -> FastMCP`
- Produces: tests that fail while MCP descriptions are terse and pass once descriptions include client guidance.

- [ ] **Step 1: Write failing test**

Add a test that creates the MCP server and asserts descriptions contain client-action guidance, especially for `append_operation`.

```python
def test_mcp_tool_descriptions_guide_clients(tmp_path):
    mcp = create_mcp_server(SessionService(SessionStore(tmp_path), FakeRenderer()))
    tools = mcp._tool_manager._tools

    assert "Start here" in tools["create_session"].description
    assert "Use this before append_operation" in tools["create_session"].description

    append_description = tools["append_operation"].description
    assert "trusted Python Manim scene-body code" in append_description
    assert "append one logical animation step" in append_description
    assert "render=False" in append_description
    assert "render=True" in append_description
    assert "cache" in append_description
    assert "use" in append_description
    assert "refresh" in append_description
    assert "disable" in append_description
```

- [ ] **Step 2: Run test verify fails**

Run:

```bash
rtk uv run pytest tests/test_mcp.py::test_mcp_tool_descriptions_guide_clients -q
```

Expected: FAIL because existing descriptions are terse and do not contain these phrases.

---

### Task 2: Tool Docstrings

**Files:**
- Modify: `app/mcp.py`
- Test: `tests/test_mcp.py`

**Interfaces:**
- Consumes: FastMCP deriving tool descriptions from function docstrings.
- Produces: detailed descriptions for `create_session`, `list_sessions`, `get_session`, `close_session`, `append_operation`, `render_scene`, and `reset_session`.

- [ ] **Step 1: Implement minimal docstring changes**

Replace only the nested MCP tool docstrings in `create_mcp_server`. Keep function signatures and return statements unchanged.

- [ ] **Step 2: Run focused test verify passes**

Run:

```bash
rtk uv run pytest tests/test_mcp.py::test_mcp_tool_descriptions_guide_clients -q
```

Expected: PASS.

- [ ] **Step 3: Run MCP tests**

Run:

```bash
rtk uv run pytest tests/test_mcp.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit implementation**

Run:

```bash
rtk git add app/mcp.py tests/test_mcp.py docs/superpowers/plans/2026-06-24-mcp-tool-descriptions.md
rtk git commit -m "feat: improve mcp tool descriptions"
```
