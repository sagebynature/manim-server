from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_TEMPLATE_ID: str = "default"


@dataclass(frozen=True)
class TemplateAsset:
    templateId: str
    code: str


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

    @staticmethod
    def _safe_id(template_id: str | None) -> bool:
        return bool(template_id) and template_id.replace("-", "_").isidentifier()
