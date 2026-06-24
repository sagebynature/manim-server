import json
import shutil
from pathlib import Path

import pytest

from app.models import RenderCacheMode, Section
from app.renderer import ManimRenderer, build_scene_script


def op(section_id: str, code: str) -> Section:
    return Section(sectionId=section_id, code=code, createdAt="now")


def test_build_scene_script_adds_section_title_comment():
    script = build_scene_script(
        [
            Section(
                sectionId="0001", title="Intro", code="self.wait(0.1)", createdAt="now"
            )
        ]
    )

    assert (
        "        # Intro\n        self.next_section('0001')\n        self.wait(0.1)"
        in script
    )


def test_build_scene_script_names_sections_before_sections():
    script = build_scene_script(
        [op("0001", "self.add(Circle())"), op("0002", "self.wait(1)")]
    )

    assert "self.next_section('0001')\n        self.add(Circle())" in script
    assert "self.next_section('0002')\n        self.wait(1)" in script


def test_renderer_copies_full_video_and_named_sections(tmp_path: Path, monkeypatch):
    renderer = ManimRenderer(tmp_path, cli_flags=["-qm", "--fps", "30"])
    seen_command = None

    def fake_run(command, cwd, capture_output, text, timeout, check):
        nonlocal seen_command
        seen_command = command
        media_dir = Path(command[command.index("--media_dir") + 1])
        output = media_dir / "videos" / "scene" / "720p30"
        sections = output / "sections"
        sections.mkdir(parents=True)
        (output / "GeneratedScene.mp4").write_bytes(b"full")
        (sections / "GeneratedScene_0000.mp4").write_bytes(b"section")
        (sections / "GeneratedScene.json").write_text(
            json.dumps(
                [
                    {
                        "name": "0001",
                        "video": "GeneratedScene_0000.mp4",
                        "duration": "1.0",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)
    stale = tmp_path / "sessions" / "s1" / "render" / "sections" / "stale.mp4"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")

    summary = renderer.render("s1", [op("0001", "self.wait(1)")], RenderCacheMode.USE)

    assert seen_command is not None
    assert seen_command[:6] == [
        "manim",
        "--save_sections",
        "-qm",
        "--fps",
        "30",
        "--media_dir",
    ]
    assert (
        tmp_path / "sessions" / "s1" / "render" / "GeneratedScene.mp4"
    ).read_bytes() == b"full"
    assert not stale.exists()
    assert summary.fullVideoUrl == "/sessions/s1/video"
    assert summary.sections[0].sectionId == "0001"
    assert summary.sections[0].videoUrl == "/sessions/s1/sections/0001/video"


@pytest.mark.skipif(shutil.which("manim") is None, reason="manim CLI not installed")
def test_real_manim_sections_are_named_by_section_id(tmp_path: Path):
    renderer = ManimRenderer(tmp_path)

    summary = renderer.render(
        "s1",
        [op("0001", "self.add(Circle())\nself.wait(0.1)")],
        RenderCacheMode.DISABLE,
    )

    assert (tmp_path / "sessions" / "s1" / "render" / "GeneratedScene.mp4").exists()
    assert [section.sectionId for section in summary.sections] == ["0001"]
