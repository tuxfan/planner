from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .models import ProjectPlan, Task, build_schedule, validate_tasks


STATUS_COLORS = {
    "pending": "#F9E2AE",
    "active": "#A9D6E5",
    "ongoing": "#CDB4DB",
    "blocked": "#F4A6A6",
    "complete": "#B7E4C7",
}

RISK_COLORS = {
    "low": "#2D6A4F",
    "medium": "#FFEA00",
    "high": "#BC6C25",
    "extreme": "#AE2012",
}

PRIORITY_COLORS = {
    "low": "#ADB5BD",
    "medium": "#3A86FF",
    "high": "#6A040F",
    "urgent": "#D00000",
}


def write_docx(plan_or_tasks: ProjectPlan | list[Task], destination: str | Path) -> Path:
    plan = _as_project_plan(plan_or_tasks)
    ordered = validate_tasks(plan.tasks)
    schedule = build_schedule(ordered)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _package_rels_xml())
        archive.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        archive.writestr("word/document.xml", _document_xml(plan, ordered, schedule))

    return output


def write_svg(plan_or_tasks: ProjectPlan | list[Task], destination: str | Path) -> Path:
    plan = _as_project_plan(plan_or_tasks)
    ordered = validate_tasks(plan.tasks)
    schedule = build_schedule(ordered)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_svg_document(plan, ordered, schedule), encoding="utf-8")
    return output


def _as_project_plan(plan_or_tasks: ProjectPlan | list[Task]) -> ProjectPlan:
    if isinstance(plan_or_tasks, ProjectPlan):
        return plan_or_tasks
    return ProjectPlan(tasks=tuple(plan_or_tasks))


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""


def _package_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


def _document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def _document_xml(
    plan: ProjectPlan, tasks: list[Task], schedule: list[tuple[int, str, Task]]
) -> str:
    task_numbers = _task_numbers(tasks)
    body = [
        _paragraph(f"Project Title: {plan.title}", style="Title"),
    ]
    body.extend(_metadata_paragraphs(plan))
    body.extend(
        [
            _paragraph("Execution:", style="Heading1"),
            *_execution_paragraphs(plan, tasks),
            _paragraph("Tasks:", style="Heading1"),
        ]
    )

    for project in _project_order(tasks):
        project_tasks = [task for task in tasks if task.project == project]
        body.append(_paragraph(project, style="Heading2"))
        for task in project_tasks:
            number = task_numbers[task.id]
            body.append(
                _labeled_paragraph(
                    f"{number} {task.label}",
                    _task_description(task),
                    style="ListParagraph",
                )
            )

    body.extend(
        [
            _paragraph("Resourcing/Schedule:", style="Heading1"),
            _paragraph("Task Summary Table:", style="Heading2"),
            _task_table(tasks, schedule, task_numbers),
            _paragraph("Risk Mitigation:", style="Heading1"),
            *_risk_mitigation_paragraphs(tasks, task_numbers),
        ]
    )

    return (
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n"""
        """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">"""
        f"<w:body>{''.join(body)}{_section_properties()}</w:body></w:document>"
    )


def _metadata_paragraphs(plan: ProjectPlan) -> list[str]:
    body: list[str] = []
    if plan.project:
        body.append(_labeled_paragraph("Project", plan.project))
    if plan.portfolio:
        body.append(_labeled_paragraph("Federal Portfolio(s)", plan.portfolio))
    if plan.managers:
        body.append(
            _labeled_paragraph("Federal Program Manager(s)", " / ".join(plan.managers))
        )
    if plan.pocs:
        body.append(_paragraph("Project Points of Contact:", bold=True, underline=True))
        body.extend(_paragraph(poc, style="ListParagraph") for poc in plan.pocs)
    if plan.summary:
        body.extend(
            [
                _paragraph("Project Summary:", style="Heading1"),
                *[_paragraph(line) for line in _summary_lines(plan.summary)],
            ]
        )
    return body


