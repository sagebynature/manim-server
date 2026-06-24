# Dockerization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dockerize `manim-server` using the official Manim Community image as the base and push the finished changes.

**Architecture:** Build one service image from `manimcommunity/manim:v0.20.1`, matching the locked Manim `0.20.1` dependency. The Dockerfile adds only this FastAPI/MCP server on top of the upstream Manim CLI/native rendering stack, then runs `uvicorn` on port `8000` with `/data` as the persisted render/session directory.

**Tech Stack:** Docker, `manimcommunity/manim:v0.20.1`, Python packaging via `uv`/pip-compatible `pyproject.toml`, FastAPI/Uvicorn, Makefile.

## Global Constraints

- Keep the image based on `manimcommunity/manim:v0.20.1`; do not rebuild ffmpeg, Cairo/Pango, fonts, or TeX Live from `python:slim`.
- Do not add new Python runtime dependencies.
- Keep Docker additions minimal: `Dockerfile`, `.dockerignore`, Makefile targets, README Docker section.
- Container defaults: `HOST=0.0.0.0`, `PORT=8000`, `DATA_DIR=/data`, `MANIM_CLI_FLAGS=-ql`, `MANIM_TIMEOUT_SECONDS=120`.
- Verification must include `manim --version` inside the built image and `/health` from a running container.

---

### Task 1: Docker smoke target before image exists

**Files:**
- Modify: `Makefile`

**Interfaces:**
- Produces Make targets later used by verification: `docker-build`, `docker-smoke`.

- [ ] **Step 1: Add Docker variables and smoke target**

Add these Makefile variables near existing variables:

```make
IMAGE ?= manim-server
CONTAINER ?= manim-server-smoke
```

Add these phony targets:

```make
.PHONY: docker-build docker-run docker-smoke

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	docker run --rm -p $(PORT):8000 -e DATA_DIR=/data $(IMAGE)

docker-smoke: docker-build
	docker rm -f $(CONTAINER) >/dev/null 2>&1 || true
	docker run --rm $(IMAGE) manim --version
	docker run --rm -d --name $(CONTAINER) -p $(PORT):8000 $(IMAGE)
	sleep 5
	curl -fsS http://127.0.0.1:$(PORT)/health
	docker rm -f $(CONTAINER) >/dev/null
```

- [ ] **Step 2: Run smoke and verify RED**

Run:

```bash
rtk make docker-smoke
```

Expected: FAIL because `Dockerfile` does not exist yet.

- [ ] **Step 3: Commit the failing Docker target**

```bash
rtk git add Makefile
rtk git commit -m "build: add docker smoke target"
```

---

### Task 2: Docker image artifacts

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: Make targets from Task 1.
- Produces: Docker image that runs `uvicorn app.main:app` and has `manim` on PATH.

- [ ] **Step 1: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM manimcommunity/manim:v0.20.1

USER root
WORKDIR /app

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/data \
    MANIM_CLI_FLAGS=-ql \
    MANIM_TIMEOUT_SECONDS=120 \
    PATH=/opt/venv/bin:/usr/local/texlive/bin/aarch64-linux:/usr/local/texlive/bin/x86_64-linux:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

COPY pyproject.toml uv.lock ./
RUN python -m pip install --no-cache-dir uv \
    && uv pip install --no-cache .

COPY app ./app

RUN mkdir -p /data && chown -R manimuser:manimuser /data /app

USER manimuser
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json, urllib.request; json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2))['ok']"

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
```

- [ ] **Step 2: Create .dockerignore**

Create `.dockerignore`:

```gitignore
.git/
.venv/
.serena/
.pytest_cache/
__pycache__/
*.py[cod]
.manim-server-data/
dist/
*.egg-info/
.env
```

- [ ] **Step 3: Run smoke and verify GREEN**

Run:

```bash
rtk make docker-smoke
```

Expected: image builds, `manim --version` prints `Manim Community v0.20.1`, and `/health` returns `{"ok":true}`.

- [ ] **Step 4: Commit Docker artifacts**

```bash
rtk git add Dockerfile .dockerignore
rtk git commit -m "build: add docker image"
```

---

### Task 3: Docker documentation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Make targets and image behavior from Tasks 1-2.
- Produces: user-facing Docker build/run instructions.

- [ ] **Step 1: Add README Docker section**

Append after the existing Run section:

```markdown
## Docker

Build the image:

```bash
make docker-build
```

Run it on `http://127.0.0.1:8000`:

```bash
make docker-run
```

Smoke-test the image:

```bash
make docker-smoke
```

The image is based on `manimcommunity/manim:v0.20.1`, matching the locked Manim dependency. That base image provides the Manim CLI plus common native rendering dependencies such as ffmpeg, Cairo/Pango, fonts, and minimal TeX Live. If a scene needs an extra TeX package, extend the image with that specific package instead of preinstalling all of TeX Live.
```

- [ ] **Step 2: Commit README update**

```bash
rtk git add README.md
rtk git commit -m "docs: add docker usage"
```

---

### Task 4: Final verification and push

**Files:**
- No planned edits.

**Interfaces:**
- Consumes: Docker image, Makefile targets, README docs.
- Produces: pushed branch on `origin/main` unless repository rejects direct push.

- [ ] **Step 1: Run Docker smoke**

```bash
rtk make docker-smoke
```

Expected: image builds, Manim version prints, `/health` returns `{"ok":true}`.

- [ ] **Step 2: Run Python tests**

```bash
rtk uv run python -m pytest -q
```

Expected locally: tests may still fail if host `manim` is missing from PATH. If so, report the exact failing tests and rely on Docker smoke for the Manim runtime layer. Do not claim local full-test pass unless output is green.

- [ ] **Step 3: Run typecheck**

```bash
rtk make typecheck
```

Expected: typecheck exits 0.

- [ ] **Step 4: Push commits**

```bash
rtk git status --short --branch
rtk git push origin main
```

Expected: branch pushes to `origin/main`.
