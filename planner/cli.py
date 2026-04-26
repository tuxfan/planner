from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from .exporters import write_docx, write_svg
from .loader import load_tasks
from .models import ValidationError, build_schedule


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple project planning system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("validate", "list", "summary", "schedule"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("task_file", help="Path to a YAML or Python task file")

    export_docx = subparsers.add_parser("export-docx")
    export_docx.add_argument("task_file", help="Path to a YAML or Python task file")
    export_docx.add_argument("output_file", help="Path to the .docx file to generate")

    export_svg = subparsers.add_parser("export-svg")
    export_svg.add_argument("task_file", help="Path to a YAML or Python task file")
    export_svg.add_argument("output_file", help="Path to the .svg file to generate")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        tasks = load_tasks(args.task_file)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"Validated {len(tasks)} task(s) from {args.task_file}.")
        return 0

    if args.command == "list":
        _print_tasks(tasks)
        return 0

    if args.command == "summary":
        _print_summary(tasks)
        return 0

    if args.command == "schedule":
        _print_schedule(tasks)
        return 0

    if args.command == "export-docx":
        output = write_docx(tasks, args.output_file)
        print(f"Wrote Word document to {output}.")
        return 0

    if args.command == "export-svg":
        output = write_svg(tasks, args.output_file)
        print(f"Wrote SVG plan to {output}.")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _print_tasks(tasks) -> None:
    for task in tasks:
        dependencies = ", ".join(task.dependencies) if task.dependencies else "-"
        print(
            f"{task.start_date.isoformat()} -> {task.due_date.isoformat()} | "
            f"{task.expected_duration} month(s) | {task.project} | {task.milestone} | "
            f"{task.priority} | risk={task.risk_level}/{task.risk_type} | "
            f"status={task.status} | {task.label} [{task.id}]"
        )
        print(f"  mitigation: {task.risk_mitigation}")
        print(f"  dependencies (ids): {dependencies}")
        print(f"  description: {task.description}")


def _print_summary(tasks) -> None:
    grouped = defaultdict(lambda: defaultdict(int))
    for task in tasks:
        grouped[task.project][task.milestone] += 1

    for project in sorted(grouped):
        print(project)
        for milestone in sorted(grouped[project]):
            print(f"  {milestone}: {grouped[project][milestone]} task(s)")


def _print_schedule(tasks) -> None:
    for position, state, task in build_schedule(tasks):
        dependencies = ", ".join(task.dependencies) if task.dependencies else "-"
        print(
            f"{position:02d} | {state} | start={task.start_date.isoformat()} | "
            f"due={task.due_date.isoformat()} | duration={task.expected_duration} month(s) | "
            f"status={task.status} | {task.label} [{task.id}]"
        )
        print(f"  project: {task.project}")
        print(f"  milestone: {task.milestone}")
        print(f"  risk: {task.risk_level}/{task.risk_type}")
        print(f"  mitigation: {task.risk_mitigation}")
        print(f"  dependencies (ids): {dependencies}")


if __name__ == "__main__":
    raise SystemExit(main())
