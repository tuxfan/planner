from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable, Mapping


class ValidationError(Exception):
    pass


REQUIRED_FIELDS = {
    "id",
    "label",
    "start",
    "deadline",
    "expected_duration",
    "milestone",
    "priority",
    "risk",
    "status",
    "description",
    "project",
    "dependencies",
}

FIELD_ALIASES = {
    "bnr": "bnr",
    "cost": "cost",
    "start": "start",
    "start month": "start",
    "deadline": "deadline",
    "deadline month": "deadline",
    "expected duration": "expected_duration",
    "expected_duration": "expected_duration",
    "funding status": "funding_status",
    "funding_status": "funding_status",
    "funding": "funding",
    "risk": "risk",
    "site": "site",
    "tags": "tags",
    "type": "type",
}

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
FISCAL_PERIOD_PATTERN = re.compile(r"^M([1-3])Q([1-4])FY(\d{2})$", re.IGNORECASE)
FISCAL_YEAR_PATTERN = re.compile(r"^(?:FY)?(\d{2}|\d{4})$", re.IGNORECASE)
FUNDING_LEVEL_PATTERN = re.compile(
    r"^\$?([0-9]+(?:\.[0-9]+)?)([KMB])?$", re.IGNORECASE
)
ALLOWED_PRIORITIES = {"low", "medium", "high", "urgent"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "extreme"}
ALLOWED_STATUSES = {"pending", "active", "ongoing", "blocked", "complete"}


@dataclass(frozen=True)
class Risk:
    type: str
    level: str
    mitigation: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object], *, label: str, index: int) -> "Risk":
        if not isinstance(raw, Mapping):
            raise ValidationError(
                f"Task '{label}' has invalid risk item #{index}; expected a mapping."
            )

        missing = {"type", "level", "mitigation"} - raw.keys()
        if missing:
            raise ValidationError(
                f"Task '{label}' risk item #{index} is missing fields: "
                + ", ".join(sorted(missing))
            )

        risk_type = str(raw["type"]).strip()
        risk_level = str(raw["level"]).strip().lower()
        risk_mitigation = str(raw["mitigation"]).strip()
        if not risk_type:
            raise ValidationError(f"Task '{label}' risk item #{index} has empty type.")
        if risk_level not in ALLOWED_RISK_LEVELS:
            raise ValidationError(
                f"Task '{label}' has invalid risk level '{raw['level']}'. "
                "Use low, medium, high, or extreme."
            )
        if not risk_mitigation:
            raise ValidationError(
                f"Task '{label}' risk item #{index} has empty mitigation."
            )

        return cls(type=risk_type, level=risk_level, mitigation=risk_mitigation)


