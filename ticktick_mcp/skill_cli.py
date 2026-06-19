"""Console script entry points for the bundled ticktick skill."""

from __future__ import annotations

import sys
from pathlib import Path


_SKILL_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "ticktick-skill" / "scripts"
sys.path.insert(0, str(_SKILL_SCRIPTS_DIR))


def _run(module_name: str) -> int:
    module = __import__(f"ticktick_cli.{module_name}", fromlist=["main"])
    return module.main()


def projects() -> int:
    return _run("projects")


def tasks_open() -> int:
    return _run("tasks_open")


def tasks_undated() -> int:
    return _run("tasks_undated")


def tasks_completed() -> int:
    return _run("tasks_completed")


def task_update() -> int:
    return _run("task_update")


def plan() -> int:
    return _run("plan")
