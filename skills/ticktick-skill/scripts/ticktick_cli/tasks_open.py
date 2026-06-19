#!/usr/bin/env python3
"""TickTick open tasks utility — all open tasks, optionally filtered by project or folder."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from ticktick_cli.mcp import (
    _is_open_task,
    build_client,
    fetch_all_tasks,
    resolve_selectors,
)
from ticktick_cli.output import write_output

_write_output = write_output


def get_open_tasks(
    selected_project_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return all open tasks, optionally filtered by project IDs."""
    tasks = fetch_all_tasks(selected_project_ids=selected_project_ids)
    return [t for t in tasks if _is_open_task(t["raw"])]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List all open TickTick tasks.")
    parser.add_argument("--output", help="Write JSON to file instead of stdout.")
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        metavar="NAME_OR_ID",
        help="Select project or project folder by name or id. Repeatable.",
    )

    args = parser.parse_args(argv)

    try:
        api_key = os.environ.get("TICKTICK_API_KEY")
        selected_project_ids: set[str] | None = None

        if args.project:
            client_for_folders = None
            if not api_key:
                try:
                    client_for_folders = build_client()
                except Exception:
                    client_for_folders = None

            selected_project_ids = resolve_selectors(
                selectors=args.project,
                api_key=api_key,
                client=client_for_folders,
            )

        tasks = get_open_tasks(selected_project_ids=selected_project_ids)
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    _write_output(tasks, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
