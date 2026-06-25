import subprocess
from pathlib import Path


def test_ci_installs_make_before_running_make_test():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    install_make = workflow.index("apt-get install -y make")
    run_tests = workflow.index("run: make test")

    assert install_make < run_tests


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