def _summary_lines(summary: str) -> list[str]:
    return [line.strip() for line in summary.splitlines() if line.strip()]


def _paragraph(
    text: str, *, style: str | None = None, bold: bool = False, underline: bool = False
) -> str:
    style_xml = f'<w:pStyle w:val="{escape(style)}"/>' if style else ""
    run_props = _run_props(bold=bold, underline=underline)
    p_props = f"<w:pPr>{style_xml}</w:pPr>" if style_xml else ""
    return (
        f"<w:p>{p_props}<w:r>{run_props}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _labeled_paragraph(label: str, value: str, *, style: str | None = None) -> str:
    style_xml = f'<w:pStyle w:val="{escape(style)}"/>' if style else ""
    p_props = f"<w:pPr>{style_xml}</w:pPr>" if style_xml else ""
    return (
        f"<w:p>{p_props}"
        f"<w:r>{_run_props(bold=True, underline=True)}<w:t xml:space=\"preserve\">{escape(label)}: </w:t></w:r>"
        f"<w:r><w:t xml:space=\"preserve\">{escape(value)}</w:t></w:r>"
        "</w:p>"
    )


def _run_props(
    *, bold: bool = False, underline: bool = False, size: int | None = None
) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if underline:
        props.append('<w:u w:val="single"/>')
    if size is not None:
        props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    return f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""


def _project_order(tasks: list[Task]) -> list[str]:
    projects: list[str] = []
    for task in tasks:
        if task.project not in projects:
            projects.append(task.project)
    return projects


def _project_letters(tasks: list[Task]) -> dict[str, str]:
    return {
        project: chr(ord("A") + index)
        for index, project in enumerate(_project_order(tasks))
    }


def _task_numbers(tasks: list[Task]) -> dict[str, str]:
    project_letters = _project_letters(tasks)
    counts = {project: 0 for project in project_letters}
    numbers = {}
    for task in tasks:
        counts[task.project] += 1
        numbers[task.id] = f"Task {project_letters[task.project]}.{counts[task.project]}"
    return numbers


def _execution_summary(tasks: list[Task]) -> str:
    projects = _project_order(tasks)
    if not projects:
        return "No activities are defined."
    if len(projects) == 1:
        return f"{projects[0]} provides the planned project activity."
    return (
        ", ".join(projects[:-1])
        + f", and {projects[-1]} provide the planned project activities."
    )


def _execution_paragraphs(plan: ProjectPlan, tasks: list[Task]) -> list[str]:
    if plan.execution:
        return [
            _labeled_paragraph(item.label, item.description, style="ListParagraph")
            for item in plan.execution
        ]

    return [
        _labeled_paragraph(
            "Activities",
            _execution_summary(tasks),
        ),
        *_activity_paragraphs(tasks),
    ]


def _activity_paragraphs(tasks: list[Task]) -> list[str]:
    paragraphs = []
    project_letters = _project_letters(tasks)
    for project in _project_order(tasks):
        project_tasks = [task for task in tasks if task.project == project]
        task_count = len(project_tasks)
        milestones = sorted({task.milestone for task in project_tasks if task.milestone})
        milestone_text = ", ".join(milestones) if milestones else "unspecified milestones"
        paragraphs.append(
            _paragraph(
                f"Activity {project_letters[project]}: {project} includes {task_count} task(s) covering {milestone_text}.",
                style="ListParagraph",
            )
        )
    return paragraphs


def _risk_mitigation_paragraphs(
    tasks: list[Task], task_numbers: dict[str, str]
) -> list[str]:
    return [
        _labeled_paragraph(task_numbers[task.id], task.risk_mitigation)
        for task in tasks
        if task.risk_mitigation
    ]


def _task_table(
    tasks: list[Task], schedule: list[tuple[int, str, Task]], task_numbers: dict[str, str]
) -> str:
    schedule_state = {task.id: state for _, state, task in schedule}
    headers = [
        "Task",
        "Project",
        "Start",
        "Deadline",
        "Duration",
        "Status",
        "BNR",
        "Cost",
        "Funding",
        "Type",
        "Priority",
        "Risk",
        "Schedule",
        "Dependencies",
    ]
    widths = [800, 1350, 650, 650, 650, 750, 750, 650, 700, 700, 800, 750, 800, 900]
    rows = [_table_row(headers, widths, header=True)]
    for task in tasks:
        rows.append(
            _table_row(
                [
                    task_numbers[task.id],
                    task.project,
                    task.start,
                    task.deadline,
                    f"{task.expected_duration} mo.",
                    task.status,
                    task.bnr or "-",
                    task.cost or "-",
                    task.funding_status or "-",
                    task.type or "-",
                    task.priority,
                    f"{task.risk_level}/{task.risk_type}",
                    schedule_state[task.id],
                    _dependency_numbers(task, task_numbers),
                ],
                widths,
            )
        )
    return (
        "<w:tbl>"
        "<w:tblPr>"
        '<w:tblW w:w="0" w:type="auto"/>'
        '<w:tblLook w:firstRow="1" w:noHBand="0" w:noVBand="1"/>'
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\"/>"
        "</w:tblBorders></w:tblPr>"
        f"{''.join(rows)}"
        "</w:tbl>"
    )


def _dependency_numbers(task: Task, task_numbers: dict[str, str]) -> str:
    if not task.dependencies:
        return "None"
    return ", ".join(
        task_numbers.get(dependency, dependency) for dependency in task.dependencies
    )


def _task_description(task: Task) -> str:
    attributes = _task_attribute_summary(task)
    if not attributes:
        return task.description
    return f"{task.description} ({attributes})"


def _task_attribute_summary(task: Task) -> str:
    parts = []
    if task.bnr:
        parts.append(f"BNR: {task.bnr}")
    if task.cost:
        parts.append(f"Cost: {task.cost}")
    if task.funding_status:
        parts.append(f"Funding: {task.funding_status}")
    if task.type:
        parts.append(f"Type: {task.type}")
    if task.tags:
        parts.append("Tags: " + ", ".join(task.tags))
    return "; ".join(parts)


def _table_row(values: list[str], widths: list[int], *, header: bool = False) -> str:
    cells = "".join(
        _table_cell(value, width=width, header=header)
        for value, width in zip(values, widths)
    )
    return f"<w:tr>{cells}</w:tr>"


def _table_cell(value: str, *, width: int, header: bool = False) -> str:
    run_props = _run_props(bold=header, size=18)
    shading = '<w:shd w:fill="D9EAF7"/>' if header else ""
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shading}</w:tcPr>'
        f"<w:p><w:r>{run_props}<w:t xml:space=\"preserve\">{escape(value)}</w:t></w:r></w:p></w:tc>"
    )


