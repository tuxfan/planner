from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


class ValidationError(Exception):
    pass


REQUIRED_FIELDS = {
    "name",
    "start_date",
    "due_date",
    "expected_duration",
    "milestone",
    "priority",
    "risk_level",
    "risk_type",
    "risk_mitigation",
    "status",
    "description",
    "project",
    "dependencies",
}

FIELD_ALIASES = {
    "start date": "start_date",
    "start_date": "start_date",
    "due date": "due_date",
    "due_date": "due_date",
    "expected duration": "expected_duration",
    "expected_duration": "expected_duration",
    "risk level": "risk_level",
    "risk_level": "risk_level",
    "risk type": "risk_type",
    "risk_type": "risk_type",
    "risk mitigation": "risk_mitigation",
    "risk_mitigation": "risk_mitigation",
}


@dataclass(frozen=True)
class Task:
    name: str
    start_date: date
    due_date: date
    expected_duration: int
    milestone: str
    priority: str
    risk_level: str
    risk_type: str
    risk_mitigation: str
    status: str
    description: str
    project: str
    dependencies: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: dict, *, index: int | None = None) -> "Task":
        if not isinstance(raw, dict):
            raise ValidationError(f"Task #{index or '?'} must be a mapping.")

        normalized = {}
        for key, value in raw.items():
            canonical = FIELD_ALIASES.get(key, key)
            normalized[canonical] = value

        missing = REQUIRED_FIELDS - normalized.keys()
        if missing:
            raise ValidationError(
                f"Task '{normalized.get('name', index or '?')}' is missing fields: "
                + ", ".join(sorted(missing))
            )

        dependencies = normalized["dependencies"]
        if not isinstance(dependencies, list):
            raise ValidationError(
                f"Task '{normalized['name']}' has invalid dependencies; expected a list."
            )

        try:
            start_date = date.fromisoformat(str(normalized["start_date"]))
        except ValueError as exc:
            raise ValidationError(
                f"Task '{normalized['name']}' has invalid start_date "
                f"'{normalized['start_date']}'. Use YYYY-MM-DD."
            ) from exc

        try:
            due_date = date.fromisoformat(str(normalized["due_date"]))
        except ValueError as exc:
            raise ValidationError(
                f"Task '{normalized['name']}' has invalid due_date "
                f"'{normalized['due_date']}'. Use YYYY-MM-DD."
            ) from exc

        try:
            expected_duration = int(normalized["expected_duration"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"Task '{normalized['name']}' has invalid expected_duration "
                f"'{normalized['expected_duration']}'. Use a whole number of months."
            ) from exc

        if expected_duration <= 0:
            raise ValidationError(
                f"Task '{normalized['name']}' has invalid expected_duration "
                f"'{normalized['expected_duration']}'. Use a positive number of months."
            )

        if start_date > due_date:
            raise ValidationError(
                f"Task '{normalized['name']}' has start_date after due_date."
            )

        status = str(normalized["status"]).strip().lower()
        if status not in {"todo", "in_progress", "done"}:
            raise ValidationError(
                f"Task '{normalized['name']}' has invalid status '{normalized['status']}'. "
                "Use todo, in_progress, or done."
            )

        return cls(
            name=str(normalized["name"]).strip(),
            start_date=start_date,
            due_date=due_date,
            expected_duration=expected_duration,
            milestone=str(normalized["milestone"]).strip(),
            priority=str(normalized["priority"]).strip(),
            risk_level=str(normalized["risk_level"]).strip(),
            risk_type=str(normalized["risk_type"]).strip(),
            risk_mitigation=str(normalized["risk_mitigation"]).strip(),
            status=status,
            description=str(normalized["description"]).strip(),
            project=str(normalized["project"]).strip(),
            dependencies=tuple(str(item).strip() for item in dependencies),
        )


def validate_tasks(tasks: Iterable[Task]) -> list[Task]:
    items = list(tasks)
    names = [task.name for task in items]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValidationError(
            "Duplicate task names are not allowed: " + ", ".join(duplicates)
        )

    task_map = {task.name: task for task in items}

    for task in items:
        for dependency in task.dependencies:
            if dependency not in task_map:
                raise ValidationError(
                    f"Task '{task.name}' depends on missing task '{dependency}'."
                )

    visited: set[str] = set()
    active: set[str] = set()

    def walk(name: str) -> None:
        if name in active:
            raise ValidationError(f"Dependency cycle detected at task '{name}'.")
        if name in visited:
            return
        active.add(name)
        for dependency in task_map[name].dependencies:
            walk(dependency)
        active.remove(name)
        visited.add(name)

    for name in task_map:
        walk(name)

    return sorted(items, key=lambda task: (task.due_date, task.project, task.name))


def build_schedule(tasks: Iterable[Task]) -> list[tuple[int, str, Task]]:
    ordered = validate_tasks(tasks)
    task_map = {task.name: task for task in ordered}
    indegree = {task.name: len(task.dependencies) for task in ordered}
    dependents: dict[str, list[str]] = {task.name: [] for task in ordered}
    for task in ordered:
        for dependency in task.dependencies:
            dependents[dependency].append(task.name)

    ready = sorted(
        [task.name for task in ordered if indegree[task.name] == 0],
        key=lambda name: (
            task_map[name].due_date,
            task_map[name].project,
            task_map[name].name,
        ),
    )

    result: list[tuple[int, str, Task]] = []
    position = 1

    while ready:
        name = ready.pop(0)
        task = task_map[name]
        result.append((position, _schedule_state(task, task_map), task))
        position += 1
        for dependent in sorted(
            dependents[name],
            key=lambda dep_name: (
                task_map[dep_name].due_date,
                task_map[dep_name].project,
                task_map[dep_name].name,
            ),
        ):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort(
                    key=lambda item: (
                        task_map[item].due_date,
                        task_map[item].project,
                        task_map[item].name,
                    )
                )

    return result


def _schedule_state(task: Task, task_map: dict[str, Task]) -> str:
    if task.status == "done":
        return "COMPLETE"
    if task.status == "in_progress":
        return "ACTIVE"
    if all(task_map[dependency].status == "done" for dependency in task.dependencies):
        return "READY"
    return "BLOCKED"
