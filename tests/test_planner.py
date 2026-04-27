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
from planner.exporters import write_docx, write_svg
from planner.loader import load_tasks
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
        self.assertEqual(tasks[0].risk_type, "dependency")
        self.assertEqual(
            tasks[0].risk_mitigation,
            "Close prerequisite questions before build starts.",
        )

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
                    """
                ),
                encoding="utf-8",
            )
            destination = Path(tmpdir) / "plan.docx"

            write_docx(load_tasks(source), destination)

            self.assertTrue(destination.exists())
            with ZipFile(destination) as archive:
                document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn("Project Plan", document)
        self.assertIn("Start", document)
        self.assertIn("Deadline", document)
        self.assertIn("Expected Duration", document)
        self.assertIn("2 month(s)", document)
        self.assertIn("Risk Mitigation", document)
        self.assertIn("Finish the prerequisite task first.", document)

    def test_writes_svg_plan(self) -> None:
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

            write_svg(load_tasks(source), destination)

            self.assertTrue(destination.exists())
            svg = destination.read_text(encoding="utf-8")

        self.assertIn("<svg", svg)
        self.assertIn("Project Plan", svg)
        self.assertIn("M1Q3FY26 to M3Q3FY26", svg)
        self.assertIn("duration 1 month(s)", svg)
        self.assertIn("risk high/delivery", svg)
        self.assertIn("marker-end=\"url(#arrow)\"", svg)
        self.assertIn("id B2", svg)


if __name__ == "__main__":
    unittest.main()
