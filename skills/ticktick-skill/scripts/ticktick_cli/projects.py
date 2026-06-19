#!/usr/bin/env python3
"""TickTick projects listing utility."""

from __future__ import annotations

import argparse
import sys

from ticktick_cli.mcp import handle_list_projects
from ticktick_cli.output import write_projects


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List available TickTick projects.")
    parser.parse_args(argv)

    try:
        payload = handle_list_projects()
        projects = payload["projects"]
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    write_projects(projects)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
