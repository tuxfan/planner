from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .export_options import ExportOptions
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

DOCX_PAGE_WIDTH = 12240
DOCX_PAGE_HEIGHT = 15840
DOCX_MARGIN = 1440
DOCX_CONTENT_WIDTH = DOCX_PAGE_WIDTH - (DOCX_MARGIN * 2)
DOCX_BODY_FONT = "Aptos"
DOCX_DISPLAY_FONT = "Aptos Display"
DOCX_TEXT_COLOR = "000000"
DOCX_ACCENT_COLOR = "0F4761"
DOCX_BODY_SIZE = 24
DOCX_TITLE_SIZE = 40
DOCX_TABLE_SIZE = 20

TASK_TABLE_REQUIRED_COLUMNS = (
    ("Task", 800, lambda task, task_numbers, schedule_state: task_numbers[task.id]),
    ("Project", 1350, lambda task, task_numbers, schedule_state: task.project),
)

TASK_TABLE_ATTRIBUTE_COLUMNS = {
    "bnr": ("BNR", 750, lambda task: task.bnr or "-"),
    "cost": ("Cost", 650, lambda task: task.cost or "-"),
    "funding_status": ("Funding", 700, lambda task: task.funding_status or "-"),
    "type": ("Type", 700, lambda task: task.type or "-"),
    "tags": ("Tags", 900, lambda task: ", ".join(task.tags) if task.tags else "-"),
}


def write_docx(
    plan_or_tasks: ProjectPlan | list[Task],
    destination: str | Path,
    *,
    export_options: ExportOptions | None = None,
) -> Path:
    plan = _as_project_plan(plan_or_tasks)
    ordered = validate_tasks(plan.tasks)
    schedule = build_schedule(ordered)
    options = export_options or ExportOptions()
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _package_rels_xml())
        archive.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        archive.writestr(
            "word/document.xml",
            _document_xml(plan, ordered, schedule, options),
        )

    return output


