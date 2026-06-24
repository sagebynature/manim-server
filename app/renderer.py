from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from app.models import Section, RenderCacheMode, RenderSummary, SectionArtifact
from app.templates import DEFAULT_TEMPLATE_ID, DEFAULT_TEMPLATE_SCRIPT


class RenderError(RuntimeError):
    pass


def build_scene_script(
    sections: Sequence[Section],
    template_code: str = DEFAULT_TEMPLATE_SCRIPT,
    session_id: str = "",
    session_title: str | None = None,
    template_id: str = DEFAULT_TEMPLATE_ID,
) -> str:
    script = (
        template_code.replace('"__SESSION_ID__"', repr(session_id))
        .replace('"__SESSION_TITLE__"', repr(session_title))
        .replace('"__TEMPLATE_ID__"', repr(template_id))
        .rstrip()
    )
    lines = script.splitlines()

    if not sections:
        lines.append("        self.wait(0.1)")
        return "\n".join(lines) + "\n"
    for section in sections:
        if not section.code.strip():
            raise ValueError("section code is empty")
        if section.title is not None:
            for title_line in section.title.splitlines() or [""]:
                lines.append(f"        # {title_line}")
        lines.append(f"        self.next_section({section.sectionId!r})")
        lines.extend(
            f"        {line}" if line.strip() else ""
            for line in section.code.strip("\n").splitlines()
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
        self,
        session_id: str,
        sections: list[Section],
        cache: RenderCacheMode,
        template_code: str = DEFAULT_TEMPLATE_SCRIPT,
        session_title: str | None = None,
        template_id: str = DEFAULT_TEMPLATE_ID,
    ) -> RenderSummary:
        session_dir = self.session_dir(session_id)
        media_dir = self.media_dir(session_id)
        render_dir = self.render_dir(session_id)
        scene_path = session_dir / "scene.py"
        session_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(render_dir, ignore_errors=True)
        render_dir.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(
            build_scene_script(
                sections,
                template_code=template_code,
                session_id=session_id,
                session_title=session_title,
                template_id=template_id,
            ),
            encoding="utf-8",
        )

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
        artifacts = self._copy_sections(
            session_id, sections, output_dir / "sections", render_dir / "sections"
        )
        return RenderSummary(
            fullVideoUrl=f"/sessions/{session_id}/video", sections=artifacts
        )

    def _copy_sections(
        self,
        session_id: str,
        sections: list[Section],
        source_dir: Path,
        target_dir: Path,
    ) -> list[SectionArtifact]:
        metadata_path = source_dir / "GeneratedScene.json"
        if not metadata_path.exists():
            return []
        target_dir.mkdir(parents=True, exist_ok=True)
        wanted = {section.sectionId: section.sectionId for section in sections}
        artifacts: list[SectionArtifact] = []
        for item in json.loads(metadata_path.read_text(encoding="utf-8")):
            section_id = wanted.get(item.get("name"))
            if section_id is None:
                continue
            shutil.copy2(source_dir / item["video"], target_dir / f"{section_id}.mp4")
            duration = float(item["duration"]) if item.get("duration") else None
            artifacts.append(
                SectionArtifact(
                    sectionId=section_id,
                    videoUrl=f"/sessions/{session_id}/sections/{section_id}/video",
                    duration=duration,
                    metadata=item,
                )
            )
        return artifacts
