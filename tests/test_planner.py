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
                      - name: A
                        start date: 2026-04-01
                        due date: 2026-06-01
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
                      - name: B
                        start_date: 2026-05-01
                        due_date: 2026-06-02
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk_level: medium
                        risk_type: delivery
                        risk_mitigation: Keep the implementation slice small and testable.
                        status: todo
                        description: Second task.
                        project: Demo
                        dependencies: [A]
                    """
                ),
                encoding="utf-8",
            )

            tasks = load_tasks(path)

        self.assertEqual([task.name for task in tasks], ["A", "B"])
        self.assertEqual(tasks[0].start_date.isoformat(), "2026-04-01")
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
                    - name: A
                      start_date: 2026-05-01
                      due_date: 2026-06-01
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

    def test_rejects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.py"
            path.write_text(
                textwrap.dedent(
                    """
                    TASKS = [
                        {
                            "name": "A",
                            "start_date": "2026-05-01",
                            "due_date": "2026-06-01",
                            "expected_duration": 1,
                            "milestone": "Build",
                            "priority": "high",
                            "risk_level": "low",
                            "risk_type": "sequencing",
                            "risk_mitigation": "Resolve the dependency graph before execution.",
                            "status": "todo",
                            "description": "First task.",
                            "project": "Demo",
                            "dependencies": ["B"],
                        },
                        {
                            "name": "B",
                            "start_date": "2026-05-01",
                            "due_date": "2026-06-02",
                            "expected_duration": 1,
                            "milestone": "Build",
                            "priority": "medium",
                            "risk_level": "medium",
                            "risk_type": "sequencing",
                            "risk_mitigation": "Resolve the dependency graph before execution.",
                            "status": "todo",
                            "description": "Second task.",
                            "project": "Demo",
                            "dependencies": ["A"],
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
                    - name: A
                      start_date: 2026-05-01
                      due_date: 2026-06-01
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
                    - name: A
                      start_date: 2026-05-01
                      due_date: 2026-06-01
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

    def test_build_schedule_marks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tasks.yaml"
            path.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - name: A
                        start_date: 2026-05-01
                        due_date: 2026-06-01
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
                      - name: B
                        start_date: 2026-05-01
                        due_date: 2026-06-02
                        expected_duration: 1
                        milestone: Build
                        priority: high
                        risk_level: medium
                        risk_type: delivery
                        risk_mitigation: Keep the active work limited to one slice.
                        status: in_progress
                        description: Second task.
                        project: Demo
                        dependencies: [A]
                      - name: C
                        start_date: 2026-05-01
                        due_date: 2026-06-03
                        expected_duration: 1
                        milestone: Test
                        priority: medium
                        risk_level: medium
                        risk_type: quality
                        risk_mitigation: Wait for the implementation task to finish before testing.
                        status: todo
                        description: Third task.
                        project: Demo
                        dependencies: [B]
                    """
                ),
                encoding="utf-8",
            )

            schedule = build_schedule(load_tasks(path))

        self.assertEqual(
            [(step, state, task.name) for step, state, task in schedule],
            [(1, "COMPLETE", "A"), (2, "ACTIVE", "B"), (3, "BLOCKED", "C")],
        )

    def test_writes_word_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "tasks.yaml"
            source.write_text(
                textwrap.dedent(
                    """
                    tasks:
                      - name: A
                        start_date: 2026-04-01
                        due_date: 2026-06-01
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
        self.assertIn("Start Date", document)
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
                      - name: A
                        start_date: 2026-04-01
                        due_date: 2026-06-01
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
                      - name: B
                        start_date: 2026-05-01
                        due_date: 2026-06-02
                        expected_duration: 1
                        milestone: Build
                        priority: medium
                        risk_level: high
                        risk_type: delivery
                        risk_mitigation: Keep the implementation slice small and testable.
                        status: todo
                        description: Second task.
                        project: Demo
                        dependencies: [A]
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
        self.assertIn("duration 1 month(s)", svg)
        self.assertIn("risk high/delivery", svg)
        self.assertIn("marker-end=\"url(#arrow)\"", svg)


if __name__ == "__main__":
    unittest.main()
