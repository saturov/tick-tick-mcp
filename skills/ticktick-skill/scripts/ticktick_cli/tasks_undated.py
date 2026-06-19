#!/usr/bin/env python3
"""TickTick undated open tasks utility."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ticktick_cli.mcp import (
    _is_open_task,
    fetch_all_tasks,
    list_projects,
    resolve_project_ids,
)
from ticktick_cli.output import write_output

_write_output = write_output


def _missing_date(value: Any) -> bool:
    return value is None or value == ""


def get_open_tasks_without_dates(
    selected_project_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return open tasks without dueDate and startDate."""
    tasks = fetch_all_tasks(selected_project_ids=selected_project_ids)
    results = []
    for task in tasks:
        raw = task["raw"]
        due_date = raw.get("dueDate") if isinstance(raw, dict) else getattr(raw, "dueDate", None)
        start_date = raw.get("startDate") if isinstance(raw, dict) else getattr(raw, "startDate", None)
        if _is_open_task(raw) and _missing_date(due_date) and _missing_date(start_date):
            results.append(task)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List open TickTick tasks without dates.")
    parser.add_argument("--output", help="Write JSON to file instead of stdout.")
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        metavar="NAME_OR_ID",
        help="Select project by exact id or exact name (case-insensitive). Repeatable.",
    )

    args = parser.parse_args(argv)

    try:
        selected_project_ids: set[str] | None = None
        if args.project:
            projects = list_projects()
            selected_project_ids = resolve_project_ids(projects, args.project)

        tasks = get_open_tasks_without_dates(selected_project_ids=selected_project_ids)
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    _write_output(tasks, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
