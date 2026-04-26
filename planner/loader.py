from __future__ import annotations

from pathlib import Path
import runpy

import yaml

from .models import Task, ValidationError, validate_tasks


def load_tasks(path: str | Path) -> list[Task]:
    source = Path(path)
    if not source.exists():
        raise ValidationError(f"Task file not found: {source}")

    suffix = source.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        raw_tasks = _load_yaml(source)
    elif suffix == ".py":
        raw_tasks = _load_python(source)
    else:
        raise ValidationError(
            f"Unsupported file type '{source.suffix}'. Use .yaml, .yml, or .py."
        )

    tasks = [Task.from_mapping(item, index=index) for index, item in enumerate(raw_tasks, 1)]
    return validate_tasks(tasks)


def _load_yaml(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or []
    return _coerce_task_list(data, path)


def _load_python(path: Path) -> list[dict]:
    namespace = runpy.run_path(str(path))
    if "TASKS" in namespace:
        data = namespace["TASKS"]
    elif "tasks" in namespace:
        data = namespace["tasks"]
    else:
        raise ValidationError(
            f"Python task file '{path}' must define TASKS or tasks."
        )
    return _coerce_task_list(data, path)


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

