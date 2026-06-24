import os
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    template_dir: Path
    manim_cli_flags: list[str]
    manim_timeout_seconds: int


def load_settings() -> Settings:
    return Settings(
        # codeql[py/path-injection]
        data_dir=Path(os.getenv("DATA_DIR", ".manim-server-data")).resolve(),
        # codeql[py/path-injection]
        template_dir=Path(os.getenv("TEMPLATE_DIR", "template")).resolve(),
        manim_cli_flags=shlex.split(os.getenv("MANIM_CLI_FLAGS", "-ql")),
        manim_timeout_seconds=int(os.getenv("MANIM_TIMEOUT_SECONDS", "120")),
    )