def write_svg(
    plan_or_tasks: ProjectPlan | list[Task],
    destination: str | Path,
    *,
    export_options: ExportOptions | None = None,
) -> Path:
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
    plan: ProjectPlan,
    tasks: list[Task],
    schedule: list[tuple[int, str, Task]],
    export_options: ExportOptions,
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
                    _task_description(task, export_options),
                    style="ListParagraph",
                )
            )

    body.extend(
        [
            _paragraph("Resourcing/Schedule:", style="Heading1"),
            _paragraph("Task Summary Table:", style="Heading2"),
            _task_table(tasks, schedule, task_numbers, export_options),
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
    run_props = _style_run_props(style, bold=bold, underline=underline)
    p_props = _paragraph_props(style)
    return (
        f"<w:p>{p_props}<w:r>{run_props}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _labeled_paragraph(label: str, value: str, *, style: str | None = None) -> str:
    p_props = _paragraph_props(style)
    return (
        f"<w:p>{p_props}"
        f"<w:r>{_style_run_props(style, bold=True, underline=True)}<w:t xml:space=\"preserve\">{escape(label)}: </w:t></w:r>"
        f"<w:r>{_style_run_props(style)}<w:t xml:space=\"preserve\">{escape(value)}</w:t></w:r>"
        "</w:p>"
    )


def _run_props(
    *,
    bold: bool = False,
    underline: bool = False,
    size: int | None = None,
    font: str | None = None,
    color: str | None = None,
) -> str:
    props = []
    if font is not None:
        font = escape(font)
        props.append(f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}"/>')
    if bold:
        props.append("<w:b/><w:bCs/>")
    if underline:
        props.append('<w:u w:val="single"/>')
    if color is not None:
        props.append(f'<w:color w:val="{escape(color)}"/>')
    if size is not None:
        props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    return f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""


def _style_run_props(
    style: str | None = None, *, bold: bool = False, underline: bool = False
) -> str:
    if style == "Title":
        return _run_props(
            bold=bold,
            underline=underline,
            size=DOCX_TITLE_SIZE,
            font=DOCX_DISPLAY_FONT,
            color=DOCX_ACCENT_COLOR,
        )
    if style in {"Heading1", "Heading2"}:
        return _run_props(
            bold=True,
            underline=True,
            size=DOCX_BODY_SIZE,
            font=DOCX_BODY_FONT,
            color=DOCX_TEXT_COLOR,
        )
    return _run_props(
        bold=bold,
        underline=underline,
        size=DOCX_BODY_SIZE,
        font=DOCX_BODY_FONT,
        color=DOCX_TEXT_COLOR,
    )


def _paragraph_props(style: str | None = None) -> str:
    props = []
    if style:
        props.append(f'<w:pStyle w:val="{escape(style)}"/>')
    if style in {"Heading1", "Heading2"}:
        props.append("<w:keepNext/>")
    props.append('<w:spacing w:after="160" w:line="278" w:lineRule="auto"/>')
    if style == "ListParagraph":
        props.append('<w:ind w:left="720"/>')
    return f"<w:pPr>{''.join(props)}</w:pPr>"


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
    paragraphs = []
    if plan.execution_overview:
        paragraphs.extend(
            _paragraph(line) for line in _summary_lines(plan.execution_overview)
        )
    if plan.execution:
        paragraphs.extend(
            _labeled_paragraph(item.label, item.description, style="ListParagraph")
            for item in plan.execution
        )
        return paragraphs

    paragraphs.extend(
        [
            _labeled_paragraph(
                "Activities",
                _execution_summary(tasks),
            ),
            *_activity_paragraphs(tasks),
        ]
    )
    return paragraphs


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
    tasks: list[Task],
    schedule: list[tuple[int, str, Task]],
    task_numbers: dict[str, str],
    export_options: ExportOptions,
) -> str:
    schedule_state = {task.id: state for _, state, task in schedule}
    configured_columns = export_options.resolved_task_table_columns()
    columns = [
        *[
            (header, width, formatter, "left")
            for header, width, formatter in TASK_TABLE_REQUIRED_COLUMNS
        ],
        *[
            (
                column.label or header,
                width,
                lambda task,
                task_numbers,
                schedule_state,
                formatter=formatter: formatter(task),
                column.alignment,
            )
            for column in configured_columns
            for header, width, formatter in [TASK_TABLE_ATTRIBUTE_COLUMNS[column.attribute]]
        ],
    ]
    headers = [header for header, _, _, _ in columns]
    widths = _scaled_table_widths([width for _, width, _, _ in columns])
    alignments = [alignment for _, _, _, alignment in columns]
    rows = [_table_row(headers, widths, alignments, header=True)]
    for task in tasks:
        rows.append(
            _table_row(
                [
                    formatter(task, task_numbers, schedule_state)
                    for _, _, formatter, _ in columns
                ],
                widths,
                alignments,
            )
        )
    return (
        "<w:tbl>"
        "<w:tblPr>"
        f'<w:tblW w:w="{DOCX_CONTENT_WIDTH}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        '<w:tblLook w:firstRow="1" w:noHBand="0" w:noVBand="1"/>'
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\"/>"
        "</w:tblBorders></w:tblPr>"
        f"{_table_grid(widths)}"
        f"{''.join(rows)}"
        "</w:tbl>"
    )


def _scaled_table_widths(widths: list[int]) -> list[int]:
    total = sum(widths)
    if total <= 0:
        return widths

    scaled = [max(1, (width * DOCX_CONTENT_WIDTH) // total) for width in widths]
    scaled[-1] += DOCX_CONTENT_WIDTH - sum(scaled)
    return scaled


def _table_grid(widths: list[int]) -> str:
    columns = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    return f"<w:tblGrid>{columns}</w:tblGrid>"


def _dependency_numbers(task: Task, task_numbers: dict[str, str]) -> str:
    if not task.dependencies:
        return "None"
    return ", ".join(
        task_numbers.get(dependency, dependency) for dependency in task.dependencies
    )


def _task_description(
    task: Task, export_options: ExportOptions | None = None
) -> str:
    attributes = _task_attribute_summary(task, export_options)
    if not attributes:
        return task.description
    return f"{task.description} ({attributes})"


def _task_attribute_summary(
    task: Task, export_options: ExportOptions | None = None
) -> str:
    options = export_options or ExportOptions()
    parts = []
    if "bnr" in options.task_table_attributes and task.bnr:
        parts.append(f"BNR: {task.bnr}")
    if "cost" in options.task_table_attributes and task.cost:
        parts.append(f"Cost: {task.cost}")
    if "funding_status" in options.task_table_attributes and task.funding_status:
        parts.append(f"Funding: {task.funding_status}")
    if "type" in options.task_table_attributes and task.type:
        parts.append(f"Type: {task.type}")
    if "tags" in options.task_table_attributes and task.tags:
        parts.append("Tags: " + ", ".join(task.tags))
    return "; ".join(parts)


def _table_row(
    values: list[str],
    widths: list[int],
    alignments: list[str],
    *,
    header: bool = False,
) -> str:
    cells = "".join(
        _table_cell(value, width=width, alignment=alignment, header=header)
        for value, width, alignment in zip(values, widths, alignments)
    )
    return f"<w:tr>{cells}</w:tr>"


def _table_cell(
    value: str,
    *,
    width: int,
    alignment: str = "center",
    header: bool = False,
) -> str:
    run_props = _run_props(
        bold=header,
        size=DOCX_TABLE_SIZE,
        font=DOCX_BODY_FONT,
        color=DOCX_TEXT_COLOR,
    )
    paragraph_alignment = _paragraph_alignment_xml(alignment)
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
        f"<w:p>{paragraph_alignment}<w:r>{run_props}<w:t xml:space=\"preserve\">{escape(value)}</w:t></w:r></w:p></w:tc>"
    )


def _paragraph_alignment_xml(alignment: str) -> str:
    return (
        f'<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
        f'<w:jc w:val="{alignment}"/></w:pPr>'
    )


def _section_properties() -> str:
    return (
        "<w:sectPr>"
        f'<w:pgSz w:w="{DOCX_PAGE_WIDTH}" w:h="{DOCX_PAGE_HEIGHT}"/>'
        f'<w:pgMar w:top="{DOCX_MARGIN}" w:right="{DOCX_MARGIN}" w:bottom="{DOCX_MARGIN}" w:left="{DOCX_MARGIN}" w:header="720" w:footer="720" w:gutter="0"/>'
        '<w:cols w:space="720"/>'
        '<w:docGrid w:linePitch="360"/>'
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
