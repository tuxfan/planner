from __future__ import annotations

from pathlib import Path
import runpy

import yaml

from .models import ProjectPlan, Task, ValidationError, validate_tasks


METADATA_KEYS = {"portfolio", "project", "managers", "pocs", "summary"}


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
    return ProjectPlan(
        tasks=tuple(tasks),
        portfolio=_coerce_optional_text(data, "portfolio"),
        project=_coerce_optional_text(data, "project"),
        managers=_coerce_optional_text_list(data, "managers"),
        pocs=_coerce_optional_text_list(data, "pocs"),
        summary=_coerce_optional_text(data, "summary"),
        metadata=metadata,
    )


def _coerce_task_list(data: object, path: Path) -> list[dict]:
    if isinstance(data, dict):
        if "tasks" not in data:
            raise ValidationError(
                f"Task file '{path}' must contain a top-level list or a 'tasks' key."
            )
        data = data["tasks"]

    if not isinstance(data, list):
        raise ValidationError(f"Task file '{path}' must resolve to a list of tasks.")

    return data


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
