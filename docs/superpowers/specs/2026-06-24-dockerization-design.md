# Dockerization Design

## Goal
Dockerize `manim-server` as a full batteries-included image that can run FastAPI, MCP, the Manim CLI, ffmpeg, and common LaTeX-backed Manim scenes without host-level Manim installation.

## Chosen approach
Use a Debian-based `python:3.11-slim` runtime image rather than an upstream Manim image or a lean app-only image.

Reasons:
- Matches the service runtime: Python FastAPI app that shells out to `manim`.
- Keeps native dependencies explicit and reviewable.
- Supports common Manim rendering paths, including ffmpeg and TeX scenes.
- Avoids inheriting unknown entrypoints or dependency policy from an upstream image.

## Artifacts

### Dockerfile
- Base: `python:3.11-slim`.
- Install system packages needed by Manim and rendering:
  - video: `ffmpeg`
  - Cairo/Pango stack and build support for Python wheels/native deps
  - LaTeX and SVG helpers: TeX Live packages and `dvisvgm`
  - fonts used by common scenes
- Install `uv`.
- Copy `pyproject.toml` and `uv.lock` first for dependency layer caching.
- Install locked runtime dependencies into the system Python environment.
- Copy `app/` and project metadata.
- Configure defaults:
  - `HOST=0.0.0.0`
  - `PORT=8000`
  - `DATA_DIR=/data`
  - `MANIM_CLI_FLAGS=-ql`
  - `MANIM_TIMEOUT_SECONDS=120`
- Create `/data` for persisted session JSON and MP4 artifacts.
- Expose port `8000`.
- Run `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Healthcheck `/health`.

### .dockerignore
Exclude local-only and bulky inputs:
- `.git/`
- `.venv/`
- `.serena/`
- `.pytest_cache/`
- `__pycache__/`
- `.manim-server-data/`
- build/dist metadata
- local `.env`

### Makefile
Add:
- `docker-build`: builds the image.
- `docker-run`: runs the image on `PORT`, mounting or creating `/data` via Docker defaults if needed.

### README
Add Docker build/run instructions and document that the image includes Manim CLI native dependencies, ffmpeg, LaTeX, and fonts.

## Verification
Before claiming completion:
- Build the Docker image.
- Run a container and check `/health`.
- Verify `manim --version` inside the image.
- Run Python tests with `uv run python -m pytest -q`.

Known local baseline before Dockerization: local Python tests run, but real-Manim tests fail when host `manim` is missing from PATH. Docker verification must cover the runtime dependency layer.