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
from planner.export_options import ExportOptions, load_export_options
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
                        type: labor
                        tags:
                          - gpu
                          - restart
                        start: m1q3fy26
                        deadline: M3Q3FY26
                        expected duration: 2
                        milestone: Design
                        priority: high
                        risk level: low
                        risk type: dependency
                        risk mitigation: Close prerequisite questions before build starts.
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
                        risk_level: medium
                        risk_type: delivery
                        risk_mitigation: Keep the implementation slice small and testable.
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
        self.assertEqual(tasks[0].type, "labor")
        self.assertEqual(tasks[0].tags, ("gpu", "restart"))
        self.assertEqual(tasks[1].funding_status, "proposed")
        self.assertEqual(tasks[1].tags, ("integration", "parser"))
        self.assertEqual(tasks[0].risk_type, "dependency")
        self.assertEqual(
            tasks[0].risk_mitigation,
            "Close prerequisite questions before build starts.",
        )

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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Keep the task small.
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

        self.assertEqual(plan.title, "Task-Parallel Project")
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
                                "risk_level": "low",
                                "risk_type": "dependency",
                                "risk_mitigation": "Keep the task small.",
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

        self.assertEqual(plan.portfolio, "Advanced Simulation and Computing (NA-114)")
        self.assertIn("Simon Hammond", plan.managers)
        self.assertIn("Ben Bergen, PI", plan.pocs)
        self.assertGreater(len(plan.summary), 0)
        self.assertGreater(len(plan.tasks), 0)

    def test_loads_repository_ristra_execution_data(self) -> None:
        path = Path(__file__).resolve().parents[1] / "data" / "ristra.yaml"

        plan = load_plan(path)

        self.assertEqual(plan.portfolio, "Advanced Simulation and Computing (NA-114)")
        self.assertEqual(
            [item.label for item in plan.execution],
            [
                "Checkpoint/Restart",
                "Device Mutator Support",
                "Multi-Material Data Structures",
                "Execution Model Enhancements",
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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Keep the task small.
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
                      risk_level: low
                      risk_type: dependency
                      risk_mitigation: Confirm all upstream work exists in the file.
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
                      risk_level: low
                      risk_type: dependency
                      risk_mitigation: Use a compact identifier for dependency tracking.
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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Keep dependency ids aligned with task ids.
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
                        risk_level: medium
                        risk_type: dependency
                        risk_mitigation: Keep dependency ids aligned with task ids.
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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Keep ids unique.
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
                        risk_level: medium
                        risk_type: delivery
                        risk_mitigation: Keep ids unique.
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
                            "risk_level": "low",
                            "risk_type": "sequencing",
                            "risk_mitigation": "Resolve the dependency graph before execution.",
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
                            "risk_level": "medium",
                            "risk_type": "sequencing",
                            "risk_mitigation": "Resolve the dependency graph before execution.",
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Use a supported status value.
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

    def test_accepts_ongoing_status_urgent_priority_and_extreme_risk_level(self) -> None:
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
                      risk_level: extreme
                      risk_type: delivery
                      risk_mitigation: Escalate immediately and review daily.
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
        self.assertEqual(tasks[0].risk_level, "extreme")
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Use a supported priority value.
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

    def test_rejects_invalid_risk_level(self) -> None:
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
                      risk_level: severe
                      risk_type: delivery
                      risk_mitigation: Use a supported risk level value.
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Use a positive whole number of months.
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Use a valid fiscal period code.
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Keep the fiscal period sequence valid.
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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
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
                        risk_level: medium
                        risk_type: delivery
                        risk_mitigation: Keep the active work limited to one slice.
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
                        risk_level: medium
                        risk_type: quality
                        risk_mitigation: Wait for the implementation task to finish before testing.
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Keep the validation path simple.
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
                      risk_level: low
                      risk_type: delivery
                      risk_mitigation: Keep the export path simple.
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
            ExportOptions(task_table_attributes=("funding_status", "tags")),
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
                        type: labor
                        tags: checkpoint, restart
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
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
                export_options=ExportOptions(task_table_attributes=("tags",)),
            )

            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn('<w:t xml:space="preserve">Tags</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">BNR</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Cost</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Funding</w:t>', document)
        self.assertNotIn('<w:t xml:space="preserve">Type</w:t>', document)

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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
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
                        risk_level: low
                        risk_type: delivery
                        risk_mitigation: Keep the kickoff scope narrow.
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
                        risk_level: low
                        risk_type: delivery
                        risk_mitigation: Close the FY26 work before rollover.
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
                    pocs:
                      - Casey
                    summary: >
                      Document-level planning context.
                    execution:
                      - label: Deliverable A
                        description: >
                          Document execution detail.
                    tasks:
                      - id: A1
                        label: A
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        type: labor
                        tags: checkpoint, restart
                        start: M1Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 2
                        milestone: Design
                        priority: high
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
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
                        risk_level: medium
                        risk_type: schedule
                        risk_mitigation: Track the prerequisite task.
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
        self.assertIn("Federal Portfolio(s)", document)
        self.assertIn("Federal Program Manager(s)", document)
        self.assertIn("Alice", document)
        self.assertIn("Project Points of Contact", document)
        self.assertIn("Document-level planning context.", document)
        self.assertIn("Execution", document)
        self.assertIn("Deliverable A", document)
        self.assertIn("Document execution detail.", document)
        self.assertIn("Tasks", document)
        self.assertIn("Resourcing/Schedule", document)
        self.assertIn("Task A.1", document)
        self.assertIn("Task B.1", document)
        self.assertNotIn("LONG_IDENTIFIER_FOR_TABLE", document)
        self.assertIn("BNR", document)
        self.assertIn("DP1518130", document)
        self.assertIn("Cost", document)
        self.assertIn("$100K", document)
        self.assertIn("Funding", document)
        self.assertIn("funded", document)
        self.assertIn("Type", document)
        self.assertIn("labor", document)
        self.assertIn("Tags: checkpoint, restart", document)
        self.assertIn("Start", document)
        self.assertIn("Deadline", document)
        self.assertIn("Duration", document)
        self.assertIn("2 mo.", document)
        self.assertIn("Risk Mitigation", document)
        self.assertIn("Finish the prerequisite task first.", document)

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
                        risk_level: low
                        risk_type: dependency
                        risk_mitigation: Finish the prerequisite task first.
                        status: complete
                        description: First task.
                        project: Demo
                        dependencies: []
                      - id: B2
                        label: B
                        bnr: DP1518130
                        cost: $100K
                        funding_status: funded
                        type: labor
                        start: M2Q3FY26
                        deadline: M3Q3FY26
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk_level: high
                        risk_type: delivery
                        risk_mitigation: Keep the implementation slice small and testable.
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
        self.assertIn("BNR: DP1518130; Cost: $100K; Funding: funded; Type: labor", svg)
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
                        risk_level: extreme
                        risk_type: delivery
                        risk_mitigation: Escalate immediately and review daily.
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
        self.assertTrue(all(task.bnr == "DP1518130" for task in plan.tasks))
        self.assertEqual(
            sorted(task.cost for task in plan.tasks),
            ["$100K", "$100K", "$100K", "$200K", "$400K", "$400K"],
        )
        self.assertTrue(all(task.funding_status == "funded" for task in plan.tasks))
        self.assertTrue(all(task.type == "labor" for task in plan.tasks))
        self.assertTrue(all(task.tags == () for task in plan.tasks))


if __name__ == "__main__":
    unittest.main()
