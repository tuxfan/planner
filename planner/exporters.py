from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .models import Task, build_schedule, validate_tasks


STATUS_COLORS = {
    "pending": "#F9E2AE",
    "active": "#A9D6E5",
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
}


def write_docx(tasks: list[Task], destination: str | Path) -> Path:
    ordered = validate_tasks(tasks)
    schedule = build_schedule(ordered)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _package_rels_xml())
        archive.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        archive.writestr("word/document.xml", _document_xml(ordered, schedule))

    return output


def write_svg(tasks: list[Task], destination: str | Path) -> Path:
    ordered = validate_tasks(tasks)
    schedule = build_schedule(ordered)
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_svg_document(ordered, schedule), encoding="utf-8")
    return output


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
    tasks: list[Task], schedule: list[tuple[int, str, Task]]
) -> str:
    body = [
        _paragraph("Project Plan", style="Title"),
        _paragraph(f"Task count: {len(tasks)}"),
        _paragraph("Execution Schedule", style="Heading1"),
    ]

    for position, state, task in schedule:
        body.extend(
            [
                _paragraph(f"{position}. {task.label} [{task.id}]", style="Heading2"),
                _paragraph(
                    f"State: {state} | Start: {task.start} | "
                    f"Deadline: {task.deadline} | Duration: {task.expected_duration} month(s)"
                ),
                _paragraph(
                    f"Project: {task.project} | Milestone: {task.milestone}"
                ),
                _paragraph(
                    f"Priority: {task.priority} | Risk: {task.risk_level}/{task.risk_type}"
                ),
                _paragraph(f"Mitigation: {task.risk_mitigation}"),
                _paragraph(
                    "Dependencies (ids): "
                    + (", ".join(task.dependencies) if task.dependencies else "None")
                ),
                _paragraph(f"Description: {task.description}"),
            ]
        )

    body.append(_paragraph("Task Details", style="Heading1"))
    body.append(_task_table(tasks))

    return (
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n"""
        """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">"""
        f"<w:body>{''.join(body)}<w:sectPr/></w:body></w:document>"
    )


def _paragraph(text: str, *, style: str | None = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{escape(style)}"/></w:pPr>' if style else ""
    return (
        f"<w:p>{style_xml}<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _task_table(tasks: list[Task]) -> str:
    headers = [
        "ID",
        "Label",
        "Start",
        "Deadline",
        "Expected Duration",
        "Project",
        "Milestone",
        "Priority",
        "Status",
        "Risk Level",
        "Risk Type",
        "Risk Mitigation",
        "Dependencies",
    ]
    rows = [_table_row(headers, header=True)]
    for task in tasks:
        rows.append(
            _table_row(
                [
                    task.id,
                    task.label,
                    task.start,
                    task.deadline,
                    f"{task.expected_duration} month(s)",
                    task.project,
                    task.milestone,
                    task.priority,
                    task.status,
                    task.risk_level,
                    task.risk_type,
                    task.risk_mitigation,
                    ", ".join(task.dependencies) if task.dependencies else "None",
                ]
            )
        )
    return (
        "<w:tbl>"
        "<w:tblPr><w:tblBorders>"
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


def _table_row(values: list[str], *, header: bool = False) -> str:
    cells = "".join(_table_cell(value, header=header) for value in values)
    return f"<w:tr>{cells}</w:tr>"


def _table_cell(value: str, *, header: bool = False) -> str:
    run_props = "<w:rPr><w:b/></w:rPr>" if header else ""
    return (
        "<w:tc><w:p><w:r>"
        f"{run_props}<w:t xml:space=\"preserve\">{escape(value)}</w:t>"
        "</w:r></w:p></w:tc>"
    )


def _svg_document(
    tasks: list[Task], schedule: list[tuple[int, str, Task]]
) -> str:
    project_order = sorted({task.project for task in tasks})
    lanes = {project: index for index, project in enumerate(project_order)}
    card_width = 260
    card_height = 148
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
        '<text x="40" y="48" font-family="Georgia, serif" font-size="28" fill="#1D3557">Project Plan</text>',
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
        mitigation = _wrap_text(task.risk_mitigation, 34)[:2]
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
        for index, line in enumerate(description):
            elements.append(
                f'<text x="{x + 22}" y="{text_y + 130 + index * 14}" font-family="Arial, sans-serif" font-size="11" fill="#495057">{escape(line)}</text>'
            )
        for index, line in enumerate(mitigation):
            elements.append(
                f'<text x="{x + 22}" y="{text_y + 158 + index * 14}" font-family="Arial, sans-serif" font-size="11" fill="#0B6E4F">{escape("mitigate: " + line if index == 0 else line)}</text>'
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
