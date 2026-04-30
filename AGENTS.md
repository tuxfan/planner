# Project Context

## Purpose

This repository is a small Python project planning tool packaged as `project-planner`.
It loads task definitions from YAML or Python files, validates them, prints summaries and dependency-aware schedules, and exports plans to `.docx` and `.svg`.

## Current Scope

- Runtime: Python 3.11+
- Packaging: setuptools via `pyproject.toml`
- Dependency: `PyYAML>=6.0`
- CLI entry point: `project-planner = planner.cli:main`
- Example data: `planner/examples/tasks.yaml` and `planner/examples/tasks.py`
- Top-level plan metadata: `portfolio`, `project`, `managers`, `pocs`, `summary`, and `execution`
- Optional task metadata: `bnr`, `cost`, `funding_status`, `type`, and `tags`

## Repository Map

- `README.md`: usage, supported task schema, CLI commands, examples
- `pyproject.toml`: package metadata and console script
- `planner/cli.py`: argparse CLI for validate, list, summary, schedule, export-docx, export-svg
- `planner/loader.py`: loads YAML or Python task sources and normalizes top-level task collections
- `planner/models.py`: `Task` dataclass, field alias handling, validation rules, schedule construction
- `planner/exporters.py`: `.docx` and `.svg` export generation
- `tests/test_planner.py`: unit tests for loading, validation, scheduling, and exporters

## Data Model Notes

Plan files can be a raw task list or a mapping with `tasks` plus optional metadata:

- `portfolio`: portfolio or parent program name
- `project`: high-level project name
- `managers`: list of manager names
- `pocs`: list of point-of-contact names
- `summary`: high-level plan summary
- `execution`: list of execution/deliverable narratives with `label` and `description`

Each task includes:

- `id`, `label`
- `bnr`, `cost`, `funding_status`, `type`, `tags`
- `start`, `deadline`
- `expected_duration`
- `milestone`, `priority`
- `risk_level`, `risk_type`, `risk_mitigation`
- `status`, `description`, `project`
- `dependencies`

Accepted aliases currently handled in code:

- `bnr` -> `bnr`
- `cost` -> `cost`
- `start` -> `start`
- `start month` -> `start`
- `deadline` -> `deadline`
- `deadline month` -> `deadline`
- `expected duration` -> `expected_duration`
- `funding status` -> `funding_status`
- `risk level` -> `risk_level`
- `risk type` -> `risk_type`
- `risk mitigation` -> `risk_mitigation`
- `tags` -> `tags`
- `type` -> `type`

Validation rules currently enforced:

- required fields must all be present
- task ids must match `^[A-Za-z0-9_]+$`
- `dependencies` must be a list
- `start` and `deadline` must use fiscal period values like `M1Q1FY26`
- `expected_duration` must be a positive integer
- `start` cannot be after `deadline` in fiscal period order
- `status` must be one of `pending`, `active`, `ongoing`, `blocked`, `complete`
- dependency ids must exist
- dependency cycles are rejected
- validated task output is sorted by deadline month, project, label, id

## Behavioral Notes

- `list` prints task details in validated sort order.
- `summary` groups counts by project and milestone.
- `schedule` uses dependency order and emits `COMPLETE`, `ACTIVE`, `READY`, or `BLOCKED`.
- `export-docx` writes a minimal Word document directly as zipped XML, using a reference-style narrative plan layout with execution narratives and compact per-project task numbers in the summary table.
- `export-svg` renders project lanes, dependency arrows, and task cards with status/risk/priority colors.
- `load_plan()` returns a `ProjectPlan` with validated tasks plus optional metadata; `load_tasks()` remains as a backward-compatible task-list wrapper.

## Working Conventions For Future Sessions

- Update this file after meaningful prompts, code changes, or architecture decisions.
- Keep the `Session Log` append-only unless a correction is required.
- Record decisions and observed repo state, not speculative plans unless they were explicitly discussed.
- If behavior changes, update both the relevant section above and the log entry below.

## Open Observations

- The codebase is intentionally small and self-contained.
- Export generation is implemented without external document/SVG libraries beyond the standard library and PyYAML.
- Tests appear to focus on validation edge cases and exporter output generation.

## Session Log

### 2026-04-26

- Created `.context.md` at the repository root to serve as persistent working context across coding sessions.
- Captured the current project purpose, module boundaries, task schema, validation rules, CLI commands, and exporter behavior from the checked-in source and README.
- Initial instruction for future updates: treat this file as a maintained context snapshot plus prompt-aware change log.
- Renamed the scheduling fields from `start_date`/`due_date` to `start`/`deadline`.
- Changed `start` and `deadline` parsing from ISO dates to full month names, with internal month-order comparison for validation and sorting.
- Updated README, examples, CLI output, exporters, and tests to use the new month-based schema.

### 2026-04-27

- Confirmed the persistent session/context file has been renamed from `.context.md` to `AGENTS.md`.
- Updated the working convention for future sessions to maintain `AGENTS.md` as the canonical context log file.

### 2026-04-28

- Added support for plan-level metadata in YAML and Python sources through a new `ProjectPlan` model and `load_plan()` loader.
- Preserved backward compatibility by keeping `load_tasks()` as a task-list wrapper around `load_plan()`.
- Updated CLI output and `.docx`/`.svg` exports to include plan metadata when present.
- Added tests for metadata loading from YAML/Python, exporter output, and validation of `data/tasks.yaml`.
- Updated `.docx` export formatting to more closely match `data/example.docx`: title/metadata labels, project summary, execution/activity sections, grouped task descriptions, a landscape task summary table, and a risk mitigation section.
- Replaced raw task ids in the `.docx` table and dependency display with generated per-project task numbers such as `Task A.1`, avoiding layout issues from long ids.

### 2026-04-30

- Added first-class support for top-level `execution` metadata as a list of labeled narrative items.
- Updated YAML/Python loading, CLI metadata output, `.docx` execution rendering, README documentation, and tests for `data/ristra.yaml`.
- Added first-class optional task attributes from `data/ristra.yaml`: `bnr`, `funding_status`, `type`, and `tags`.
- Threaded the new task attributes through YAML/Python loading, CLI list/schedule output, `.docx` task descriptions and summary tables, `.svg` task cards, README documentation, and unit coverage.
- Added first-class optional `cost` task metadata from `data/ristra.yaml`, including CLI/export rendering, README documentation, and tests.
- Added optional export configuration file support for export commands through `--export-options` or `TUXFAN_PLANNER_EXPORT_OPTIONS`.
- Added validated export table column selection for `.docx` task summary tables, with configurable optional attributes `bnr`, `cost`, `funding_status`, `type`, and `tags`.
- Added `planner/examples/export-options.yaml`, README documentation, and unit coverage for both CLI and direct exporter usage of export options.
