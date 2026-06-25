from pathlib import Path


def test_ci_installs_manim_build_dependencies_before_sync():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    install_deps = workflow.index("libpango1.0-dev")
    run_sync = workflow.index("make sync test")

    assert install_deps < run_sync
    assert "build-essential" in workflow
    assert "python3-dev" in workflow
    assert "pkg-config" in workflow
    assert "libcairo2-dev" in workflow
