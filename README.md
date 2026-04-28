# Project Planner

A small planning system that lets you define project plans and tasks in either YAML or Python.

A plan can include optional top-level project metadata:

- `portfolio`: portfolio or parent program name.
- `project`: high-level project name. When present, this is used as the plan title.
- `managers`: list of manager names.
- `pocs`: list of point-of-contact names.
- `summary`: high-level plan summary.

Each task supports these fields:

- `id`: required string task id. Must contain only letters, numbers, or underscores, with no spaces.
- `label`: required string display name for the task.
- `start`: required fiscal period string in `M{month}Q{quarter}FY{year}` format, where `month` is `1` to `3` within the quarter.
- `deadline`: required fiscal period string in `M{month}Q{quarter}FY{year}` format, where `month` is `1` to `3` within the quarter.
- `expected duration` or `expected_duration`: required positive whole number of months.
- `milestone`: required string milestone name.
- `priority`: required string priority label such as `low`, `medium`, `high`, or `urgent`.
- `risk level` or `risk_level`: required string risk severity label such as `low`, `medium`, `high`, or `extreme`.
- `risk type` or `risk_type`: required string risk category.
- `risk mitigation` or `risk_mitigation`: required string describing how the risk will be mitigated.
- `status`: required string status. Allowed values are `pending`, `active`, `ongoing`, `blocked`, and `complete`.
- `description`: required string describing the task.
- `project`: required string project name.
- `dependencies`: required list of task ids. Each dependency must reference another task `id`.

## Quick start

Run from this directory:

```bash
planner validate planner/examples/tasks.yaml
planner list planner/examples/tasks.yaml
planner summary planner/examples/tasks.yaml
planner schedule planner/examples/tasks.yaml
planner export-docx planner/examples/tasks.yaml /tmp/plan.docx
planner export-svg planner/examples/tasks.yaml /tmp/plan.svg
```

If you set `TUXFAN_PLANNER_DATAFILE`, the CLI uses that file by default:

```bash
export TUXFAN_PLANNER_DATAFILE=planner/examples/tasks.yaml
planner validate
planner list
planner export-docx /tmp/plan.docx
planner export-svg /tmp/plan.svg
```

You can also install it locally:

```bash
python3 -m pip install -e .
planner list planner/examples/tasks.yaml
```

The legacy `tuxfan-planner` command remains available as an alias.

## YAML format

Top-level can be either a list of tasks or a mapping with a `tasks` key. The mapping form can also include plan-level metadata such as `portfolio`, `project`, `managers`, `pocs`, and `summary`.

```yaml
portfolio: Advanced Simulation and Computing
project: Task-Parallel Project
managers:
  - Alice Example
pocs:
  - Casey Example, PI
summary: >
  High-level planning context for the task collection.

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
    status: complete
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
    status: pending
    description: Load task definitions from YAML and Python files.
    project: Planning System
    dependencies:
      - DraftArchitecture
```

## Python format

Define `PLAN` or `plan` in a `.py` file for metadata plus tasks. The legacy `TASKS` or `tasks` list still works.

```python
PLAN = {
    "portfolio": "Advanced Simulation and Computing",
    "project": "Task-Parallel Project",
    "managers": ["Alice Example"],
    "pocs": ["Casey Example, PI"],
    "summary": "High-level planning context for the task collection.",
    "tasks": [
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
            "status": "complete",
            "description": "Produce the first architecture draft.",
            "project": "Planning System",
            "dependencies": [],
        }
    ],
}
```

## Status values

Use one of:

- `pending`
- `active`
- `ongoing`
- `blocked`
- `complete`

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
