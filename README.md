# Project Planner

A small planning system that lets you define tasks in either YAML or Python.

Each task supports these fields:

- `name`
- `start date` or `start_date`
- `due date` or `due_date`
- `expected duration` or `expected_duration` in months
- `milestone`
- `priority`
- `risk level` or `risk_level`
- `risk type` or `risk_type`
- `risk mitigation` or `risk_mitigation`
- `status`
- `description`
- `project`
- `dependencies`

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
project-planner list planner/examples/tasks.yaml
```

## YAML format

Top-level can be either a list of tasks or a mapping with a `tasks` key.

```yaml
tasks:
  - name: Draft architecture
    start date: 2026-04-01
    due date: 2026-05-05
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

  - name: Build parser
    start_date: 2026-05-01
    due_date: 2026-05-10
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
      - Draft architecture
```

## Python format

Define `TASKS` or `tasks` in a `.py` file:

```python
TASKS = [
    {
        "name": "Draft architecture",
        "start_date": "2026-04-01",
        "due_date": "2026-05-05",
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

## Commands

- `validate`: checks required fields, invalid status values, invalid date or duration values, duplicate names, missing dependencies, and dependency cycles
- `list`: prints task details in due-date order by default, including start date and expected duration in months
- `summary`: groups tasks by project and milestone
- `schedule`: prints tasks in dependency order and marks them as `READY`, `BLOCKED`, `ACTIVE`, or `COMPLETE`
- `export-docx`: generates a Word document with the schedule and a detailed task table
- `export-svg`: generates a graphical SVG plan where fill color reflects status, border color reflects risk level, and an accent bar reflects priority
