import ast
from pathlib import Path

from app.templates import TemplateStore


def test_all_builtin_templates_have_docstrings():
    template_paths = sorted(Path("template").glob("*.py"))

    assert template_paths
    for path in template_paths:
        module = ast.parse(path.read_text(encoding="utf-8"))
        assert ast.get_docstring(module), f"{path} needs a module docstring"


def test_template_store_lists_docstring_metadata_without_executing_code(tmp_path):
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "alpha.py").write_text(
        "\n".join(
            [
                '"""Alpha template.',
                "",
                "Use for algebra explainers and quick title cards.",
                "Best when the user wants a simple 2D scene.",
                '"""',
                'raise RuntimeError("must not execute")',
            ]
        ),
        encoding="utf-8",
    )
    (template_dir / "bad/name.py").parent.mkdir(exist_ok=True)
    (template_dir / "bad/name.py").write_text('"""Ignored nested template."""', encoding="utf-8")

    templates = TemplateStore(template_dir).list_templates()

    assert [template.templateId for template in templates] == ["alpha"]
    assert templates[0].description == "Alpha template."
    assert templates[0].useCases == (
        "Use for algebra explainers and quick title cards. "
        "Best when the user wants a simple 2D scene."
    )
