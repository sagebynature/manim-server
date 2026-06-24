# manim-server

Python-only FastAPI + MCP service for trusted Manim Community rendering.

## Install

```bash
uv sync --all-groups
```

## Configure

Create `.env` from the example:

```bash
cp .env.example .env
```

Supported keys:

```env
HOST=127.0.0.1
PORT=8000
DATA_DIR=.manim-server-data
MANIM_CLI_FLAGS=-ql
MANIM_TIMEOUT_SECONDS=120
```

Notes:
- `DATA_DIR` stores session JSON logs and rendered MP4 artifacts.
- `MANIM_CLI_FLAGS` is split like a shell command, then passed as subprocess args. Common values: `-ql`, `-qm`, `-qh`, `-ql --fps 30`.
- `--save_sections`, `--media_dir`, cache flags, scene path, and scene class are managed by the server.

## Run

```bash
make run
```

Default server: `http://127.0.0.1:8000`.

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

## REST flow

```bash
curl -s -X POST http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Demo"}'

curl -s -X POST http://127.0.0.1:8000/sessions/<sessionId>/section \
  -H 'content-type: application/json' \
  -d '{"code":"self.add(Circle())\nself.wait(0.5)","render":true}'
```

Open returned `latestRender.fullVideoUrl`, or a section URL such as `/sessions/<sessionId>/sections/0001/video`, in a browser or video client.

## MCP endpoint

`http://127.0.0.1:8000/mcp`

Tools mirror REST: `create_session`, `list_sessions`, `get_session`, `close_session`, `append_section`, `render_scene`, `reset_session`.

## Security

Scene code is trusted Python. Do not expose this server to untrusted users or networks.
