# Project Planner

A small planning system that lets you define tasks in either YAML or Python.

Each task supports these fields:

- `id`
- `label`
- `start`
- `deadline`
- `expected duration` or `expected_duration` in months
- `milestone`
- `priority`
- `risk level` or `risk_level`
- `risk type` or `risk_type`
- `risk mitigation` or `risk_mitigation`
- `status`
- `description`
- `project`
- `dependencies` as a list of task ids

## Quick start

Run from this directory:

```bash
python3 -m planner.cli validate planner/examples/tasks.yaml
python3 -m planner.cli list planner/examples/tasks.yaml
python3 -m planner.cli summary planner/examples/tasks.yaml
python3 -m planner.cli schedule planner/examples/tasks.yaml
python3 -m planner.cli export-docx planner/examples/tasks.yaml /tmp/plan.docx
python3 -m planner.cli export-svg planner/examples/tasks.yaml /tmp/plan.svg
```

You can also install it locally:

```bash
python3 -m pip install -e .
tuxfan-planner list planner/examples/tasks.yaml
```

## YAML format

Top-level can be either a list of tasks or a mapping with a `tasks` key.

```yaml
tasks:
  - id: DraftArchitecture
    label: Draft architecture
    start: M1Q3FY26
    deadline: M2Q3FY26
    expected duration: 2
    milestone: Design
    priority: high
    risk level: medium
    risk type: scope
    risk mitigation: Review the architecture with stakeholders before implementation starts.
    status: done
    description: Produce the first architecture draft.
    project: Planning System
    dependencies: []

  - id: BuildParser
    label: Build parser
    start: M2Q3FY26
    deadline: M2Q3FY26
    expected_duration: 1
    milestone: Implementation
    priority: high
    risk_level: medium
    risk_type: integration
    risk_mitigation: Add schema validation tests for both YAML and Python task sources.
    status: todo
    description: Load task definitions from YAML and Python files.
    project: Planning System
    dependencies:
      - DraftArchitecture
```

## Python format

Define `TASKS` or `tasks` in a `.py` file:

```python
TASKS = [
    {
        "id": "DraftArchitecture",
        "label": "Draft architecture",
        "start": "M1Q3FY26",
        "deadline": "M2Q3FY26",
        "expected_duration": 2,
        "milestone": "Design",
        "priority": "high",
        "risk_level": "medium",
        "risk_type": "scope",
        "risk_mitigation": "Review the architecture with stakeholders before implementation starts.",
        "status": "done",
        "description": "Produce the first architecture draft.",
        "project": "Planning System",
        "dependencies": [],
    }
]
```

## Status values

Use one of:

- `todo`
- `in_progress`
- `done`

## Fiscal period values

`start` and `deadline` must use `M{month}Q{quarter}FY{year}`:

- `month` is `1` to `3` within the quarter
- `quarter` is `1` to `4`
- `year` is a 2-digit fiscal year, for example `FY26`

Fiscal years begin on October 1:

- `Q1` = October through December
- `Q2` = January through March
- `Q3` = April through June
- `Q4` = July through September

Examples:

- `M1Q1FY26` = October 2025
- `M2Q3FY26` = May 2026
- `M3Q4FY26` = September 2026

## Commands

- `validate`: checks required fields, invalid status values, invalid fiscal period or duration values, invalid ids, duplicate ids, missing dependencies, and dependency cycles
- `list`: prints task details in deadline order by default, including fiscal start and deadline values and expected duration in months
- `summary`: groups tasks by project and milestone
- `schedule`: prints tasks in dependency order and marks them as `READY`, `BLOCKED`, `ACTIVE`, or `COMPLETE`
- `export-docx`: generates a Word document with the schedule and a detailed task table
- `export-svg`: generates a graphical SVG plan where fill color reflects status, border color reflects risk level, and an accent bar reflects priority
