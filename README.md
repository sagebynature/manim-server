<div align="center">

  # manim-server

  FastAPI + MCP server for trusted Manim script rendering. (uses [Manim Community](https://www.manim.community/))
  <video src="https://github.com/user-attachments/assets/9be7e5de-c89a-4c5a-9b6e-2852ae104acf" controls="controls" muted="muted" class="d-block rounded-bottom-2 border-top width-fit" style="max-height:480px; min-height: 200px">
  </video>
</div>



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

The example builds one session from five Manim snippets, renders the final scene,
then downloads the MP4. Use `Manim-Session-ID` when you want a stable id; omit it
to let the server generate one.

```bash
# POST /sessions creates a new scene session.
# Response includes sessionId, title, sectionCount, and an empty section log.
curl -sS -X POST http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -H 'Manim-Session-ID: five-section-demo' \
  -d '{"title":"Five animated sections curl smoke"}'

# POST /sessions/<sessionId>/section appends one Manim code section.
# render=false records code without invoking Manim; cache is ignored until rendering.
curl -sS -X POST http://127.0.0.1:8000/sessions/five-section-demo/section \
  -H 'content-type: application/json' \
  -d '{"title":"Create blue circle","code":"circle = Circle(color=BLUE)\nself.play(Create(circle), run_time=1.0)","render":false}'

# Another section. Sections run in append order inside the generated scene.
curl -sS -X POST http://127.0.0.1:8000/sessions/five-section-demo/section \
  -H 'content-type: application/json' \
  -d '{"title":"Create green square","code":"square = Square(color=GREEN).shift(RIGHT * 2)\nself.play(Create(square), run_time=1.0)","render":false}'

# Adds a third shape, still only updating the session JSON log.
curl -sS -X POST http://127.0.0.1:8000/sessions/five-section-demo/section \
  -H 'content-type: application/json' \
  -d '{"title":"Create yellow triangle","code":"triangle = Triangle(color=YELLOW).shift(LEFT * 2)\nself.play(Create(triangle), run_time=1.0)","render":false}'

# Adds a fourth animation section.
curl -sS -X POST http://127.0.0.1:8000/sessions/five-section-demo/section \
  -H 'content-type: application/json' \
  -d '{"title":"Create lower line","code":"line = Line(LEFT, RIGHT, color=RED).shift(DOWN * 1.5)\nself.play(Create(line), run_time=1.0)","render":false}'

# Final section render=true appends code and runs Manim. cache defaults to "use",
# so omitting it lets Manim reuse existing cached partial movie files.
curl -sS -X POST http://127.0.0.1:8000/sessions/five-section-demo/section \
  -H 'content-type: application/json' \
  -d '{"title":"Create purple ellipse","code":"ellipse = Ellipse(width=3, height=1.5, color=PURPLE).shift(UP * 1.5)\nself.play(Create(ellipse), run_time=1.0)\nself.wait(0.1)","render":true}'

# GET /sessions/<sessionId>/video downloads the full MP4 from the latest render.
curl -sS -o /tmp/five-sections-full.mp4 \
  -w 'status=%{http_code} content_type=%{content_type} bytes=%{size_download}\n' \
  http://127.0.0.1:8000/sessions/five-section-demo/video
```

Open returned `latestRender.fullVideoUrl`, or a section URL such as
`/sessions/five-section-demo/sections/0001/video`, in a browser or video client.

Cache modes for `append_section` with `render=true`, and for `render_scene`:

- Omit `cache`, or set `"cache":"use"`: default; let Manim reuse cache.
- `"cache":"flush"`: delete Manim partial movie cache before rendering.
- `"cache":"disable"`: pass `--disable_caching` to Manim for that render.

## Session templates

`POST /sessions` accepts optional `templateId`:

```bash
curl -sS -X POST http://127.0.0.1:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Lecture","templateId":"lecture"}'
```

Template assets are Python files under
`DATA_DIR/assets/session-templates/<templateId>.py`. Unknown or missing templates
fall back to `default.py`; if `default.py` is absent, the server uses its
built-in title-header template.

Template files are full Manim scripts, not scene-body snippets. Keep the scene
class named `GeneratedScene`; Manim renders that class, and user sections are
appended at EOF at the `construct()` body indentation. Do not put dedented code
after `construct()` that would close that append point.

The reserved string literals `"__SESSION_ID__"`, `"__SESSION_TITLE__"`, and
`"__TEMPLATE_ID__"` are replaced before render. Include them where the template
needs those values:

```python
from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled").to_edge(UP)
        self.add(title)

        # user sections append here
```

## MCP endpoint

`http://127.0.0.1:8000/mcp`

Tools mirror REST: `create_session`, `list_sessions`, `get_session`, `close_session`, `append_section`, `render_scene`, `reset_session`.

## Thanks

Special thanks to the [Manim Community](https://www.manim.community/) and
[3Blue1Brown](https://github.com/3b1b) for their amazing work and inspiration.

## Security

Scene code is trusted Python. Do not expose this server to untrusted users or networks.
