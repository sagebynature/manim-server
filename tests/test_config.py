from pathlib import Path


from app.config import load_settings


def test_load_settings_from_environment(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", "data")
    monkeypatch.setenv("MANIM_CLI_FLAGS", "-qm --fps 30")
    monkeypatch.setenv("MANIM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("TEMPLATE_DIR", "templates")

    settings = load_settings()

    assert settings.data_dir == (tmp_path / "data").resolve()
    assert settings.template_dir == (tmp_path / "templates").resolve()
    assert settings.manim_cli_flags == ["-qm", "--fps", "30"]
    assert settings.manim_timeout_seconds == 45


def test_load_settings_defaults(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("MANIM_CLI_FLAGS", raising=False)
    monkeypatch.delenv("MANIM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("TEMPLATE_DIR", raising=False)

    settings = load_settings()

    assert settings.data_dir == Path(".manim-server-data").resolve()
    assert settings.template_dir == Path("template").resolve()
    assert settings.manim_cli_flags == ["-ql"]
    assert settings.manim_timeout_seconds == 120
