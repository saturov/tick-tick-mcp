from __future__ import annotations

from datetime import date as date_type
from typing import Any

from session import get_session, TickTickMCPSession
from ticktick_cli.task_update import create_task as _cli_create_task, update_task as _cli_update_task, _parse_date
from ticktick_cli.tasks_completed import get_completed_tasks_for_date, get_completed_tasks_range
from ticktick_cli.api import fetch_all_tasks
from ticktick_cli.client import TickTickClient


def _format_task(task: dict[str, Any]) -> dict[str, Any]:
    raw = task.get("raw", task)
    meta = task.get("meta", {})
    result = dict(raw)
    if "completed_at" in meta:
        result["completed_at"] = meta["completed_at"]
    if "fetched_at" in meta:
        result["fetched_at"] = meta["fetched_at"]
    if "source" in meta:
        result["source"] = meta["source"]
    return result


def handle_get_tasks(project_id: str = "") -> dict[str, Any]:
    session = get_session()
    selected: set[str] | None = None
    if project_id:
        resolved = session.resolve_project_id(project_id)
        selected = {resolved}
    tasks = fetch_all_tasks(selected_project_ids=selected)
    open_tasks = [t for t in tasks if t.get("raw", {}).get("status") != 2]
    return {"tasks": [_format_task(t) for t in open_tasks], "count": len(open_tasks)}


def handle_get_task(project_id: str, task_id: str) -> dict[str, Any]:
    session = get_session()
    resolved_pid = session.resolve_project_id(project_id)
    tasks = fetch_all_tasks(selected_project_ids={resolved_pid})
    for t in tasks:
        raw = t.get("raw", {})
        if raw.get("id") == task_id:
            return {"task": _format_task(t)}
    raise RuntimeError(f"task not found: {task_id}")


def handle_create_task(
    title: str,
    project_id: str = "",
    start_date: str = "",
    due_date: str = "",
    priority: int | None = None,
    content: str = "",
    all_day: bool | None = None,
    time_zone: str = "",
) -> dict[str, Any]:
    pid: str | None = None
    if project_id:
        session = get_session()
        pid = session.resolve_project_id(project_id)
    task = _cli_create_task(
        title=title,
        project_id=pid,
        start_date=start_date if start_date else None,
        due_date=due_date if due_date else None,
        priority=priority,
        content=content if content else None,
        all_day=all_day,
        time_zone=time_zone if time_zone else None,
    )
    return {"task": task}


def handle_update_task(
    task_id: str,
    title: str = "",
    start_date: str = "",
    due_date: str = "",
    priority: int | None = None,
) -> dict[str, Any]:
    result = _cli_update_task(
        task_id=task_id,
        title=title if title else None,
        start_date=start_date if start_date else None,
        due_date=due_date if due_date else None,
        priority=str(priority) if priority is not None else None,
    )
    return {"task": result}


def handle_complete_task(task_id: str, project_id: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved_pid = session.resolve_project_id(project_id)
    result = client.complete_task(task_id=task_id, project_id=resolved_pid)
    return {"task": result}


def handle_uncomplete_task(task_id: str, project_id: str) -> dict[str, Any]:
    session = get_session()
    _ = session.api_key
    from ticktick_cli.task_update import _send_task_update
    from ticktick_cli.client import _make_retry_session
    resolved_pid = session.resolve_project_id(project_id)
    api_key = session.api_key
    tasks = fetch_all_tasks(selected_project_ids={resolved_pid})
    task_data = None
    for t in tasks:
        raw = t.get("raw", {})
        if raw.get("id") == task_id:
            task_data = dict(raw)
            break
    if not task_data:
        raise RuntimeError(f"task not found: {task_id}")
    task_data["status"] = 0
    result = _send_task_update(
        session=_make_retry_session(),
        api_key=api_key,
        task_data=task_data,
    )
    return {"task": result}


def handle_delete_task(task_id: str, project_id: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved_pid = session.resolve_project_id(project_id)
    result = client.delete_task(task_id=task_id, project_id=resolved_pid)
    return {"task": result}


def handle_delete_tasks(items: list[dict[str, str]]) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved = []
    for item in items:
        resolved_pid = session.resolve_project_id(item["project_id"])
        resolved.append({"projectId": resolved_pid, "taskId": item["task_id"]})
    result = client.delete_tasks_batch(resolved)
    return {"deleted": result}


def handle_move_task(task_id: str, from_project_id: str, to_project_id: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    from_pid = session.resolve_project_id(from_project_id)
    to_pid = session.resolve_project_id(to_project_id)
    result = client.move_task(
        task_id=task_id, from_project_id=from_pid, to_project_id=to_pid
    )
    return {"task": result}


def handle_get_completed_tasks(date: str = "", project_id: str = "") -> dict[str, Any]:
    session = get_session()
    target = date_type.today() if not date else date_type.fromisoformat(date)
    selected: set[str] | None = None
    if project_id:
        resolved = session.resolve_project_id(project_id)
        selected = {resolved}
    tasks = get_completed_tasks_for_date(
        target_date=target, selected_project_ids=selected
    )
    return {"tasks": [_format_task(t) for t in tasks], "count": len(tasks)}


def handle_get_completed_tasks_range(
    from_date: str,
    to_date: str,
    project_id: str = "",
) -> dict[str, Any]:
    session = get_session()
    fr = date_type.fromisoformat(from_date)
    to = date_type.fromisoformat(to_date)
    selected: set[str] | None = None
    if project_id:
        resolved = session.resolve_project_id(project_id)
        selected = {resolved}
    tasks = get_completed_tasks_range(from_date=fr, to_date=to, selected_project_ids=selected)
    return {"tasks": [_format_task(t) for t in tasks], "count": len(tasks)}


def handle_make_subtask(task_id: str, parent_id: str, project_id: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved_pid = session.resolve_project_id(project_id)
    result = client.make_subtask(
        task_id=task_id, parent_id=parent_id, project_id=resolved_pid
    )
    return {"task": result}


def handle_remove_subtask(task_id: str, project_id: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved_pid = session.resolve_project_id(project_id)
    result = client.remove_subtask(task_id=task_id, project_id=resolved_pid)
    return {"task": result}