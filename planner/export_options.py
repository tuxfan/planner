from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import runpy

import yaml

from .models import ValidationError


DEFAULT_TASK_TABLE_ATTRIBUTES = ("bnr", "cost", "funding_status", "type")
TASK_TABLE_ATTRIBUTE_ALIASES = {
    "bnr": "bnr",
    "cost": "cost",
    "funding": "funding_status",
    "funding_status": "funding_status",
    "type": "type",
    "tags": "tags",
}
TASK_TABLE_OPTION_KEYS = ("task_table_attributes", "task_table_columns")


@dataclass(frozen=True)
class ExportOptions:
    task_table_attributes: tuple[str, ...] = DEFAULT_TASK_TABLE_ATTRIBUTES

    @classmethod
    def from_mapping(cls, raw: object) -> "ExportOptions":
        if not isinstance(raw, dict):
            raise ValidationError("Export options must be a mapping.")

        task_table_attributes = cls._coerce_task_table_attributes(raw)
        return cls(task_table_attributes=task_table_attributes)

    @staticmethod
    def _coerce_task_table_attributes(raw: dict) -> tuple[str, ...]:
        value = None
        for key in TASK_TABLE_OPTION_KEYS:
            if key in raw:
                value = raw[key]
                break

        if value is None:
            return DEFAULT_TASK_TABLE_ATTRIBUTES
        if not isinstance(value, list):
            raise ValidationError(
                "Export option 'task_table_attributes' must be a list of attribute names."
            )

        attributes: list[str] = []
        seen: set[str] = set()
        for item in value:
            alias = str(item).strip().lower()
            if alias not in TASK_TABLE_ATTRIBUTE_ALIASES:
                allowed = ", ".join(sorted(TASK_TABLE_ATTRIBUTE_ALIASES))
                raise ValidationError(
                    f"Unsupported task table attribute '{item}'. Use one of: {allowed}."
                )
            canonical = TASK_TABLE_ATTRIBUTE_ALIASES[alias]
            if canonical in seen:
                continue
            attributes.append(canonical)
            seen.add(canonical)
        return tuple(attributes)


def load_export_options(path: str | Path) -> ExportOptions:
    source = Path(path)
    if not source.exists():
        raise ValidationError(f"Export options file not found: {source}")

    suffix = source.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = _load_yaml(source)
    elif suffix == ".py":
        data = _load_python(source)
    else:
        raise ValidationError(
            f"Unsupported export options file type '{source.suffix}'. Use .yaml, .yml, or .py."
        )

    return ExportOptions.from_mapping(data)


def _load_yaml(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_python(path: Path) -> object:
    namespace = runpy.run_path(str(path))
    if "EXPORT_OPTIONS" in namespace:
        return namespace["EXPORT_OPTIONS"]
    if "export_options" in namespace:
        return namespace["export_options"]

    raise ValidationError(
        f"Python export options file '{path}' must define EXPORT_OPTIONS or export_options."
    )
