"""Output helpers owned by the skill CLI layer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def write_output(data: Any, output: str | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        return
    sys.stdout.write(text + "\n")


def write_projects(projects: list[dict[str, Any]]) -> None:
    for project in sorted(projects, key=lambda item: item.get("name", "")):
        sys.stdout.write(f"{project.get('id', '')}\t{project.get('name', '')}\n")
