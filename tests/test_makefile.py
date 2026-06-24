import subprocess


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
