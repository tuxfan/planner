from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import runpy

import yaml

from .models import ValidationError

DEFAULT_TASK_TABLE_ATTRIBUTES = ("site", "bnr", "cost", "funding_status", "type")
TASK_TABLE_ATTRIBUTE_ALIASES = {
    "bnr": "bnr",
    "cost": "cost",
    "funding": "funding_status",
    "funding_status": "funding_status",
    "site": "site",
    "type": "type",
    "tags": "tags",
}
TASK_TABLE_COLUMN_ALIGNMENT_ALIASES = {
    "left": "left",
    "center": "center",
    "right": "right",
}
TASK_TABLE_OPTION_KEYS = ("task_table_columns", "task_table_attributes")


@dataclass(frozen=True)
class TaskTableColumn:
    attribute: str
    label: str | None = None
    alignment: str = "center"


@dataclass(frozen=True)
class ExportOptions:
    task_table_attributes: tuple[str, ...] = DEFAULT_TASK_TABLE_ATTRIBUTES
    task_table_columns: tuple[TaskTableColumn, ...] = ()

    @classmethod
    def from_mapping(cls, raw: object) -> "ExportOptions":
        if not isinstance(raw, dict):
            raise ValidationError("Export options must be a mapping.")

        task_table_columns = cls._coerce_task_table_columns(raw)
        return cls(
            task_table_attributes=tuple(
                column.attribute for column in task_table_columns
            ),
            task_table_columns=task_table_columns,
        )

    def resolved_task_table_columns(self) -> tuple[TaskTableColumn, ...]:
        if self.task_table_columns:
            return self.task_table_columns
        return tuple(
            TaskTableColumn(attribute=attribute)
            for attribute in self.task_table_attributes
        )

    @staticmethod
    def _coerce_task_table_columns(raw: dict) -> tuple[TaskTableColumn, ...]:
        value = None
        for key in TASK_TABLE_OPTION_KEYS:
            if key in raw:
                value = raw[key]
                break

        if value is None:
            return tuple(
                TaskTableColumn(attribute=attribute)
                for attribute in DEFAULT_TASK_TABLE_ATTRIBUTES
            )
        if not isinstance(value, list):
            raise ValidationError(
                "Export option 'task_table_attributes' must be a list of attribute names or column definitions."
            )

        columns: list[TaskTableColumn] = []
        seen: set[str] = set()
        for item in value:
            column = ExportOptions._coerce_task_table_column(item)
            if column.attribute in seen:
                continue
            columns.append(column)
            seen.add(column.attribute)
        return tuple(columns)

    @staticmethod
    def _coerce_task_table_column(item: object) -> TaskTableColumn:
        if isinstance(item, str):
            return TaskTableColumn(attribute=_canonical_attribute(item))

        if not isinstance(item, dict):
            raise ValidationError(
                "Each task table column must be an attribute name or a mapping."
            )

        if "attribute" in item:
            return TaskTableColumn(
                attribute=_canonical_attribute(item["attribute"]),
                label=_coerce_optional_label(item.get("label")),
                alignment=_coerce_alignment(item.get("alignment")),
            )

        if len(item) != 1:
            raise ValidationError(
                "Shorthand task table column mappings must contain exactly one attribute key."
            )

        alias, raw_value = next(iter(item.items()))
        attribute = _canonical_attribute(alias)
        if raw_value is None:
            return TaskTableColumn(attribute=attribute)
        if isinstance(raw_value, str):
            return TaskTableColumn(attribute=attribute, label=raw_value.strip() or None)
        if isinstance(raw_value, dict):
            return TaskTableColumn(
                attribute=attribute,
                label=_coerce_optional_label(raw_value.get("label")),
                alignment=_coerce_alignment(raw_value.get("alignment")),
            )
        raise ValidationError(
            "Shorthand task table column values must be text or a mapping."
        )


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


def _canonical_attribute(value: object) -> str:
    alias = str(value).strip().lower()
    if alias not in TASK_TABLE_ATTRIBUTE_ALIASES:
        allowed = ", ".join(sorted(TASK_TABLE_ATTRIBUTE_ALIASES))
        raise ValidationError(
            f"Unsupported task table attribute '{value}'. Use one of: {allowed}."
        )
    return TASK_TABLE_ATTRIBUTE_ALIASES[alias]


def _coerce_optional_label(value: object) -> str | None:
    if value is None:
        return None
    label = str(value).strip()
    return label or None


def _coerce_alignment(value: object) -> str:
    if value is None:
        return "center"
    alias = str(value).strip().lower()
    if alias not in TASK_TABLE_COLUMN_ALIGNMENT_ALIASES:
        allowed = ", ".join(sorted(TASK_TABLE_COLUMN_ALIGNMENT_ALIASES))
        raise ValidationError(
            f"Unsupported task table column alignment '{value}'. Use one of: {allowed}."
        )
    return TASK_TABLE_COLUMN_ALIGNMENT_ALIASES[alias]


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
