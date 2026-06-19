#!/usr/bin/env python3
"""TickTick task update utility — update task fields via Open API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

from ticktick_mcp.cli.api import _is_open_task, _task_raw, fetch_all_tasks
from ticktick_mcp.cli.client import ensure_venv_active, _make_retry_session


_SKIP_KEYS = {"projectName", "etag", "modifiedTime"}
_MAX_VERIFY_ATTEMPTS = 3


def _build_open_api_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _parse_date(value: str) -> tuple[str, bool]:
    """Parse a date string and return (TickTick-format UTC date, is_datetime).

    Date-only strings (YYYY-MM-DD) are returned as-is with midnight UTC and
    is_datetime=False.  Datetime strings are converted to UTC and returned
    with is_datetime=True so callers can set isAllDay accordingly.
    """
    from datetime import timezone as _tz

    date_only = len(value) == 10 and "-" in value and "T" not in value

    if date_only:
        return f"{value}T00:00:00.000+0000", False

    normalized = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", value)
    dt = datetime.fromisoformat(normalized)

    if dt.tzinfo is not None:
        utc_dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
    else:
        utc_dt = dt  # treat naive as UTC

    return f"{utc_dt.isoformat()}.000+0000", True


def _complete_task(
    session: Any,
    api_key: str,
    task_data: dict[str, Any],
    *,
    wont_do: bool = False,
) -> dict[str, Any]:
    headers = _build_open_api_headers(api_key)
    payload: dict[str, Any] = {}
    if wont_do:
        payload["isWontDo"] = True

    task_id = task_data.get("id", "")
    project_id = task_data.get("projectId", "")
    if not project_id:
        raise RuntimeError("task has no projectId")

    response = session.post(
        f"https://api.ticktick.com/open/v1/project/{project_id}/task/{task_id}/complete",
        json=payload,
        headers=headers,
        timeout=20,
    )
    if response.status_code == 200:
        try:
            return response.json() if response.text else {"id": task_id, "completed": True}
        except Exception as exc:
            raise RuntimeError("unexpected response") from exc
    if response.status_code in (401, 403):
        raise RuntimeError("auth failed")
    raise RuntimeError("sync failed")


def _send_task_update(
    session: Any,
    api_key: str,
    task_data: dict[str, Any],
) -> dict[str, Any]:
    headers = _build_open_api_headers(api_key)
    payload = dict(task_data)
    for key in _SKIP_KEYS:
        payload.pop(key, None)

    task_id = payload.get("id", "")

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        response = session.post(
            f"https://api.ticktick.com/open/v1/task/{task_id}",
            json=payload,
            headers=headers,
            timeout=20,
        )
        if response.status_code in (401, 403):
            raise RuntimeError("auth failed")
        if response.status_code == 200:
            try:
                return response.json() if response.text else {"id": task_id}
            except Exception as exc:
                raise RuntimeError("unexpected response") from exc

        try:
            error_data = response.json()
            is_rate_limited = error_data.get("errorCode") == "exceed_query_limit"
        except Exception:
            is_rate_limited = response.status_code == 429

        if is_rate_limited and attempt < max_attempts:
            time.sleep(16)
            continue

        raise RuntimeError("sync failed")

    raise RuntimeError("sync failed")


def _verify_update(task_id: str, expected_fields: dict[str, Any]) -> list[str]:
    """Re-fetch task and compare expected fields. Returns list of mismatch descriptions."""
    try:
        current = get_task_by_id(task_id)
    except RuntimeError as exc:
        return [f"re-fetch failed: {exc}"]

    mismatches: list[str] = []
    for key, expected_val in expected_fields.items():
        actual_val = current.get(key)
        # For datetime strings compare only up to seconds (ignore ms and tz suffix)
        if isinstance(expected_val, str) and "T" in expected_val and len(expected_val) >= 19:
            exp_norm = expected_val[:19]
            act_norm = (actual_val or "")[:19]
            if exp_norm != act_norm:
                mismatches.append(f"{key}: expected {exp_norm!r}, got {act_norm!r}")
        elif actual_val != expected_val:
            mismatches.append(f"{key}: expected {expected_val!r}, got {actual_val!r}")
    return mismatches


def get_task_by_id(task_id: str) -> dict[str, Any]:
    ensure_venv_active()
    api_key = os.environ.get("TICKTICK_API_KEY")
    if not api_key:
        raise RuntimeError("TICKTICK_API_KEY is required for task updates")

    tasks = [t for t in fetch_all_tasks() if _is_open_task(_task_raw(t))]
    for task in tasks:
        raw = _task_raw(task)
        if raw.get("id") == task_id:
            return raw

    raise RuntimeError(f"task not found: {task_id}")


def update_task(
    task_id: str,
    start_date: str | None = None,
    due_date: str | None = None,
    title: str | None = None,
    priority: str | None = None,
    *,
    complete: bool = False,
    wont_do: bool = False,
) -> dict[str, Any]:
    ensure_venv_active()
    api_key = os.environ.get("TICKTICK_API_KEY")
    if not api_key:
        raise RuntimeError("TICKTICK_API_KEY is required for task updates")

    if complete or wont_do:
        task_data = get_task_by_id(task_id)
        session = _make_retry_session()
        return _complete_task(session=session, api_key=api_key, task_data=task_data, wont_do=wont_do)

    if start_date is None and due_date is None and title is None and priority is None:
        raise RuntimeError("at least one field to update is required")

    task_data = get_task_by_id(task_id)

    if start_date is not None:
        parsed, is_datetime = _parse_date(start_date)
        task_data["startDate"] = parsed
        if is_datetime:
            task_data["isAllDay"] = False
    if due_date is not None:
        parsed, is_datetime = _parse_date(due_date)
        task_data["dueDate"] = parsed
        if is_datetime:
            task_data["isAllDay"] = False
    if title is not None:
        task_data["title"] = title
    if priority is not None:
        try:
            task_data["priority"] = int(priority)
        except ValueError:
            raise RuntimeError(f"invalid priority value: {priority}")

    # Build expected state for post-update verification
    expected_fields: dict[str, Any] = {}
    if start_date is not None:
        expected_fields["startDate"] = task_data["startDate"]
        expected_fields["isAllDay"] = False
    if due_date is not None:
        expected_fields["dueDate"] = task_data["dueDate"]
    if title is not None:
        expected_fields["title"] = title
    if priority is not None:
        expected_fields["priority"] = task_data["priority"]

    session = _make_retry_session()

    for attempt in range(1, _MAX_VERIFY_ATTEMPTS + 1):
        result = _send_task_update(session=session, api_key=api_key, task_data=task_data)
        mismatches = _verify_update(task_id=task_id, expected_fields=expected_fields)
        if not mismatches:
            return result
        if attempt < _MAX_VERIFY_ATTEMPTS:
            sys.stderr.write(
                f"verification attempt {attempt} failed ({', '.join(mismatches)}), retrying\n"
            )
        else:
            raise RuntimeError(
                f"verification failed after {_MAX_VERIFY_ATTEMPTS} attempts: {'; '.join(mismatches)}"
            )

    raise RuntimeError("sync failed")  # unreachable


def create_task(
    title: str,
    project_id: str | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
    priority: int | None = None,
    content: str | None = None,
    all_day: bool | None = None,
    time_zone: str | None = None,
) -> dict[str, Any]:
    ensure_venv_active()
    api_key = os.environ.get("TICKTICK_API_KEY")
    if not api_key:
        raise RuntimeError("TICKTICK_API_KEY is required for task creation")

    task_data: dict[str, Any] = {"title": title}
    if project_id is not None:
        task_data["projectId"] = project_id
    if content is not None:
        task_data["content"] = content
    if priority is not None:
        task_data["priority"] = priority
    if all_day is not None:
        task_data["isAllDay"] = all_day
    if time_zone is not None:
        task_data["timeZone"] = time_zone
    if start_date is not None:
        parsed, is_dt = _parse_date(start_date)
        task_data["startDate"] = parsed
        if is_dt:
            task_data["isAllDay"] = False
    if due_date is not None:
        parsed, is_dt = _parse_date(due_date)
        task_data["dueDate"] = parsed
        if is_dt:
            task_data["isAllDay"] = False

    headers = _build_open_api_headers(api_key)
    session = _make_retry_session()

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        response = session.post(
            "https://api.ticktick.com/open/v1/task",
            json=task_data,
            headers=headers,
            timeout=20,
        )
        if response.status_code in (401, 403):
            raise RuntimeError("auth failed")
        if response.status_code == 200:
            try:
                return response.json() if response.text else task_data
            except Exception as exc:
                raise RuntimeError("unexpected response") from exc
        try:
            error_data = response.json()
            is_rate_limited = error_data.get("errorCode") == "exceed_query_limit"
        except Exception:
            is_rate_limited = response.status_code == 429
        if is_rate_limited and attempt < max_attempts:
            time.sleep(16)
            continue
        raise RuntimeError("sync failed")
    raise RuntimeError("sync failed")


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
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Mark task as completed",
    )
    parser.add_argument(
        "--wont-do",
        action="store_true",
        help="Mark task as won't do (abandoned)",
    )

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
