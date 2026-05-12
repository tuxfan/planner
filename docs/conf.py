from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

with (ROOT / "pyproject.toml").open("rb") as handle:
    _project_metadata = tomllib.load(handle)["project"]

project = "Project Planner"
author = "Project Planner contributors"
copyright = "2026, Project Planner contributors"
release = _project_metadata["version"]

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"
html_static_path = ["_static"]

autodoc_typehints = "description"
autodoc_member_order = "bysource"
