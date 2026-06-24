from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from app.models import Operation, RenderCacheMode, RenderSummary, SectionArtifact


class RenderError(RuntimeError):
    pass


def build_scene_script(operations: Sequence[Operation]) -> str:
    lines = [
        "from manim import *",
        "from manim.opengl import *",
        "",
        "",
        "class GeneratedScene(Scene):",
        "    def construct(self):",
    ]
    if not operations:
        lines.append("        self.wait(0.1)")
        return "\n".join(lines) + "\n"
    for operation in operations:
        if not operation.code.strip():
            raise ValueError("operation code is empty")
        lines.append(f"        self.next_section({operation.sectionName!r})")
        lines.extend(
            f"        {line}" if line.strip() else ""
            for line in operation.code.strip("\n").splitlines()
        )
    return "\n".join(lines) + "\n"


class ManimRenderer:
    def __init__(
        self,
        data_dir: Path,
        cli_flags: list[str] | None = None,
        timeout_seconds: int = 120,
    ):
        self.data_dir = data_dir
        self.cli_flags = cli_flags or ["-ql"]
        self.timeout_seconds = timeout_seconds

    def session_dir(self, session_id: str) -> Path:
        return self.data_dir / "sessions" / session_id

    def render_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "render"

    def media_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "media"

    def render(
        self, session_id: str, operations: list[Operation], cache: RenderCacheMode
    ) -> RenderSummary:
        session_dir = self.session_dir(session_id)
        media_dir = self.media_dir(session_id)
        render_dir = self.render_dir(session_id)
        scene_path = session_dir / "scene.py"
        session_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(render_dir, ignore_errors=True)
        render_dir.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(build_scene_script(operations), encoding="utf-8")

        if cache == RenderCacheMode.FLUSH:
            shutil.rmtree(
                media_dir / "videos" / "scene" / "480p15" / "partial_movie_files",
                ignore_errors=True,
            )

        command = [
            "manim",
            "--save_sections",
            *self.cli_flags,
            "--media_dir",
            str(media_dir),
        ]
        if cache == RenderCacheMode.DISABLE:
            command.append("--disable_caching")
        command.extend([str(scene_path), "GeneratedScene"])

        completed = subprocess.run(
            command,
            cwd=session_dir,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RenderError(
                (completed.stderr or completed.stdout or "Manim render failed").strip()
            )

        matches = sorted((media_dir / "videos" / "scene").glob("*/GeneratedScene.mp4"))
        if not matches:
            raise RenderError(
                f"Manim did not produce expected video under: {media_dir / 'videos' / 'scene'}"
            )
        full_video = matches[-1]
        output_dir = full_video.parent

        shutil.copy2(full_video, render_dir / "GeneratedScene.mp4")
        sections = self._copy_sections(
            session_id, operations, output_dir / "sections", render_dir / "sections"
        )
        return RenderSummary(
            fullVideoUrl=f"/sessions/{session_id}/video", sections=sections
        )

    def _copy_sections(
        self,
        session_id: str,
        operations: list[Operation],
        source_dir: Path,
        target_dir: Path,
    ) -> list[SectionArtifact]:
        metadata_path = source_dir / "GeneratedScene.json"
        if not metadata_path.exists():
            return []
        target_dir.mkdir(parents=True, exist_ok=True)
        wanted = {
            operation.sectionName: operation.operationId for operation in operations
        }
        artifacts: list[SectionArtifact] = []
        for item in json.loads(metadata_path.read_text(encoding="utf-8")):
            operation_id = wanted.get(item.get("name"))
            if operation_id is None:
                continue
            shutil.copy2(source_dir / item["video"], target_dir / f"{operation_id}.mp4")
            duration = float(item["duration"]) if item.get("duration") else None
            artifacts.append(
                SectionArtifact(
                    operationId=operation_id,
                    videoUrl=f"/sessions/{session_id}/sections/{operation_id}/video",
                    duration=duration,
                    metadata=item,
                )
            )
        return artifacts