def _section_properties() -> str:
    return (
        "<w:sectPr>"
        '<w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )


def _svg_document(
    plan: ProjectPlan, tasks: list[Task], schedule: list[tuple[int, str, Task]]
) -> str:
    project_order = sorted({task.project for task in tasks})
    lanes = {project: index for index, project in enumerate(project_order)}
    card_width = 260
    card_height = 178
    left_padding = 170
    top_padding = 110
    x_gap = 120
    y_gap = 50
    width = left_padding + len(schedule) * (card_width + x_gap) + 80
    height = top_padding + max(1, len(project_order)) * (card_height + y_gap) + 100
    positions = {}
    for position, state, task in schedule:
        x = left_padding + (position - 1) * (card_width + x_gap)
        y = top_padding + lanes[task.project] * (card_height + y_gap)
        positions[task.id] = (x, y, state)

    elements = [
        f'<rect width="{width}" height="{height}" fill="#F8F5F0"/>',
        f'<text x="40" y="48" font-family="Georgia, serif" font-size="28" fill="#1D3557">{escape(plan.title)}</text>',
        '<text x="40" y="76" font-family="Arial, sans-serif" font-size="14" fill="#4A4E69">Fill color = status, border = risk level, accent bar = priority</text>',
    ]

    for project, lane in lanes.items():
        y = top_padding + lane * (card_height + y_gap)
        elements.append(
            f'<text x="40" y="{y + 38}" font-family="Arial, sans-serif" font-size="16" font-weight="700" fill="#264653">{escape(project)}</text>'
        )
        elements.append(
            f'<line x1="{left_padding - 20}" y1="{y + card_height + 18}" x2="{width - 40}" y2="{y + card_height + 18}" stroke="#D9D9D9" stroke-dasharray="4 6"/>'
        )

    for _, _, task in schedule:
        x, y, _ = positions[task.id]
        start_x = x
        start_y = y + card_height / 2
        for dependency in task.dependencies:
            dep_x, dep_y, _ = positions[dependency]
            end_x = dep_x + card_width
            end_y = dep_y + card_height / 2
            elements.append(
                f'<path d="M {end_x} {end_y} C {end_x + 40} {end_y}, {start_x - 40} {start_y}, {start_x} {start_y}" stroke="#6C757D" stroke-width="2.5" fill="none" marker-end="url(#arrow)"/>'
            )

    for position, state, task in schedule:
        x, y, _ = positions[task.id]
        fill = STATUS_COLORS.get(task.status, "#FFFFFF")
        stroke = RISK_COLORS.get(task.risk_level.lower(), "#495057")
        accent = PRIORITY_COLORS.get(task.priority.lower(), "#495057")
        dependencies = ", ".join(task.dependencies) if task.dependencies else "None"
        attributes = _task_attribute_summary(task)
        description = _wrap_text(task.description, 34)[:2]
        text_y = y + 28
        elements.extend(
            [
                f'<g id="{_slug(task.id)}">',
                f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="4"/>',
                f'<rect x="{x}" y="{y}" width="12" height="{card_height}" rx="12" fill="{accent}"/>',
                f'<text x="{x + 22}" y="{text_y}" font-family="Arial, sans-serif" font-size="12" font-weight="700" fill="#495057">{position:02d} {escape(state)}</text>',
                f'<text x="{x + 22}" y="{text_y + 22}" font-family="Georgia, serif" font-size="18" font-weight="700" fill="#1D3557">{escape(task.label)}</text>',
                f'<text x="{x + 22}" y="{text_y + 40}" font-family="Arial, sans-serif" font-size="11" fill="#495057">id {escape(task.id)}</text>',
                f'<text x="{x + 22}" y="{text_y + 58}" font-family="Arial, sans-serif" font-size="12" fill="#343A40">{escape(task.milestone)} | {task.start} to {task.deadline}</text>',
                f'<text x="{x + 22}" y="{text_y + 76}" font-family="Arial, sans-serif" font-size="12" fill="#343A40">duration {task.expected_duration} month(s)</text>',
                f'<text x="{x + 22}" y="{text_y + 94}" font-family="Arial, sans-serif" font-size="12" fill="#343A40">risk {escape(task.risk_level)}/{escape(task.risk_type)}</text>',
                f'<text x="{x + 22}" y="{text_y + 112}" font-family="Arial, sans-serif" font-size="12" fill="#343A40">deps {escape(dependencies)}</text>',
            ]
        )
        if attributes:
            elements.append(
                f'<text x="{x + 22}" y="{text_y + 130}" font-family="Arial, sans-serif" font-size="11" fill="#343A40">{escape(attributes)}</text>'
            )
        for index, line in enumerate(description):
            elements.append(
                f'<text x="{x + 22}" y="{text_y + 148 + index * 14}" font-family="Arial, sans-serif" font-size="11" fill="#495057">{escape(line)}</text>'
            )
        elements.append("</g>")

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#6C757D"/></marker></defs>'
        + "".join(elements)
        + "</svg>"
    )


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