@dataclass(frozen=True)
class Task:
    id: str
    label: str
    start: str
    deadline: str
    expected_duration: int
    milestone: str
    priority: str
    risks: tuple[Risk, ...]
    status: str
    description: str
    project: str
    dependencies: tuple[str, ...]
    bnr: str = ""
    cost: str = ""
    funding_status: str = ""
    funding: Mapping[str, str] = field(default_factory=dict)
    site: str = ""
    type: str = ""
    tags: tuple[str, ...] = ()

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
                f"Task '{normalized.get('label', normalized.get('id', index or '?'))}' is missing fields: "
                + ", ".join(sorted(missing))
            )

        task_id = str(normalized["id"]).strip()
        label = str(normalized["label"]).strip()
        dependencies = normalized["dependencies"]
        if not isinstance(dependencies, list):
            raise ValidationError(
                f"Task '{label}' has invalid dependencies; expected a list."
            )
        if not TASK_ID_PATTERN.fullmatch(task_id):
            raise ValidationError(
                f"Task '{label}' has invalid id '{normalized['id']}'. Use only letters, numbers, and underscores with no spaces."
            )

        start = _parse_fiscal_period(
            normalized["start"], field_name="start", label=label
        )
        deadline = _parse_fiscal_period(
            normalized["deadline"], field_name="deadline", label=label
        )

        try:
            expected_duration = int(normalized["expected_duration"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"Task '{label}' has invalid expected_duration "
                f"'{normalized['expected_duration']}'. Use a whole number of months."
            ) from exc

        if expected_duration <= 0:
            raise ValidationError(
                f"Task '{label}' has invalid expected_duration "
                f"'{normalized['expected_duration']}'. Use a positive number of months."
            )

        if _fiscal_period_sort_key(start) > _fiscal_period_sort_key(deadline):
            raise ValidationError(f"Task '{label}' has start after deadline.")

        priority = str(normalized["priority"]).strip().lower()
        if priority not in ALLOWED_PRIORITIES:
            raise ValidationError(
                f"Task '{label}' has invalid priority '{normalized['priority']}'. "
                "Use low, medium, high, or urgent."
            )

        risks = _coerce_task_risks(normalized, label)

        status = str(normalized["status"]).strip().lower()
        if status not in ALLOWED_STATUSES:
            raise ValidationError(
                f"Task '{label}' has invalid status '{normalized['status']}'. "
                "Use pending, active, ongoing, blocked, or complete."
            )

        return cls(
            id=task_id,
            label=label,
            start=start,
            deadline=deadline,
            expected_duration=expected_duration,
            milestone=str(normalized["milestone"]).strip(),
            priority=priority,
            risks=risks,
            status=status,
            description=str(normalized["description"]).strip(),
            project=str(normalized["project"]).strip(),
            dependencies=tuple(str(item).strip() for item in dependencies),
            bnr=_coerce_optional_task_text(normalized, "bnr"),
            cost=_coerce_optional_task_text(normalized, "cost"),
            funding_status=_coerce_optional_task_text(normalized, "funding_status"),
            funding=_coerce_task_funding(normalized, label),
            site=_coerce_optional_task_text(normalized, "site"),
            type=_coerce_optional_task_text(normalized, "type"),
            tags=_coerce_optional_task_tags(normalized),
        )


@dataclass(frozen=True)
class ExecutionItem:
    label: str
    description: str

    @classmethod
    def from_mapping(cls, raw: dict, *, index: int | None = None) -> "ExecutionItem":
        if not isinstance(raw, dict):
            raise ValidationError(f"Execution item #{index or '?'} must be a mapping.")

        missing = {"label", "description"} - raw.keys()
        if missing:
            raise ValidationError(
                f"Execution item #{index or '?'} is missing fields: "
                + ", ".join(sorted(missing))
            )

        label = str(raw["label"]).strip()
        description = str(raw["description"]).strip()
        if not label:
            raise ValidationError(f"Execution item #{index or '?'} has an empty label.")
        if not description:
            raise ValidationError(f"Execution item '{label}' has an empty description.")

        return cls(label=label, description=description)


@dataclass(frozen=True)
class ProjectPlan:
    tasks: tuple[Task, ...]
    portfolio: str = ""
    project: str = ""
    managers: tuple[str, ...] = ()
    pocs: tuple[str, ...] = ()
    summary: str = ""
    fiscal_years: tuple[str, ...] = ()
    execution_overview: str = ""
    execution: tuple[ExecutionItem, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


def _parse_fiscal_period(value: object, *, field_name: str, label: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(
            f"Task '{label}' has invalid {field_name} '{value}'. Use format M1Q1FY26."
        )

    match = FISCAL_PERIOD_PATTERN.fullmatch(normalized)
    if match is None:
        raise ValidationError(
            f"Task '{label}' has invalid {field_name} '{value}'. Use format M1Q1FY26."
        )

    month_in_quarter, quarter, fiscal_year = match.groups()
    return f"M{month_in_quarter}Q{quarter}FY{fiscal_year}"


def _coerce_optional_task_text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key, "")
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        raise ValidationError(f"Task field '{key}' must be text when provided.")
    text = str(value).strip()
    if text.lower() in {"none", "null"}:
        return ""
    return text


def _coerce_optional_task_tags(raw: Mapping[str, object]) -> tuple[str, ...]:
    if "tags" not in raw:
        return ()
    value = raw["tags"]
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"none", "null"}:
            return ()
        return tuple(part.strip() for part in text.split(",") if part.strip())
    if not isinstance(value, list):
        raise ValidationError("Task field 'tags' must be text or a list when provided.")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _coerce_task_risks(raw: Mapping[str, object], label: str) -> tuple[Risk, ...]:
    value = raw["risk"]
    if isinstance(value, Mapping):
        return (Risk.from_mapping(value, label=label, index=1),)
    if isinstance(value, list):
        if not value:
            raise ValidationError(f"Task '{label}' field 'risk' cannot be empty.")
        return tuple(
            Risk.from_mapping(item, label=label, index=index)
            for index, item in enumerate(value, 1)
        )
    raise ValidationError(f"Task '{label}' field 'risk' must be a mapping or list.")


def _coerce_task_funding(raw: Mapping[str, object], label: str) -> Mapping[str, str]:
    value = raw.get("funding", {})
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return _coerce_funding_mapping(value, label)
    if isinstance(value, list):
        funding: dict[str, str] = {}
        for index, item in enumerate(value, 1):
            if not isinstance(item, Mapping):
                raise ValidationError(
                    f"Task '{label}' has invalid funding item #{index}; expected a mapping."
                )
            year = item.get("year", item.get("fiscal_year", item.get("fiscal year")))
            level = item.get("level", item.get("funding", item.get("amount")))
            if year is None or level is None:
                raise ValidationError(
                    f"Task '{label}' has invalid funding item #{index}; expected year and level."
                )
            funding[_coerce_fiscal_year(year, context=f"Task '{label}' funding")] = (
                _coerce_funding_level(level, label)
            )
        return funding
    raise ValidationError(f"Task '{label}' field 'funding' must be a mapping or list.")


def _coerce_funding_mapping(
    value: Mapping[object, object], label: str
) -> Mapping[str, str]:
    funding: dict[str, str] = {}
    for year, level in value.items():
        fiscal_year = _coerce_fiscal_year(year, context=f"Task '{label}' funding")
        funding[fiscal_year] = _coerce_funding_level(level, label)
    return funding


def _coerce_funding_level(value: object, label: str) -> str:
    if value is None:
        raise ValidationError(f"Task '{label}' has a funding year with no level.")
    if isinstance(value, (list, dict)):
        raise ValidationError(f"Task '{label}' funding levels must be text or numbers.")
    text = str(value).strip()
    if not text:
        raise ValidationError(f"Task '{label}' has a blank funding level.")
    return text


def _coerce_fiscal_year(value: object, *, context: str = "fiscal year") -> str:
    text = str(value).strip()
    match = FISCAL_YEAR_PATTERN.fullmatch(text)
    if match is None:
        raise ValidationError(f"{context} value '{value}' must look like FY27.")
    year = match.group(1)
    if len(year) == 4:
        year = year[-2:]
    return f"FY{year}"


def fiscal_year_range(begin: object, end: object) -> tuple[str, ...]:
    start = _fiscal_year_number(begin, context="fiscal_range_begin")
    stop = _fiscal_year_number(end, context="fiscal_range_end")
    if start > stop:
        raise ValidationError(
            "Top-level 'fiscal_range_begin' cannot be after 'fiscal_range_end'."
        )
    return tuple(f"FY{year:02d}" for year in range(start, stop + 1))


def _fiscal_year_number(value: object, *, context: str) -> int:
    fiscal_year = _coerce_fiscal_year(value, context=context)
    return int(fiscal_year[2:])


def funding_totals(
    tasks: Iterable[Task], fiscal_years: Iterable[str]
) -> Mapping[str, str]:
    totals = {year: 0.0 for year in fiscal_years}
    for task in tasks:
        for year, level in task.funding.items():
            if year not in totals:
                continue
            totals[year] += _funding_level_to_k(level)
    return {year: _format_funding_k(total) for year, total in totals.items()}


def _funding_level_to_k(value: str) -> float:
    text = value.strip().replace(",", "")
    match = FUNDING_LEVEL_PATTERN.fullmatch(text)
    if match is None:
        raise ValidationError(
            f"Funding level '{value}' must be numeric, optionally with K, M, or B."
        )
    amount = float(match.group(1))
    unit = (match.group(2) or "K").upper()
    if unit == "K":
        return amount
    if unit == "M":
        return amount * 1000
    if unit == "B":
        return amount * 1000000
    raise AssertionError(f"Unhandled funding unit: {unit}")


def _format_funding_k(value: float) -> str:
    if value.is_integer():
        return f"{int(value)}K"
    return f"{value:g}K"


def _fiscal_period_sort_key(value: str) -> tuple[int, int]:
    match = FISCAL_PERIOD_PATTERN.fullmatch(value)
    if match is None:
        raise ValidationError(f"Invalid fiscal period '{value}'.")
    month_in_quarter, quarter, fiscal_year = match.groups()
    fiscal_month = (int(quarter) - 1) * 3 + int(month_in_quarter)
    return (int(fiscal_year), fiscal_month)


def validate_tasks(tasks: Iterable[Task]) -> list[Task]:
    items = list(tasks)
    ids = [task.id for task in items]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise ValidationError(
            "Duplicate task ids are not allowed: " + ", ".join(duplicates)
        )

    task_map = {task.id: task for task in items}

    for task in items:
        for dependency in task.dependencies:
            if dependency not in task_map:
                raise ValidationError(
                    f"Task '{task.label}' depends on missing task id '{dependency}'."
                )

    visited: set[str] = set()
    active: set[str] = set()

    def walk(task_id: str) -> None:
        if task_id in active:
            raise ValidationError(f"Dependency cycle detected at task id '{task_id}'.")
        if task_id in visited:
            return
        active.add(task_id)
        for dependency in task_map[task_id].dependencies:
            walk(dependency)
        active.remove(task_id)
        visited.add(task_id)

    for task_id in task_map:
        walk(task_id)

    return sorted(
        items,
        key=lambda task: (
            _fiscal_period_sort_key(task.deadline),
            task.project,
            task.label,
            task.id,
        ),
    )


def build_schedule(tasks: Iterable[Task]) -> list[tuple[int, str, Task]]:
    ordered = validate_tasks(tasks)
    task_map = {task.id: task for task in ordered}
    indegree = {task.id: len(task.dependencies) for task in ordered}
    dependents: dict[str, list[str]] = {task.id: [] for task in ordered}
    for task in ordered:
        for dependency in task.dependencies:
            dependents[dependency].append(task.id)

    ready = sorted(
        [task.id for task in ordered if indegree[task.id] == 0],
        key=lambda task_id: (
            _fiscal_period_sort_key(task_map[task_id].deadline),
            task_map[task_id].project,
            task_map[task_id].label,
            task_map[task_id].id,
        ),
    )

    result: list[tuple[int, str, Task]] = []
    position = 1

    while ready:
        task_id = ready.pop(0)
        task = task_map[task_id]
        result.append((position, _schedule_state(task, task_map), task))
        position += 1
        for dependent in sorted(
            dependents[task_id],
            key=lambda dep_name: (
                _fiscal_period_sort_key(task_map[dep_name].deadline),
                task_map[dep_name].project,
                task_map[dep_name].label,
                task_map[dep_name].id,
            ),
        ):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort(
                    key=lambda item: (
                        _fiscal_period_sort_key(task_map[item].deadline),
                        task_map[item].project,
                        task_map[item].label,
                        task_map[item].id,
                    )
                )

    return result


def _schedule_state(task: Task, task_map: dict[str, Task]) -> str:
    if task.status == "complete":
        return "COMPLETE"
    if task.status == "active":
        return "ACTIVE"
    if task.status == "ongoing":
        return "ONGOING"
    if task.status == "blocked":
        return "BLOCKED"
    if all(
        task_map[dependency].status == "complete" for dependency in task.dependencies
    ):
        return "READY"
    return "BLOCKED"
