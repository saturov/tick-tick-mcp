#!/usr/bin/env python3
"""TickTick task update CLI wrapper."""

from __future__ import annotations

import argparse
import json
import sys

from ticktick_cli.mcp import update_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update TickTick task fields.")
    parser.add_argument("task_id", help="Task ID to update")
    parser.add_argument(
        "--start-date",
        metavar="DATE",
        help="Set start date (YYYY-MM-DD or ISO 8601)",
    )
    parser.add_argument(
        "--due-date",
        metavar="DATE",
        help="Set due date (YYYY-MM-DD or ISO 8601)",
    )
    parser.add_argument("--title", metavar="TEXT", help="Set task title")
    parser.add_argument(
        "--priority",
        metavar="N",
        help="Set priority: 0=none, 1=low, 3=medium, 5=high",
    )
    parser.add_argument("--complete", action="store_true", help="Mark task as completed")
    parser.add_argument("--wont-do", action="store_true", help="Mark task as won't do")

    args = parser.parse_args(argv)

    if args.complete and args.wont_do:
        sys.stderr.write("cannot use --complete and --wont-do together\n")
        return 1

    try:
        result = update_task(
            task_id=args.task_id,
            start_date=args.start_date,
            due_date=args.due_date,
            title=args.title,
            priority=args.priority,
            complete=args.complete,
            wont_do=args.wont_do,
        )
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
