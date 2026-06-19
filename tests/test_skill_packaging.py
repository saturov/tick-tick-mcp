from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "ticktick-skill"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def test_ticktick_skill_lives_in_mcp_repo():
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SCRIPTS_DIR / "ticktick-plan").is_file()
    assert (SCRIPTS_DIR / "ticktick_cli" / "plan.py").is_file()


def test_skill_bridge_does_not_reference_sibling_repo():
    bridge = SCRIPTS_DIR / "ticktick_cli" / "mcp.py"
    assert bridge.is_file()
    text = bridge.read_text()
    assert "tick-tick-mcp" not in text
    assert "sys.path.insert" not in text


def test_pyproject_exposes_skill_cli_commands():
    text = (ROOT / "pyproject.toml").read_text()
    for name in (
        "ticktick-projects",
        "ticktick-tasks-open",
        "ticktick-tasks-undated",
        "ticktick-tasks-completed",
        "ticktick-task-update",
        "ticktick-plan",
    ):
        assert f'{name} =' in text


def test_skill_cli_modules_import_from_mcp_repo():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import ticktick_cli.plan
    import ticktick_cli.projects
    import ticktick_cli.task_update
    import ticktick_cli.tasks_completed
    import ticktick_cli.tasks_open
    import ticktick_cli.tasks_undated

    assert ticktick_cli.plan.fetch_all_tasks is not None
