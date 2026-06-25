from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TEMPLATE_ID: str = "default"


@dataclass(frozen=True)
class TemplateAsset:
    templateId: str
    code: str


@dataclass(frozen=True)
class TemplateSummary:
    templateId: str
    description: str
    useCases: str


class TemplateStore:
    def __init__(self, template_dir: Path):
        self.templates_dir = template_dir

    def resolve(self, template_id: str | None) -> TemplateAsset:
        if template_id is None or not self._safe_id(template_id):
            template_id = DEFAULT_TEMPLATE_ID

        path = self.templates_dir / f"{template_id}.py"
        if path.exists():
            return TemplateAsset(template_id, path.read_text(encoding="utf-8"))

        default_path = self.templates_dir / f"{DEFAULT_TEMPLATE_ID}.py"
        if default_path.exists():
            return TemplateAsset(
                DEFAULT_TEMPLATE_ID, default_path.read_text(encoding="utf-8")
            )

        raise FileNotFoundError(f"missing default template: {default_path}")

    def list_templates(self) -> list[TemplateSummary]:
        if not self.templates_dir.exists():
            return []

        summaries = []
        for path in sorted(self.templates_dir.glob("*.py")):
            template_id = path.stem
            if not self._safe_id(template_id):
                continue
            summaries.append(self._summarize(template_id, path))
        return summaries

    def _summarize(self, template_id: str, path: Path) -> TemplateSummary:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring = ast.get_docstring(module) or ""
        lines = [line.strip() for line in docstring.splitlines() if line.strip()]
        description = lines[0] if lines else ""
        use_cases = " ".join(lines[1:])
        return TemplateSummary(template_id, description, use_cases)

    @staticmethod
    def _safe_id(template_id: str | None) -> bool:
        return bool(template_id) and template_id.replace("-", "_").isidentifier()
