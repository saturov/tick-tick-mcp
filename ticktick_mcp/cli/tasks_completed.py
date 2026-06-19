#!/usr/bin/env python3
"""TickTick completed tasks utility."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from typing import Any

from ticktick_mcp.cli.api import _write_output, list_projects, resolve_project_ids
from ticktick_mcp.cli.client import TickTickClient, build_client, ensure_venv_active


def _parse_completed_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.000+0000")
    except ValueError:
        return None


def _fetch_closed_tasks(client: TickTickClient, limit: int) -> list[dict[str, Any]]:
    response = client._session.get(
        client.BASE_URL + "project/all/closed",
        params={"status": "Completed", "limit": limit},
        cookies=client.cookies,
        headers=client._headers,
        timeout=20,
    )
    if response.status_code in (401, 403):
        raise RuntimeError("auth failed")
    if response.status_code != 200:
        raise RuntimeError("sync failed")
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError("unexpected response") from exc
    if not isinstance(payload, list):
        raise RuntimeError("unexpected response")
    return [item for item in payload if isinstance(item, dict)]


def get_completed_tasks_for_date(
    target_date: date,
    selected_project_ids: set[str] | None = None,
    initial_limit: int = 200,
    max_limit: int = 5000,
) -> list[dict[str, Any]]:
    ensure_venv_active()

    try:
        client = build_client()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("auth failed") from exc

    limit = max(1, initial_limit)
    fetched_tasks: list[dict[str, Any]] = []
    target_iso = target_date.isoformat()

    while True:
        fetched_tasks = _fetch_closed_tasks(client, limit=limit)
        completed_times = [dt for task in fetched_tasks if (dt := _parse_completed_time(task.get("completedTime")))]
        if not completed_times:
            break

        oldest_date = min(completed_times).date().isoformat()
        if oldest_date <= target_iso:
            break
        if len(fetched_tasks) < limit or limit >= max_limit:
            break
        limit = min(limit * 2, max_limit)

    project_names = {
        project["id"]: project["name"]
        for project in getattr(client, "state", {}).get("projects", [])
        if isinstance(project, dict)
        and isinstance(project.get("id"), str)
        and isinstance(project.get("name"), str)
    }

    fetched_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []
    for task in fetched_tasks:
        completed_at = _parse_completed_time(task.get("completedTime"))
        if completed_at is None or completed_at.date() != target_date:
            continue

        project_id = task.get("projectId")
        if selected_project_ids is not None and project_id not in selected_project_ids:
            continue

        raw = dict(task)
        if isinstance(project_id, str) and project_id in project_names:
            raw["projectName"] = project_names[project_id]

        results.append(
            {
                "raw": raw,
                "meta": {
                    "completed_at": task.get("completedTime"),
                    "fetched_at": fetched_at,
                    "source": "ticktick-web-v2-closed",
                },
            }
        )

    results.sort(key=lambda item: item["meta"]["completed_at"] or "")
    return results


def get_completed_tasks_range(
    from_date: date,
    to_date: date,
    selected_project_ids: set[str] | None = None,
    initial_limit: int = 200,
    max_limit: int = 5000,
) -> list[dict[str, Any]]:
    ensure_venv_active()

    try:
        client = build_client()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("auth failed") from exc

    limit = max(1, initial_limit)
    fetched_tasks: list[dict[str, Any]] = []
    to_iso = to_date.isoformat()

    while True:
        fetched_tasks = _fetch_closed_tasks(client, limit=limit)
        completed_times = [dt for task in fetched_tasks if (dt := _parse_completed_time(task.get("completedTime")))]
        if not completed_times:
            break
        oldest_date = min(completed_times).date().isoformat()
        if oldest_date <= to_iso:
            break
        if len(fetched_tasks) < limit or limit >= max_limit:
            break
        limit = min(limit * 2, max_limit)

    project_names = {
        project["id"]: project["name"]
        for project in getattr(client, "state", {}).get("projects", [])
        if isinstance(project, dict)
        and isinstance(project.get("id"), str)
        and isinstance(project.get("name"), str)
    }

    fetched_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []
    for task in fetched_tasks:
        completed_at = _parse_completed_time(task.get("completedTime"))
        if completed_at is None:
            continue
        completed_date = completed_at.date()
        if not (from_date <= completed_date <= to_date):
            continue

        project_id = task.get("projectId")
        if selected_project_ids is not None and project_id not in selected_project_ids:
            continue

        raw = dict(task)
        if isinstance(project_id, str) and project_id in project_names:
            raw["projectName"] = project_names[project_id]

        results.append(
            {
                "raw": raw,
                "meta": {
                    "completed_at": task.get("completedTime"),
                    "fetched_at": fetched_at,
                    "source": "ticktick-web-v2-closed",
                },
            }
        )

    results.sort(key=lambda item: item["meta"]["completed_at"] or "")
    return results


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

    _write_output(tasks, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
