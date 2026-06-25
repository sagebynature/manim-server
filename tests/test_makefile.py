import subprocess
from pathlib import Path


def test_ci_installs_make_before_pytest_uses_makefile_tests():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    install_make = workflow.index("apt-get install -y make")
    run_pytest = workflow.index("run: /opt/venv/bin/pytest -q")

    assert install_make < run_pytest


def test_ci_uses_prebuilt_manim_virtualenv():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "run: make test" not in workflow
    assert "uv pip install --python /opt/venv/bin/python -e . --group dev" in workflow
    assert "run: /opt/venv/bin/ruff check app tests" in workflow
    assert "run: /opt/venv/bin/ruff format --check app tests" in workflow
    assert (
        "run: /opt/venv/bin/ty check --python /opt/venv/bin/python app tests"
        in workflow
    )
    assert "run: /opt/venv/bin/pytest -q" in workflow


def test_docker_run_restarts_named_container_before_starting():
    result = subprocess.run(
        ["make", "-n", "docker-run"],
        check=True,
        capture_output=True,
        text=True,
    )
    commands = result.stdout.splitlines()

    rm_index = next(
        (
            i
            for i, command in enumerate(commands)
            if "docker rm -f manim-server" in command
        ),
        None,
    )
    run_index = next(
        (i for i, command in enumerate(commands) if command.startswith("docker run ")),
        None,
    )

    assert rm_index is not None
    assert run_index is not None
    assert rm_index < run_index
    assert "|| true" in commands[rm_index]
    assert "--name manim-server" in commands[run_index]
