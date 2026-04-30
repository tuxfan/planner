from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from .export_options import load_export_options
from .exporters import write_docx, write_svg
from .loader import load_plan
from .models import ValidationError, build_schedule

TASK_FILE_ENV_VAR = "TUXFAN_PLANNER_DATAFILE"
EXPORT_OPTIONS_ENV_VAR = "TUXFAN_PLANNER_EXPORT_OPTIONS"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple project planning system")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("validate", "list", "summary", "schedule"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "task_file",
            nargs="?",
            help=(
                "Path to a YAML or Python task file. Optional when "
                f"{TASK_FILE_ENV_VAR} is set."
            ),
        )

    export_docx = subparsers.add_parser("export-docx")
    export_docx.add_argument(
        "task_file",
        nargs="?",
        help=(
            "Path to a YAML or Python task file. Optional when "
            f"{TASK_FILE_ENV_VAR} is set and only the output path is passed."
        ),
    )
    export_docx.add_argument(
        "output_file",
        nargs="?",
        help="Path to the .docx file to generate",
    )
    export_docx.add_argument(
        "--export-options",
        dest="export_options",
        help=(
            "Path to a YAML or Python export options file. Optional when "
            f"{EXPORT_OPTIONS_ENV_VAR} is set."
        ),
    )

    export_svg = subparsers.add_parser("export-svg")
    export_svg.add_argument(
        "task_file",
        nargs="?",
        help=(
            "Path to a YAML or Python task file. Optional when "
            f"{TASK_FILE_ENV_VAR} is set and only the output path is passed."
        ),
    )
    export_svg.add_argument(
        "output_file",
        nargs="?",
        help="Path to the .svg file to generate",
    )
    export_svg.add_argument(
        "--export-options",
        dest="export_options",
        help=(
            "Path to a YAML or Python export options file. Optional when "
            f"{EXPORT_OPTIONS_ENV_VAR} is set."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    task_file, output_file = _resolve_paths(args, parser)
    export_options = _resolve_export_options(args)

    try:
        plan = load_plan(task_file)
        tasks = list(plan.tasks)
        options = (
            load_export_options(export_options) if export_options is not None else None
        )
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"Validated {len(tasks)} task(s) from {task_file}.")
        _print_plan_metadata(plan)
        return 0

    if args.command == "list":
        _print_plan_metadata(plan)
        _print_tasks(tasks)
        return 0

    if args.command == "summary":
        _print_plan_metadata(plan)
        _print_summary(tasks)
        return 0

    if args.command == "schedule":
        _print_plan_metadata(plan)
        _print_schedule(tasks)
        return 0

    if args.command == "export-docx":
        output = write_docx(plan, output_file, export_options=options)
        print(f"Wrote Word document to {output}.")
        return 0

    if args.command == "export-svg":
        output = write_svg(plan, output_file, export_options=options)
        print(f"Wrote SVG plan to {output}.")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _resolve_paths(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[str, str | None]:
    task_file_from_env = os.getenv(TASK_FILE_ENV_VAR)

    if args.command in {"validate", "list", "summary", "schedule"}:
        task_file = args.task_file or task_file_from_env
        if task_file is None:
            parser.error(
                f"task_file is required unless {TASK_FILE_ENV_VAR} is set."
            )
        return task_file, None

    if args.command in {"export-docx", "export-svg"}:
        if args.output_file is not None:
            task_file = args.task_file or task_file_from_env
            if task_file is None:
                parser.error(
                    f"task_file is required for {args.command} unless "
                    f"{TASK_FILE_ENV_VAR} is set."
                )
            return task_file, args.output_file

        if args.task_file is not None and task_file_from_env is not None:
            return task_file_from_env, args.task_file

        if args.task_file is None:
            parser.error(f"output_file is required for {args.command}.")

        parser.error(
            f"{args.command} requires both task_file and output_file unless "
            f"{TASK_FILE_ENV_VAR} is set."
        )

    parser.error(f"Unknown command: {args.command}")
    raise AssertionError("parser.error should have exited")


def _resolve_export_options(args: argparse.Namespace) -> str | None:
    if args.command not in {"export-docx", "export-svg"}:
        return None
    export_options_from_env = os.getenv(EXPORT_OPTIONS_ENV_VAR)
    if export_options_from_env is not None and args.export_options is not None:
        print(
            f"warning: both --export-options and {EXPORT_OPTIONS_ENV_VAR} are set; "
            f"using {EXPORT_OPTIONS_ENV_VAR}.",
            file=sys.stderr,
        )
    return export_options_from_env or args.export_options


def _print_plan_metadata(plan) -> None:
    if not any(
        (
            plan.project,
            plan.portfolio,
            plan.managers,
            plan.pocs,
            plan.summary,
            plan.execution,
        )
    ):
        return
    if plan.project:
        print(f"Project: {plan.project}")
    if plan.portfolio:
        print(f"Portfolio: {plan.portfolio}")
    if plan.managers:
        print("Managers: " + ", ".join(plan.managers))
    if plan.pocs:
        print("POCs: " + ", ".join(plan.pocs))
    if plan.summary:
        print("Summary:")
        for line in plan.summary.splitlines():
            if line.strip():
                print(f"  {line.strip()}")
    if plan.execution:
        print("Execution:")
        for item in plan.execution:
            print(f"  {item.label}:")
            for line in item.description.splitlines():
                if line.strip():
                    print(f"    {line.strip()}")
    print()


def _print_tasks(tasks) -> None:
    for task in tasks:
        dependencies = ", ".join(task.dependencies) if task.dependencies else "-"
        metadata = _task_metadata(task)
        print(
            f"{task.start} -> {task.deadline} | "
            f"{task.expected_duration} month(s) | {task.project} | {task.milestone} | "
            f"{task.priority} | risk={task.risk_level}/{task.risk_type} | "
            f"status={task.status} | {task.label} [{task.id}]"
        )
        if metadata:
            print(f"  attributes: {metadata}")
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
        metadata = _task_metadata(task)
        print(
            f"{position:02d} | {state} | start={task.start} | "
            f"deadline={task.deadline} | duration={task.expected_duration} month(s) | "
            f"status={task.status} | {task.label} [{task.id}]"
        )
        print(f"  project: {task.project}")
        print(f"  milestone: {task.milestone}")
        if metadata:
            print(f"  attributes: {metadata}")
        print(f"  risk: {task.risk_level}/{task.risk_type}")
        print(f"  mitigation: {task.risk_mitigation}")
        print(f"  dependencies (ids): {dependencies}")


def _task_metadata(task) -> str:
    parts = []
    if task.bnr:
        parts.append(f"bnr={task.bnr}")
    if task.cost:
        parts.append(f"cost={task.cost}")
    if task.funding_status:
        parts.append(f"funding={task.funding_status}")
    if task.type:
        parts.append(f"type={task.type}")
    if task.tags:
        parts.append("tags=" + ", ".join(task.tags))
    return " | ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
