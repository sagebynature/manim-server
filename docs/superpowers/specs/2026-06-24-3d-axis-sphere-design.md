# 3D Axis Sphere Scene Design

## Goal
Render one Manim scene showing 3D axes with a translucent sphere centered at the origin.

## Design
- Create a new Manim MCP session.
- Add `ThreeDAxes` with equal scale on x/y/z.
- Add a blue translucent `Sphere` at the origin.
- Set a 3D camera angle so all axes and the sphere are visible.
- Add a short ambient camera orbit.
- Render once and return the video URL.

## Scope
No labels, legends, textures, or extra geometry. Add those only if requested.

## Verification
Rendering succeeds and the Manim MCP server returns a video URL.