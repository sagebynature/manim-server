from pathlib import Path


def test_three_d_template_uses_three_d_scene():
    code = Path("template/three-d.py").read_text(encoding="utf-8")

    assert "class GeneratedScene(ThreeDScene):" in code
