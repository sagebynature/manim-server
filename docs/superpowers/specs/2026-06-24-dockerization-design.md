# Dockerization Design

## Goal
Dockerize `manim-server` as a full batteries-included image that can run FastAPI, MCP, the Manim CLI, ffmpeg, and common LaTeX-backed Manim scenes without host-level Manim installation.

## Chosen approach
Use the official Manim Community Docker image as the base:

```dockerfile
FROM manimcommunity/manim:v0.20.1
```

Reasons:
- The project lock currently uses Manim `0.20.1`, so pinning `v0.20.1` avoids `stable` tag drift.
- The upstream image already carries the Manim CLI and native rendering stack, including ffmpeg, Cairo/Pango, fonts, and a minimal TeX Live install.
- This keeps the service Dockerfile focused on the FastAPI/MCP server instead of recreating Manim packaging.
- If a scene needs extra TeX packages beyond upstream minimal TeX Live, extend the image later with the specific missing package. Do not preinstall the full TeX universe unless a real scene needs it.

## Artifacts

### Dockerfile
- Base: `manimcommunity/manim:v0.20.1`.
- Install only server/runtime additions not already provided by the Manim image:
  - `uv`
  - any small OS package required by the app server or healthcheck if absent
- Copy `pyproject.toml` and `uv.lock` first for dependency layer caching.
- Install locked runtime dependencies for this service.
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
- `docker-run`: runs the image on `PORT`.
- `docker-smoke`: builds the image, verifies `manim --version`, starts the service, and checks `/health`.

### README
Add Docker build/run instructions and document:
- The image is based on `manimcommunity/manim:v0.20.1`.
- The base image includes the Manim CLI and common native rendering dependencies.
- The base image has minimal TeX Live; install additional TeX packages only when a scene requires them.

## Verification
Before claiming completion:
- Build the Docker image.
- Verify `manim --version` inside the image.
- Run a container and check `/health`.
- Run a simple render smoke inside the image if startup and build time allow it.
- Run Python tests with `uv run python -m pytest -q`.

Known local baseline before Dockerization: local Python tests run, but real-Manim tests fail when host `manim` is missing from PATH. Docker verification must cover the runtime dependency layer.