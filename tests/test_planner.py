from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from zipfile import ZipFile

from planner.exporters import write_docx, write_svg
from planner.loader import load_tasks
from planner.models import ValidationError, build_schedule


class PlannerTests(unittest.TestCase):
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
                        status: done
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
                        status: todo
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
                      status: todo
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
                      status: todo
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
                        status: todo
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
                        status: todo
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
                            "status": "todo",
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
                            "status": "todo",
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
                      status: todo
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
                      status: todo
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
                      status: todo
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
                        status: done
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
                        status: in_progress
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
                        status: todo
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
                        status: todo
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
                        status: todo
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
                        status: done
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
                        status: done
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
                        status: todo
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
