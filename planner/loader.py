from __future__ import annotations

from pathlib import Path
import runpy

import yaml

from .models import (
    ExecutionItem,
    ProjectPlan,
    Task,
    ValidationError,
    fiscal_year_range,
    validate_tasks,
)

METADATA_KEYS = {
    "portfolio",
    "project",
    "managers",
    "pocs",
    "summary",
    "execution",
    "fiscal_range_begin",
    "fiscal_range_end",
    "fiscal_years",
}


def load_tasks(path: str | Path) -> list[Task]:
    return list(load_plan(path).tasks)


def load_plan(path: str | Path) -> ProjectPlan:
    source = Path(path)
    if not source.exists():
        raise ValidationError(f"Task file not found: {source}")

    suffix = source.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = _load_yaml(source)
    elif suffix == ".py":
        data = _load_python(source)
    else:
        raise ValidationError(
            f"Unsupported file type '{source.suffix}'. Use .yaml, .yml, or .py."
        )

    return _coerce_plan(data, source)


def _load_yaml(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    return data


def _load_python(path: Path) -> object:
    namespace = runpy.run_path(str(path))
    if "PLAN" in namespace:
        return namespace["PLAN"]
    if "plan" in namespace:
        return namespace["plan"]

    if "TASKS" not in namespace and "tasks" not in namespace:
        raise ValidationError(
            f"Python task file '{path}' must define PLAN, plan, TASKS, or tasks."
        )

    data = {"tasks": namespace.get("TASKS", namespace.get("tasks"))}
    for key in METADATA_KEYS:
        if key in namespace:
            data[key] = namespace[key]
        upper_key = key.upper()
        if upper_key in namespace:
            data[key] = namespace[upper_key]
    return data


def _coerce_plan(data: object, path: Path) -> ProjectPlan:
    raw_tasks = _coerce_task_list(data, path)
    tasks = validate_tasks(
        Task.from_mapping(item, index=index) for index, item in enumerate(raw_tasks, 1)
    )

    if not isinstance(data, dict):
        return ProjectPlan(tasks=tuple(tasks))

    metadata = {key: value for key, value in data.items() if key != "tasks"}
    execution_overview, execution_items = _coerce_execution(data)
    return ProjectPlan(
        tasks=tuple(tasks),
        portfolio=_coerce_optional_text(data, "portfolio"),
        project=_coerce_optional_text(data, "project"),
        managers=_coerce_optional_text_list(data, "managers"),
        pocs=_coerce_optional_text_list(data, "pocs"),
        summary=_coerce_optional_text(data, "summary"),
        fiscal_years=_coerce_fiscal_years(data),
        execution_overview=execution_overview,
        execution=execution_items,
        metadata=metadata,
    )


def _coerce_task_list(data: object, path: Path) -> list[object]:
    if isinstance(data, dict):
        if "tasks" not in data:
            raise ValidationError(
                f"Task file '{path}' must contain a top-level list or a 'tasks' key."
            )
        data = data["tasks"]

    if not isinstance(data, list):
        raise ValidationError(f"Task file '{path}' must resolve to a list of tasks.")

    return _expand_task_parts(data)


def _expand_task_parts(raw_tasks: list[object]) -> list[object]:
    expanded_tasks: list[object] = []
    parent_aliases: dict[str, tuple[str, ...]] = {}

    for index, raw_task in enumerate(raw_tasks, 1):
        if not isinstance(raw_task, dict):
            expanded_tasks.append(raw_task)
            continue

        if "parts" not in raw_task:
            expanded_tasks.append(raw_task)
            continue

        parts = raw_task["parts"]
        if not isinstance(parts, list) or not parts:
            label = raw_task.get("label", raw_task.get("id", index))
            raise ValidationError(
                f"Task '{label}' field 'parts' must be a non-empty list."
            )

        parent = {key: value for key, value in raw_task.items() if key != "parts"}
        parent_id = str(parent.get("id", "")).strip()
        if not parent_id:
            raise ValidationError(f"Task #{index} with 'parts' is missing an id.")

        part_ids = _part_id_aliases(parent_id, parts, index)
        parent_aliases[parent_id] = tuple(part_ids.values())

        for part_index, part in enumerate(parts, 1):
            if not isinstance(part, dict):
                raise ValidationError(
                    f"Task '{parent_id}' has invalid part #{part_index}; expected a mapping."
                )

            part_id = str(part.get("id", "")).strip()
            if not part_id:
                raise ValidationError(
                    f"Task '{parent_id}' part #{part_index} is missing an id."
                )

            task = {**parent, **part}
            task["id"] = part_ids[part_id]
            task["_parent_id"] = parent_id
            task["_parent_label"] = str(parent.get("label", "")).strip()
            task["_part_id"] = part_id
            if "funding" in parent and "funding" not in part:
                task["_funding_source_id"] = parent_id
            else:
                task["_funding_source_id"] = task["id"]
            if "dependencies" in task:
                task["dependencies"] = _rewrite_dependency_aliases(
                    task["dependencies"], part_ids
                )
            expanded_tasks.append(task)

    if parent_aliases:
        for task in expanded_tasks:
            if isinstance(task, dict) and "dependencies" in task:
                task["dependencies"] = _rewrite_dependency_aliases(
                    task["dependencies"], parent_aliases
                )

    return expanded_tasks


def _part_id_aliases(
    parent_id: str, parts: list[object], parent_index: int
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for part_index, part in enumerate(parts, 1):
        if not isinstance(part, dict):
            continue
        part_id = str(part.get("id", "")).strip()
        if not part_id:
            continue
        expanded_id = _expanded_part_id(parent_id, part_id)
        if part_id in aliases:
            raise ValidationError(
                f"Task '{parent_id}' has duplicate part id '{part_id}'."
            )
        if expanded_id in aliases.values():
            raise ValidationError(
                f"Task '{parent_id}' part #{part_index} expands to duplicate id '{expanded_id}'."
            )
        aliases[part_id] = expanded_id
    if not aliases:
        raise ValidationError(f"Task #{parent_index} has no valid part ids.")
    return aliases


def _expanded_part_id(parent_id: str, part_id: str) -> str:
    if part_id == parent_id or part_id.startswith(f"{parent_id}_"):
        return part_id
    return f"{parent_id}_{part_id}"


def _rewrite_dependency_aliases(
    dependencies: object, aliases: dict[str, str | tuple[str, ...]]
) -> object:
    if not isinstance(dependencies, list):
        return dependencies

    rewritten: list[str] = []
    for dependency in dependencies:
        key = str(dependency).strip()
        replacement = aliases.get(key, key)
        replacement_items = (
            replacement if isinstance(replacement, tuple) else (replacement,)
        )
        for item in replacement_items:
            if item not in rewritten:
                rewritten.append(item)
    return rewritten


def _coerce_optional_text(data: dict, key: str) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        raise ValidationError(f"Top-level '{key}' must be text.")
    return str(value).strip()


def _coerce_optional_text_list(data: dict, key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"Top-level '{key}' must be a list of text values.")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _coerce_fiscal_years(data: dict) -> tuple[str, ...]:
    if "fiscal_range_begin" in data or "fiscal_range_end" in data:
        if "fiscal_range_begin" not in data or "fiscal_range_end" not in data:
            raise ValidationError(
                "Top-level fiscal year range requires both "
                "'fiscal_range_begin' and 'fiscal_range_end'."
            )
        return fiscal_year_range(data["fiscal_range_begin"], data["fiscal_range_end"])

    value = data.get("fiscal_years", [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError("Top-level 'fiscal_years' must be a list.")
    years = []
    for item in value:
        year = fiscal_year_range(item, item)[0]
        if year not in years:
            years.append(year)
    return tuple(years)


def _coerce_execution(data: dict) -> tuple[str, tuple[ExecutionItem, ...]]:
    value = data.get("execution", [])
    if value is None:
        return "", ()
    if isinstance(value, dict):
        overview = _coerce_nested_optional_text(value, "overview", "execution")
        sections = value.get("sections", [])
        if sections is None:
            sections = []
        if not isinstance(sections, list):
            raise ValidationError(
                "Top-level 'execution.sections' must be a list of items."
            )
        return overview, _coerce_execution_items(sections)
    if not isinstance(value, list):
        raise ValidationError(
            "Top-level 'execution' must be a list of items or a mapping with 'overview' and 'sections'."
        )
    return "", _coerce_execution_items(value)


def _coerce_execution_items(value: list) -> tuple[ExecutionItem, ...]:
    return tuple(
        ExecutionItem.from_mapping(item, index=index)
        for index, item in enumerate(value, 1)
    )


def _coerce_nested_optional_text(data: dict, key: str, parent: str) -> str:
    value = data.get(key, "")
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        raise ValidationError(f"Top-level '{parent}.{key}' must be text.")
    return str(value).strip()
