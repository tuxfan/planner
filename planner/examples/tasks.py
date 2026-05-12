PLAN = {
    "fiscal_range_begin": 27,
    "fiscal_range_end": 29,
    "tasks": [
        {
            "id": "DraftArchitecture",
            "label": "Draft architecture",
            "site": "LANL",
            "project": "Planning System",
            "description": "Produce the first architecture draft for the planner.",
            "start": "M1Q3FY26",
            "deadline": "M2Q3FY26",
            "expected_duration": 2,
            "milestone": "Design",
            "priority": "high",
            "status": "complete",
            "dependencies": [],
            "risk": [
                {
                    "type": "scope",
                    "level": "medium",
                    "mitigation": "Review the architecture with stakeholders before implementation starts.",
                }
            ],
            "funding": {"fy27": "50K", "fy28": "50K"},
        },
        {
            "id": "DefineTaskSchema",
            "label": "Define task schema",
            "site": "LANL",
            "project": "Planning System",
            "description": "Lock down the required task attributes and field aliases.",
            "start": "M2Q3FY26",
            "deadline": "M2Q3FY26",
            "expected_duration": 1,
            "milestone": "Design",
            "priority": "high",
            "status": "pending",
            "dependencies": ["DraftArchitecture"],
            "risk": [
                {
                    "type": "requirements",
                    "level": "low",
                    "mitigation": "Document field aliases and validate examples against the schema.",
                }
            ],
        },
    ],
}
