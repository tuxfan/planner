from __future__ import annotations

import io
import tempfile
import textwrap
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from planner.cli import main
from planner.export_options import ExportOptions, TaskTableColumn, load_export_options
from planner.exporters import write_docx, write_svg
from planner.loader import load_plan, load_tasks
from planner.models import ValidationError, build_schedule


class PlannerTests(unittest.TestCase):
    def test_declares_planner_console_script(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["scripts"]["planner"], "planner.cli:main")
        self.assertEqual(
            data["project"]["scripts"]["tuxfan-planner"],
            "planner.cli:main",
        )

    def test_loads_yaml_with_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding status: funded
                        site: LANL
                        type: labor
                        tags:
                          - gpu
                          - restart
                        start: m1q3fy26
                        deadline: M3Q3FY26
                        expected duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Close prerequisite questions before build starts.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: B2
                        label: B
                        funding_status: proposed
                        tags: integration, parser
                        start: M2Q3FY26
                        deadline: m3q3fy26
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk:
                          - type: delivery
                            level: medium
                            mitigation: Keep the implementation slice small and testable.
                        status: pending
                        description: Second task.
                        project: Demo
                        dependencies: [A1]
                    """
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)

        self.assertEqual([task.label for task in tasks], ["A", "B"])
        self.assertEqual([task.id for task in tasks], ["A1", "B2"])
        self.assertEqual(tasks[0].start, "M1Q3FY26")
        self.assertEqual(tasks[0].deadline, "M3Q3FY26")
        self.assertEqual(tasks[0].expected_duration, 2)
        self.assertEqual(tasks[0].bnr, "DP1518130")
        self.assertEqual(tasks[0].cost, "$100K")
        self.assertEqual(tasks[0].funding_status, "funded")
        self.assertEqual(tasks[0].site, "LANL")
        self.assertEqual(tasks[0].type, "labor")
        self.assertEqual(tasks[0].tags, ("gpu", "restart"))
        self.assertEqual(tasks[1].funding_status, "proposed")
        self.assertEqual(tasks[1].tags, ("integration", "parser"))
        self.assertEqual(tasks[0].risks[0].type, "dependency")
        self.assertEqual(
            tasks[0].risks[0].mitigation,
            "Close prerequisite questions before build starts.",
        )

    def test_loads_yaml_with_canonical_risk_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: VTK
                      label: VTK Support
                      site: LANL
                      bnr: DP1518130
                      type: labor
                      tags: []
                      project: Task-Parallel Specializations
                      description: >
                        Add VTK I/O support for unstructured mesh input.
                      start: M1Q1FY26
                      deadline: M1Q1FY26
                      expected duration: 1
                      milestone: Unassigned
                      priority: medium
                      status: active
                      dependencies: []
                      risk:
                        - type: technical
                          level: low
                          mitigation: >
                            Work with viz team.
                        - type: schedule
                          level: medium
                          mitigation: >
                            Add additional staffing.
                      funding:
                        fy27: 50K
                        fy28: 100K
                        fy29: 200K
                        fy30: 50K
                        fy31: 3000K
                    """
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)

        self.assertEqual([task.id for task in tasks], ["VTK"])
        self.assertEqual(tasks[0].risks[0].type, "technical")
        self.assertEqual(tasks[0].risks[0].level, "low")
        self.assertEqual(tasks[0].risks[0].mitigation, "Work with viz team.")
        self.assertEqual(tasks[0].risks[1].type, "schedule")
        self.assertEqual(tasks[0].risks[1].level, "medium")
        self.assertEqual(tasks[0].risks[1].mitigation, "Add additional staffing.")
        self.assertEqual(tasks[0].risks[0].type, "technical")
        self.assertEqual(tasks[0].risks[0].level, "low")
        self.assertEqual(tasks[0].funding["FY31"], "3000K")

    def test_loads_fiscal_range_and_task_funding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    fiscal_range_begin: 27
                    fiscal_range_end: 29
                    tasks:
                      - id: A1
                        label: A
                        funding:
                          fy27: 50K
                          FY29: 1M
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep the task small.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            plan = load_plan(path)

        self.assertEqual(plan.fiscal_years, ("FY27", "FY28", "FY29"))
        self.assertEqual(plan.tasks[0].funding, {"FY27": "50K", "FY29": "1M"})

    def test_loads_yaml_plan_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    portfolio: Advanced Simulation and Computing
                    project: Task-Parallel Project
                    managers:
                      - Alice
                      - Bob
                    pocs:
                      - Casey, PI
                    summary: >
                      High-level planning context for the task collection.
                    execution:
                      - label: Deliverable A
                        description: >
                          Narrative execution detail for the deliverable.
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M1Q3FY26
                        expected_duration: 1
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep the task small.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            plan = load_plan(path)
            tasks = load_tasks(path)

        self.assertEqual(plan.project, "Task-Parallel Project")
        self.assertEqual(plan.portfolio, "Advanced Simulation and Computing")
        self.assertEqual(plan.managers, ("Alice", "Bob"))
        self.assertEqual(plan.pocs, ("Casey, PI",))
        self.assertEqual(
            plan.summary,
            "High-level planning context for the task collection.",
        )
        self.assertEqual(len(plan.execution), 1)
        self.assertEqual(plan.execution[0].label, "Deliverable A")
        self.assertEqual(
            plan.execution[0].description,
            "Narrative execution detail for the deliverable.",
        )
        self.assertEqual([task.id for task in plan.tasks], ["A1"])
        self.assertEqual([task.id for task in tasks], ["A1"])

    def test_loads_execution_overview_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    execution:
                      overview: >
                        Overall execution context for the plan.
                      sections:
                        - label: Deliverable A
                          description: >
                            Narrative execution detail for the deliverable.
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M1Q3FY26
                        expected_duration: 1
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep the task small.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            plan = load_plan(path)

        self.assertEqual(
            plan.execution_overview, "Overall execution context for the plan."
        )
        self.assertEqual(len(plan.execution), 1)
        self.assertEqual(plan.execution[0].label, "Deliverable A")
        self.assertEqual(
            plan.execution[0].description,
            "Narrative execution detail for the deliverable.",
        )

    def test_loads_python_plan_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.py"
            path.write_text(
                textwrap.dedent(
                    """
                    PLAN = {
                        "portfolio": "Portfolio A",
                        "managers": ["Alice"],
                        "pocs": ["Casey"],
                        "summary": "Python plan metadata.",
                        "execution": [
                            {
                                "label": "Execution A",
                                "description": "Python execution detail.",
                            }
                        ],
                        "tasks": [
                            {
                                "id": "A1",
                                "label": "A",
                                "start": "M1Q3FY26",
                                "deadline": "M1Q3FY26",
                                "expected_duration": 1,
                                "milestone": "Design",
                                "priority": "high",
                                "risk": [{"type": "dependency", "level": "low", "mitigation": "Keep the task small."}],
                                "status": "pending",
                                "description": "First task.",
                                "project": "Demo",
                                "dependencies": [],
                            }
                        ],
                    }
                    """
                ),
                encoding="utf-8",
            )

            plan = load_plan(path)

        self.assertEqual(plan.portfolio, "Portfolio A")
        self.assertEqual(plan.managers, ("Alice",))
        self.assertEqual(plan.pocs, ("Casey",))
        self.assertEqual(plan.summary, "Python plan metadata.")
        self.assertEqual(plan.execution[0].label, "Execution A")
        self.assertEqual(plan.execution[0].description, "Python execution detail.")

    def test_loads_repository_data_file(self) -> None:
        path = Path(__file__).resolve().parents[1] / "data" / "tasks.yaml"

        plan = load_plan(path)

        self.assertEqual(plan.portfolio, "Example Portfolio")
        self.assertIn("Manager One", plan.managers)
        self.assertIn("Contact Two, PI", plan.pocs)
        self.assertGreater(len(plan.summary), 0)
        self.assertGreater(len(plan.tasks), 0)

    def test_loads_repository_ristra_execution_data(self) -> None:
        path = Path(__file__).resolve().parents[1] / "data" / "ristra.yaml"

        plan = load_plan(path)

        self.assertEqual(plan.portfolio, "Example Portfolio")
        self.assertEqual(
            [item.label for item in plan.execution],
            [
                "Restart Capability",
                "Mutator Support",
                "Multi-Material Structures",
                "Execution Model Updates",
            ],
        )
        self.assertIn("Delivery: June 1st, 2026.", plan.execution[0].description)
        self.assertGreater(len(plan.tasks), 0)

    def test_rejects_invalid_execution_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    execution:
                      - label: Missing Description
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M1Q3FY26
                        expected_duration: 1
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep the task small.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_plan(path)

    def test_rejects_missing_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      risk:
                        - type: dependency
                          level: low
                          mitigation: Confirm all upstream work exists in the file.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: [Missing]
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_invalid_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: bad id
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      risk:
                        - type: dependency
                          level: low
                          mitigation: Use a compact identifier for dependency tracking.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_accepts_underscore_in_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A_1
                        label: A
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep dependency ids aligned with task ids.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: B_2
                        label: B
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk:
                          - type: dependency
                            level: medium
                            mitigation: Keep dependency ids aligned with task ids.
                        status: pending
                        description: Second task.
                        project: Demo
                        dependencies: [A_1]
                    """
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)

        self.assertEqual([task.id for task in tasks], ["A_1", "B_2"])
        self.assertEqual(tasks[1].dependencies, ("A_1",))

    def test_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep ids unique.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: A1
                        label: B
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk:
                          - type: delivery
                            level: medium
                            mitigation: Keep ids unique.
                        status: pending
                        description: Second task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.py"
            path.write_text(
                textwrap.dedent(
                    """
                    TASKS = [
                        {
                            "id": "A1",
                            "label": "A",
                            "start": "M2Q3FY26",
                            "deadline": "M3Q3FY26",
                            "expected_duration": 1,
                            "milestone": "Build",
                            "priority": "high",
                            "risk": [{"type": "sequencing", "level": "low", "mitigation": "Resolve the dependency graph before execution."}],
                            "status": "pending",
                            "description": "First task.",
                            "project": "Demo",
                            "dependencies": ["B2"],
                        },
                        {
                            "id": "B2",
                            "label": "B",
                            "start": "M2Q3FY26",
                            "deadline": "M3Q3FY26",
                            "expected_duration": 1,
                            "milestone": "Build",
                            "priority": "medium",
                            "risk": [{"type": "sequencing", "level": "medium", "mitigation": "Resolve the dependency graph before execution."}],
                            "status": "pending",
                            "description": "Second task.",
                            "project": "Demo",
                            "dependencies": ["A1"],
                        },
                    ]
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Use a supported status value.
                      status: stalled
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_accepts_ongoing_status_urgent_priority_and_extreme_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: urgent
                      risk:
                        - type: delivery
                          level: extreme
                          mitigation: Escalate immediately and review daily.
                      status: ongoing
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)
            schedule = build_schedule(tasks)

        self.assertEqual(tasks[0].priority, "urgent")
        self.assertEqual(tasks[0].risks[0].level, "extreme")
        self.assertEqual(tasks[0].status, "ongoing")
        self.assertEqual(schedule[0][1], "ONGOING")

    def test_rejects_invalid_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: asap
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Use a supported priority value.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_invalid_risk_entry_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      risk:
                        - type: delivery
                          level: severe
                          mitigation: Use a supported risk level value.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_missing_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_invalid_expected_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q3FY26
                      deadline: M3Q3FY26
                      expected_duration: 0
                      milestone: Build
                      priority: high
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Use a positive whole number of months.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_invalid_fiscal_period(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: Month5
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Use a valid fiscal period code.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_rejects_start_after_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M2Q4FY26
                      deadline: M3Q3FY26
                      expected_duration: 1
                      milestone: Build
                      priority: high
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Keep the fiscal period sequence valid.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValidationError):
                load_tasks(path)

    def test_build_schedule_marks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: B2
                        label: B
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: high
                        risk:
                          - type: delivery
                            level: medium
                            mitigation: Keep the active work limited to one slice.
                        status: active
                        description: Second task.
                        project: Demo
                        dependencies: [A1]
                      - id: C3
                        label: C
                        start: M3Q3FY26
                        deadline: M1Q4FY26
                        expected_duration: 1
                        milestone: Test
                        priority: medium
                        risk:
                          - type: quality
                            level: medium
                            mitigation: Wait for the implementation task to finish before testing.
                        status: pending
                        description: Third task.
                        project: Demo
                        dependencies: [B2]
                    """
                ),
                encoding="utf-8",
            )

            schedule = build_schedule(load_tasks(path))

        self.assertEqual(
            [(step, state, task.label) for step, state, task in schedule],
            [(1, "COMPLETE", "A"), (2, "ACTIVE", "B"), (3, "BLOCKED", "C")],
        )

    def test_cli_validate_uses_env_task_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M1Q3FY26
                      deadline: M1Q3FY26
                      expected_duration: 1
                      milestone: Design
                      priority: high
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Keep the validation path simple.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                patch.dict("os.environ", {"TUXFAN_PLANNER_DATAFILE": str(path)}),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = main(["validate"])

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(f"Validated 1 task(s) from {path}.", stdout.getvalue())

    def test_cli_validate_requires_task_file_without_env(self) -> None:
        stderr = io.StringIO()

        with (
            patch.dict("os.environ", {}, clear=True),
            redirect_stderr(stderr),
            self.assertRaises(SystemExit) as excinfo,
        ):
            main(["validate"])

        self.assertEqual(excinfo.exception.code, 2)
        self.assertIn(
            "task_file is required unless TUXFAN_PLANNER_DATAFILE is set.",
            stderr.getvalue(),
        )

    def test_cli_prints_bash_completion_script(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(["completion", "bash"])

        output = stdout.getvalue()
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("validate list summary schedule export-docx export-svg", output)
        self.assertIn("complete -o default -F _planner_completion planner", output)
        self.assertIn(
            "complete -o default -F _planner_completion tuxfan-planner",
            output,
        )

    def test_cli_prints_fish_completion_script(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(["completion", "fish"])

        output = stdout.getvalue()
        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(
            "complete -c planner -n '__fish_use_subcommand' -a validate",
            output,
        )
        self.assertIn(
            "complete -c tuxfan-planner -n '__fish_use_subcommand' -a schedule",
            output,
        )
        self.assertIn("-l export-options", output)

    def test_cli_export_svg_uses_env_task_file_with_output_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    - id: A1
                      label: A
                      start: M1Q3FY26
                      deadline: M1Q3FY26
                      expected_duration: 1
                      milestone: Design
                      priority: high
                      risk:
                        - type: delivery
                          level: low
                          mitigation: Keep the export path simple.
                      status: pending
                      description: First task.
                      project: Demo
                      dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.svg"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                patch.dict(
                    "os.environ",
                    {"TUXFAN_PLANNER_DATAFILE": str(source)},
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = main(["export-svg", str(destination)])

            self.assertEqual(result, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(destination.exists())
            self.assertIn(f"Wrote SVG plan to {destination}.", stdout.getvalue())

    def test_loads_export_options_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "export-options.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    task_table_attributes:
                      - site
                      - funding
                      - tags
                      - funding_status
                    """
                ),
                encoding="utf-8",
            )

            options = load_export_options(path)

        self.assertEqual(
            options,
            ExportOptions(
                task_table_attributes=("site", "funding_status", "tags"),
                task_table_columns=(
                    TaskTableColumn(attribute="site", alignment="center"),
                    TaskTableColumn(attribute="funding_status", alignment="center"),
                    TaskTableColumn(attribute="tags", alignment="center"),
                ),
            ),
        )

    def test_loads_export_options_with_column_labels_and_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "export-options.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    task_table_attributes:
                      - site: Site
                      - bnr: BNR
                      - funding:
                          label: Status
                          alignment: center
                      - tags
                    """
                ),
                encoding="utf-8",
            )

            options = load_export_options(path)

        self.assertEqual(
            options,
            ExportOptions(
                task_table_attributes=("site", "bnr", "funding_status", "tags"),
                task_table_columns=(
                    TaskTableColumn(attribute="site", label="Site", alignment="center"),
                    TaskTableColumn(attribute="bnr", label="BNR", alignment="center"),
                    TaskTableColumn(
                        attribute="funding_status",
                        label="Status",
                        alignment="center",
                    ),
                    TaskTableColumn(attribute="tags", alignment="center"),
                ),
            ),
        )

    def test_writes_word_document_with_custom_table_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        site: LANL
                        type: labor
                        tags: checkpoint, restart
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"

            write_docx(
                load_plan(source),
                destination,
                export_options=ExportOptions(
                    task_table_attributes=("funding_status", "tags"),
                    task_table_columns=(
                        TaskTableColumn(
                            attribute="funding_status",
                            label="Status",
                            alignment="center",
                        ),
                        TaskTableColumn(attribute="tags"),
                    ),
                ),
            )

            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn('<w:t xml:space="preserve">Status</w:t>', document)
        self.assertIn('<w:jc w:val="center"/>', document)
        self.assertNotIn("<w:textDirection", document)
        self.assertIn('<w:t xml:space="preserve">Tags</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">BNR</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Cost</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Funding</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Type</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Start</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Deadline</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Duration</w:t>', document)
        self.assertNotIn("BNR: DP1518130", document)
        self.assertNotIn("Cost: $100K", document)
        self.assertIn("Funding: funded", document)
        self.assertNotIn("Type: labor", document)
        self.assertIn("Tags: checkpoint, restart", document)
        self.assertIn('<w:tblW w:w="9360" w:type="dxa"/>', document)
        self.assertIn('<w:tblLayout w:type="fixed"/>', document)
        self.assertIn(
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"',
            document,
        )
        self.assertIn('<w:pgSz w:w="12240" w:h="15840"/>', document)
        self.assertIn('<w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/>', document)
        self.assertIn('<w:color w:val="000000"/>', document)

    def test_cli_export_docx_uses_env_export_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        type: labor
                        tags:
                          - checkpoint
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            options_path = Path(tmpdir) / "export-options.yaml"
            options_path.write_text(
                textwrap.dedent(
                    """
                    task_table_attributes:
                      - tags
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                patch.dict(
                    "os.environ",
                    {
                        "TUXFAN_PLANNER_DATAFILE": str(source),
                        "TUXFAN_PLANNER_EXPORT_OPTIONS": str(options_path),
                    },
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = main(["export-docx", str(destination)])

            self.assertEqual(result, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(destination.exists())
            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn(f"Wrote Word document to {destination}.", stdout.getvalue())
        self.assertIn('<w:t xml:space="preserve">Tags</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">BNR</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Start</w:t>', document)
        self.assertIn("Tags: checkpoint", document)
        self.assertNotIn("BNR: DP1518130", document)

    def test_cli_export_docx_accepts_export_options_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        type: labor
                        tags:
                          - checkpoint
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            options_path = Path(tmpdir) / "export-options.yaml"
            options_path.write_text(
                textwrap.dedent(
                    """
                    task_table_attributes:
                      - tags
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"

            result = main(
                [
                    "export-docx",
                    str(source),
                    str(destination),
                    "--export-options",
                    str(options_path),
                ]
            )

            self.assertEqual(result, 0)
            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn('<w:t xml:space="preserve">Tags</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">BNR</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Start</w:t>', document)
        self.assertIn("Tags: checkpoint", document)
        self.assertNotIn("BNR: DP1518130", document)

    def test_cli_export_docx_env_export_options_override_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        type: labor
                        tags:
                          - checkpoint
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            cli_options_path = Path(tmpdir) / "cli-export-options.yaml"
            cli_options_path.write_text(
                textwrap.dedent(
                    """
                    task_table_attributes:
                      - tags
                    """
                ),
                encoding="utf-8",
            )
            env_options_path = Path(tmpdir) / "env-export-options.yaml"
            env_options_path.write_text(
                textwrap.dedent(
                    """
                    task_table_attributes:
                      - bnr
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                patch.dict(
                    "os.environ",
                    {"TUXFAN_PLANNER_EXPORT_OPTIONS": str(env_options_path)},
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "export-docx",
                        str(source),
                        str(destination),
                        "--export-options",
                        str(cli_options_path),
                    ]
                )

            self.assertEqual(result, 0)
            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn('<w:t xml:space="preserve">BNR</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Tags</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Start</w:t>', document)
        self.assertIn("BNR: DP1518130", document)
        self.assertNotIn("Tags: checkpoint", document)
        self.assertIn(
            "warning: both --export-options and TUXFAN_PLANNER_EXPORT_OPTIONS are set; "
            "using TUXFAN_PLANNER_EXPORT_OPTIONS.",
            stderr.getvalue(),
        )

    def test_orders_deadlines_across_fiscal_year_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: October kickoff
                        start: M1Q1FY27
                        deadline: M1Q1FY27
                        expected_duration: 1
                        milestone: Launch
                        priority: medium
                        risk:
                          - type: delivery
                            level: low
                            mitigation: Keep the kickoff scope narrow.
                        status: pending
                        description: First task in FY27.
                        project: Demo
                        dependencies: []
                      - id: B2
                        label: September close
                        start: M3Q4FY26
                        deadline: M3Q4FY26
                        expected_duration: 1
                        milestone: Wrap-up
                        priority: medium
                        risk:
                          - type: delivery
                            level: low
                            mitigation: Close the FY26 work before rollover.
                        status: pending
                        description: Final task in FY26.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)

        self.assertEqual([task.id for task in tasks], ["B2", "A1"])

    def test_writes_word_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    portfolio: Portfolio A
                    managers:
                      - Alice
                      - Bob
                    pocs:
                      - Casey
                      - Drew
                    fiscal_range_begin: 27
                    fiscal_range_end: 29
                    summary: >
                      Document-level planning context.
                    execution:
                      overview: >
                        Document execution overview.
                      sections:
                        - label: Deliverable A
                          description: >
                            Document execution detail.
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        funding:
                          fy27: 50K
                          fy29: 1M
                        site: LANL
                        type: labor
                        tags: checkpoint, restart
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: LONG_IDENTIFIER_FOR_TABLE
                        label: B
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk:
                          - type: schedule
                            level: medium
                            mitigation: Track the prerequisite task.
                        status: active
                        description: Second task.
                        project: Other
                        dependencies:
                          - A1
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"

            write_docx(load_plan(source), destination)

            self.assertTrue(destination.exists())
            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn("Portfolio A", document)
        self.assertIn("Project: Portfolio A", document)
        self.assertNotIn("Project Title", document)
        self.assertIn("Federal Portfolio(s)", document)
        self.assertIn("Federal Program Manager(s)", document)
        self.assertIn("Alice", document)
        self.assertIn("Bob", document)
        self.assertNotIn("Alice / Bob", document)
        self.assertIn("Project Points of Contact", document)
        self.assertIn("Casey", document)
        self.assertIn("Drew", document)
        self.assertIn("Document-level planning context.", document)
        self.assertIn("Fiscal Years", document)
        self.assertIn("FY27, FY28, FY29", document)
        self.assertIn("Funding Totals", document)
        self.assertIn("FY27: 50K", document)
        self.assertIn("FY28: 0K", document)
        self.assertIn("FY29: 1000K", document)
        self.assertIn("Execution", document)
        self.assertIn("Document execution overview.", document)
        self.assertIn("Deliverable A", document)
        self.assertIn("Document execution detail.", document)
        self.assertIn("Tasks", document)
        self.assertIn("Resourcing/Schedule", document)
        self.assertIn('<w:t xml:space="preserve">Task</w:t>', document)
        self.assertIn('<w:t xml:space="preserve">Project</w:t>', document)
        self.assertIn("Task A.1", document)
        self.assertIn("Task B.1", document)
        self.assertNotIn("LONG_IDENTIFIER_FOR_TABLE", document)
        self.assertIn("Site", document)
        self.assertIn("LANL", document)
        self.assertIn("BNR", document)
        self.assertIn("DP1518130", document)
        self.assertIn("Cost", document)
        self.assertIn("$100K", document)
        self.assertIn("Funding", document)
        self.assertIn("funded", document)
        self.assertIn('<w:t xml:space="preserve">FY27</w:t>', document)
        self.assertIn('<w:t xml:space="preserve">FY28</w:t>', document)
        self.assertIn('<w:t xml:space="preserve">FY29</w:t>', document)
        self.assertIn('<w:t xml:space="preserve">50K</w:t>', document)
        self.assertIn('<w:t xml:space="preserve">1M</w:t>', document)
        self.assertIn("Type", document)
        self.assertIn("labor", document)
        self.assertNotIn("Tags", document)
        self.assertNotIn("checkpoint, restart", document)
        self.assertNotIn('<w:t xml:space="preserve">Start</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Deadline</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Duration</w:t>', document)
        self.assertIn("Risk Mitigation", document)
        self.assertIn("Finish the prerequisite task first.", document)

    def test_docx_metadata_people_are_not_joined_or_indented(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    managers:
                      - Alice
                      - Bob
                    pocs:
                      - Casey
                      - Drew
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M1Q3FY26
                        expected_duration: 1
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep the task small.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"

            write_docx(load_plan(source), destination)

            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        def paragraph_containing(text: str) -> str:
            marker = f'<w:t xml:space="preserve">{text}</w:t>'
            return next(
                paragraph for paragraph in document.split("<w:p>") if marker in paragraph
            )

        self.assertNotIn("Alice / Bob", document)
        for name in ["Alice", "Bob", "Casey", "Drew"]:
            paragraph = paragraph_containing(name)
            self.assertNotIn('<w:pStyle w:val="ListParagraph"/>', paragraph)
            self.assertNotIn('<w:ind w:left="720"/>', paragraph)

    def test_docx_uses_tight_body_paragraph_spacing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M1Q3FY26
                        expected_duration: 1
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Keep the task small.
                        status: pending
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"

            write_docx(load_plan(source), destination)

            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn(
            '<w:spacing w:after="80" w:line="240" w:lineRule="auto"/>',
            document,
        )
        self.assertNotIn(
            '<w:spacing w:after="160" w:line="278" w:lineRule="auto"/>',
            document,
        )

    def test_writes_svg_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    portfolio: Portfolio A
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk:
                          - type: dependency
                            level: low
                            mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: B2
                        label: B
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        site: LANL
                        type: labor
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk:
                          - type: delivery
                            level: high
                            mitigation: Keep the implementation slice small and testable.
                        status: pending
                        description: Second task.
                        project: Demo
                        dependencies: [A1]
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.svg"

            write_svg(load_plan(source), destination)

            self.assertTrue(destination.exists())
            svg = destination.read_text(encoding="utf-8")

        self.assertIn("<svg", svg)
        self.assertIn("Portfolio A", svg)
        self.assertIn("M1Q3FY26 to M3Q3FY26", svg)
        self.assertIn("duration 1 month(s)", svg)
        self.assertIn(
            "Site: LANL; BNR: DP1518130; Cost: $100K; Funding: funded; Type: labor",
            svg,
        )
        self.assertIn("risk high/delivery", svg)
        self.assertIn("marker-end=\"url(#arrow)\"", svg)
        self.assertIn("id B2", svg)

    def test_writes_svg_plan_for_ongoing_urgent_extreme_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - id: A1
                        label: A
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: urgent
                        risk:
                          - type: delivery
                            level: extreme
                            mitigation: Escalate immediately and review daily.
                        status: ongoing
                        description: First task.
                        project: Demo
                        dependencies: []
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.svg"

            write_svg(load_tasks(source), destination)

            svg = destination.read_text(encoding="utf-8")

        self.assertIn("01 ONGOING", svg)
        self.assertIn("risk extreme/delivery", svg)
        self.assertIn('fill="#CDB4DB"', svg)
        self.assertIn('fill="#D00000"', svg)

    def test_loads_ristra_task_attributes(self) -> None:
        source = Path(__file__).resolve().parents[1] / "data" / "ristra.yaml"

        plan = load_plan(source)

        self.assertGreater(len(plan.tasks), 0)
        self.assertTrue(all(task.bnr == "ANON-BNR-001" for task in plan.tasks))
        self.assertEqual(
            sorted(task.cost for task in plan.tasks),
            ["$100K", "$100K", "$100K", "$200K", "$400K", "$400K"],
        )
        self.assertTrue(all(task.funding_status == "funded" for task in plan.tasks))
        self.assertTrue(all(task.type == "labor" for task in plan.tasks))
        self.assertTrue(all(task.tags == () for task in plan.tasks))


if __name__ == "__main__":
    unittest.main()
