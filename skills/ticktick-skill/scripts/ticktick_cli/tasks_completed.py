#!/usr/bin/env python3
"""TickTick completed tasks utility."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

from ticktick_cli.mcp import handle_get_completed_tasks, list_projects, resolve_project_ids
from ticktick_cli.output import write_output


def _wrap_completed_task(task: dict[str, Any]) -> dict[str, Any]:
    raw = dict(task)
    meta = {
        "completed_at": raw.pop("completed_at", None) or raw.get("completedTime"),
        "fetched_at": raw.pop("fetched_at", None),
        "source": raw.pop("source", None) or "ticktick-web-v2-closed",
    }
    return {"raw": raw, "meta": meta}


def get_completed_tasks_for_date(
    target_date: date,
    selected_project_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    selected = selected_project_ids or {""}
    tasks: list[dict[str, Any]] = []
    for project_id in selected:
        payload = handle_get_completed_tasks(
            date=target_date.isoformat(),
            project_id=project_id,
        )
        tasks.extend(_wrap_completed_task(task) for task in payload["tasks"])
    tasks.sort(key=lambda item: item["meta"]["completed_at"] or "")
    return tasks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List completed TickTick tasks for a date.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Target date in YYYY-MM-DD. Defaults to today.")
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
        target_date = date.fromisoformat(args.date)
    except ValueError:
        sys.stderr.write("invalid date\n")
        return 1

    try:
        selected_project_ids: set[str] | None = None
        if args.project:
            projects = list_projects()
            selected_project_ids = resolve_project_ids(projects, args.project)
        tasks = get_completed_tasks_for_date(target_date=target_date, selected_project_ids=selected_project_ids)
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    write_output(tasks, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
