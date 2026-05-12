# Project Planner

A small planning system that lets you define project plans and tasks in either YAML or Python.

A plan can include optional top-level project metadata:

- `portfolio`: portfolio or parent program name.
- `project`: high-level project name.
- `managers`: list of manager names.
- `pocs`: list of point-of-contact names.
- `summary`: high-level plan summary.
- `fiscal_range_begin` and `fiscal_range_end`: optional fiscal year range covered by the plan, for example `27` through `31`.
- `execution`: execution metadata. It can be a mapping with `overview` text and `sections`, where each section has `label` and `description`. The older flat list of sections is still accepted.

Each task supports these fields:

- `id`: required string task id. Must contain only letters, numbers, or underscores, with no spaces.
- `label`: required string display name for the task.
- `site`: optional site or institution label.
- `bnr`: optional budget and reporting identifier.
- `cost`: optional task cost label, for example `$100K`.
- `funding status` or `funding_status`: optional funding state label.
- `type`: optional task type label.
- `tags`: optional comma-separated string or list of task tags.
- `project`: required string project name.
- `description`: required string describing the task.
- `start`: required fiscal period string in `M{month}Q{quarter}FY{year}` format, where `month` is `1` to `3` within the quarter.
- `deadline`: required fiscal period string in `M{month}Q{quarter}FY{year}` format, where `month` is `1` to `3` within the quarter.
- `expected duration` or `expected_duration`: required positive whole number of months.
- `milestone`: required string milestone name.
- `priority`: required string priority label such as `low`, `medium`, `high`, or `urgent`.
- `status`: required string status. Allowed values are `pending`, `active`, `ongoing`, `blocked`, and `complete`.
- `dependencies`: required list of task ids. Each dependency must reference another task `id`.
- `risk`: required risk entry or list of risk entries. Each entry has `type`, `level`, and `mitigation`; `level` must be `low`, `medium`, `high`, or `extreme`.
- `funding`: optional mapping of fiscal year to funding level, for example `fy27: 50K`. A task is treated as unfunded for fiscal years not present in this mapping.

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

If you set `TUXFAN_PLANNER_EXPORT_OPTIONS`, the export commands use that file by default:

```bash
export TUXFAN_PLANNER_EXPORT_OPTIONS=planner/examples/export-options.yaml
planner export-docx planner/examples/tasks.yaml /tmp/plan.docx
```

You can also install it locally:

```bash
python3 -m pip install -e .
planner list planner/examples/tasks.yaml
```

The legacy `tuxfan-planner` command remains available as an alias.

## Shell completion

The CLI can print completion scripts for `bash`, `zsh`, and `fish`:

```bash
planner completion bash
planner completion zsh
planner completion fish
```

For a one-session bash setup:

```bash
source <(planner completion bash)
```

The generated completion supports the basic planner subcommands, the
`tuxfan-planner` alias, file path completion for task and output arguments, and
`--export-options` for export commands.

## YAML format

Top-level can be either a list of tasks or a mapping with a `tasks` key. The mapping form can also include plan-level metadata such as `portfolio`, `project`, `managers`, `pocs`, `summary`, `fiscal_range_begin`, `fiscal_range_end`, and `execution`.

```yaml
portfolio: Advanced Simulation and Computing
project: Task-Parallel Project
managers:
  - Alice Example
pocs:
  - Casey Example, PI
summary: >
  High-level planning context for the task collection.
fiscal_range_begin: 27
fiscal_range_end: 29
execution:
  overview: >
    Overall execution context for the plan.
  sections:
    - label: Deliverable A
      description: >
        Narrative execution detail for this deliverable.

tasks:
  - id: DraftArchitecture
    label: Draft architecture
    bnr: DP1518130
    cost: $100K
    funding status: funded
    site: LANL
    type: labor
    tags:
      - architecture
    project: Planning System
    description: Produce the first architecture draft.
    start: M1Q3FY26
    deadline: M2Q3FY26
    expected duration: 2
    milestone: Design
    priority: high
    status: complete
    dependencies: []
    risk:
      - type: scope
        level: medium
        mitigation: Review the architecture with stakeholders before implementation starts.
    funding:
      fy27: 50K
      fy29: 100K

  - id: BuildParser
    label: Build parser
    project: Planning System
    description: Load task definitions from YAML and Python files.
    start: M2Q3FY26
    deadline: M2Q3FY26
    expected_duration: 1
    milestone: Implementation
    priority: high
    status: pending
    dependencies:
      - DraftArchitecture
    risk:
      - type: integration
        level: medium
        mitigation: Add schema validation tests for both YAML and Python task sources.
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
    "fiscal_range_begin": 27,
    "fiscal_range_end": 29,
    "execution": {
        "overview": "Overall execution context for the plan.",
        "sections": [
            {
                "label": "Deliverable A",
                "description": "Narrative execution detail for this deliverable.",
            }
        ],
    },
    "tasks": [
        {
            "id": "DraftArchitecture",
            "label": "Draft architecture",
            "bnr": "DP1518130",
            "cost": "$100K",
            "funding_status": "funded",
            "site": "LANL",
            "type": "labor",
            "tags": ["architecture"],
            "project": "Planning System",
            "description": "Produce the first architecture draft.",
            "start": "M1Q3FY26",
            "deadline": "M2Q3FY26",
            "expected_duration": 2,
            "milestone": "Design",
            "priority": "high",
            "status": "complete",
            "dependencies": [],
            "risk": [
                {
                    "type": "scope",
                    "level": "medium",
                    "mitigation": "Review the architecture with stakeholders before implementation starts.",
                }
            ],
            "funding": {"fy27": "50K", "fy29": "100K"},
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
- `summary`: groups tasks by project and milestone and prints funding totals when task funding is present
- `schedule`: prints tasks in dependency order and marks them as `READY`, `BLOCKED`, `ACTIVE`, or `COMPLETE`
- `export-docx`: generates a Word document with the schedule and a detailed task table. Use `--export-options PATH` or `TUXFAN_PLANNER_EXPORT_OPTIONS` to control which optional task attributes appear in the summary table and in the per-task narrative metadata. When fiscal years are configured, the table also includes one column per fiscal year with each task's funding level or a blank cell when the task is not funded in that year.
- `export-svg`: generates a graphical SVG plan where fill color reflects status, border color reflects risk level, and an accent bar reflects priority. It also accepts `--export-options PATH` for CLI consistency, though the current table-column options affect the Word export table only.

## Export options

Export options files can be YAML, YML, or Python. The current supported settings are `task_table_attributes` and `task_table_columns`, which control the optional task attribute columns included in the Word export summary table. The `.docx` export always includes `Task` and `Project`; every other task metadata field in the table and per-task attribute narrative is limited to the attributes listed here.

Supported attribute names:

- `bnr`
- `cost`
- `funding` or `funding_status`
- `site`
- `type`
- `tags`

Simple YAML:

```yaml
task_table_attributes:
  - site
  - bnr
  - funding
  - tags
```

Shorthand YAML with custom labels:

```yaml
task_table_attributes:
  - bnr: BNR
  - funding: Status
  - tags: Keywords
```

Recommended explicit YAML when you need labels or alignment:

```yaml
task_table_columns:
  - attribute: bnr
    label: BNR
  - attribute: funding
    label: Status
  - attribute: tags
    label: Keywords
```

Supported column alignment values:

- `left`
- `center`
- `right`

`alignment` is optional and defaults to `center`.

Example CLI usage:

```bash
planner export-docx planner/examples/tasks.yaml /tmp/plan.docx --export-options planner/examples/export-options.yaml
```
