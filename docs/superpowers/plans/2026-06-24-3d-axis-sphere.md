# 3D Axis Sphere Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render one Manim scene showing 3D axes with a translucent sphere centered at the origin.

**Architecture:** Use the Manim MCP server directly. Create one session, append one scene-body section, render once.

**Tech Stack:** Manim MCP server, Manim `ThreeDAxes`, `Sphere`, 3D camera controls.

## Global Constraints

- No labels, legends, textures, or extra geometry.
- Add a short ambient camera orbit.
- Return the video URL after render.

---

### Task 1: Render 3D axes and sphere

**Files:**
- Create: MCP session `3d-axis-sphere`
- Modify: none
- Test: MCP render result

**Interfaces:**
- Consumes: Manim scene-body code executed inside the generated `Scene.construct` method.
- Produces: A rendered video URL from the Manim MCP server.

- [ ] **Step 1: Create a Manim MCP session**

Create a new session titled `3D Axis Sphere`.

- [ ] **Step 2: Append the scene body**

```python
self.set_camera_orientation(phi=65 * DEGREES, theta=35 * DEGREES, zoom=0.9)
axes = ThreeDAxes(
    x_range=[-3, 3, 1],
    y_range=[-3, 3, 1],
    z_range=[-3, 3, 1],
    x_length=5,
    y_length=5,
    z_length=5,
)
sphere = Sphere(radius=1.2, resolution=(32, 16))
sphere.set_fill(BLUE, opacity=0.45)
sphere.set_stroke(WHITE, opacity=0.35, width=1)
self.add(axes, sphere)
self.begin_ambient_camera_rotation(rate=0.25)
self.wait(4)
self.stop_ambient_camera_rotation()
```

- [ ] **Step 3: Render the scene**

Run the Manim MCP render for the session.

Expected: render succeeds and returns `fullVideoUrl`.

- [ ] **Step 4: Report result**

Return the session id and video URL.