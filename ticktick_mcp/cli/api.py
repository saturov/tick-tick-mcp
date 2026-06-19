"""TickTick API — project listing, task fetching, and project resolution."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from ticktick_mcp.cli.client import (
    TickTickClient,
    build_client,
    ensure_venv_active,
    open_api_get_json,
    _make_retry_session,
)


# ---------------------------------------------------------------------------
# Task helpers
# ---------------------------------------------------------------------------

def _task_raw(task: Any) -> Any:
    if isinstance(task, dict):
        if "raw" in task:
            return task["raw"]
        return task
    if hasattr(task, "to_dict") and callable(task.to_dict):
        try:
            return task.to_dict()
        except Exception:
            return task
    if hasattr(task, "raw"):
        return task.raw
    return task


def _is_open_task(task: Any) -> bool:
    if isinstance(task, dict):
        return task.get("status") != 2
    return getattr(task, "status", None) != 2


def _task_project_id(raw: Any) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("projectId")
    else:
        value = getattr(raw, "projectId", None)
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# Project listing
# ---------------------------------------------------------------------------

def _list_projects_with_api_key(api_key: str) -> list[dict[str, Any]]:
    """List projects via Open API. Returns dicts with id, name, and optional groupId."""
    try:
        session = _make_retry_session()
        projects_raw = open_api_get_json(
            session=session,
            url="https://api.ticktick.com/open/v1/project",
            api_key=api_key,
        )
        if not isinstance(projects_raw, list):
            raise RuntimeError("unexpected response")

        result: list[dict[str, Any]] = []
        for project in projects_raw:
            if not isinstance(project, dict):
                continue
            if project.get("closed") is True:
                continue
            project_id = project.get("id")
            project_name = project.get("name")
            if not isinstance(project_id, str) or not isinstance(project_name, str):
                continue
            entry: dict[str, Any] = {"id": project_id, "name": project_name}
            group_id = project.get("groupId")
            if isinstance(group_id, str):
                entry["groupId"] = group_id
            result.append(entry)
        return result
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("sync failed") from exc


def _list_projects_with_client() -> list[dict[str, str]]:
    """List projects via web session client."""
    ensure_venv_active()
    try:
        client = build_client()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("auth failed") from exc

    state = getattr(client, "state", None)
    if not isinstance(state, dict):
        raise RuntimeError("unexpected response")

    raw_projects = state.get("projects", [])
    if not isinstance(raw_projects, list):
        raise RuntimeError("unexpected response")

    projects: list[dict[str, str]] = []
    for project in raw_projects:
        if not isinstance(project, dict):
            continue
        if project.get("closed") is True:
            continue
        project_id = project.get("id")
        project_name = project.get("name")
        if not isinstance(project_id, str) or not isinstance(project_name, str):
            continue
        projects.append({"id": project_id, "name": project_name})
    return projects


def list_projects() -> list[dict[str, str]]:
    """List available TickTick projects (dispatcher: API key or web client)."""
    ensure_venv_active()
    api_key = os.environ.get("TICKTICK_API_KEY")
    if api_key:
        return _list_projects_with_api_key(api_key=api_key)
    return _list_projects_with_client()


# ---------------------------------------------------------------------------
# Project / folder resolution
# ---------------------------------------------------------------------------

def resolve_project_ids(projects: list[dict[str, str]], selectors: list[str]) -> set[str]:
    """Resolve a list of project name/ID selectors to a set of project IDs."""
    id_map = {project["id"]: project for project in projects}
    name_map: dict[str, list[dict[str, str]]] = {}
    for project in projects:
        name_key = project["name"].casefold()
        name_map.setdefault(name_key, []).append(project)

    resolved: set[str] = set()
    for selector in selectors:
        exact_id = id_map.get(selector)
        if exact_id is not None:
            resolved.add(exact_id["id"])
            continue

        same_name = name_map.get(selector.casefold(), [])
        if len(same_name) == 1:
            resolved.add(same_name[0]["id"])
            continue
        if len(same_name) > 1:
            ids = ", ".join(project["id"] for project in same_name)
            raise RuntimeError(f"project name is ambiguous: {selector}. use id: {ids}")
        raise RuntimeError(f"project not found: {selector}")

    return resolved


def _resolve_folder_from_projects(
    selector: str,
    projects_with_group: list[dict[str, Any]],
) -> set[str]:
    """Resolve a folder selector to project IDs using the Open API (groupId) path."""
    key = selector.casefold()
    groups: dict[str, set[str]] = {}
    for project in projects_with_group:
        group_id = project.get("groupId")
        if not isinstance(group_id, str):
            continue
        groups.setdefault(group_id, set()).add(project["id"])

    for group_id, project_ids in groups.items():
        if group_id.casefold() == key and project_ids:
            return project_ids

    return set()


def _resolve_folder_from_raw(
    selector: str,
    raw_folders: list[dict[str, Any]],
    raw_projects: list[dict[str, Any]],
) -> set[str]:
    """Resolve a folder selector to project IDs using web client state."""
    key = selector.casefold()
    folder_ids: dict[str, str] = {}
    for folder in raw_folders:
        if not isinstance(folder, dict):
            continue
        fid = folder.get("id")
        fname = folder.get("name")
        if isinstance(fid, str) and isinstance(fname, str):
            folder_ids[fid] = fname

    matched_folder_id: str | None = None
    for fid, fname in folder_ids.items():
        if fname.casefold() == key:
            matched_folder_id = fid
            break

    if matched_folder_id is None:
        return set()

    result: set[str] = set()
    for project in raw_projects:
        if not isinstance(project, dict):
            continue
        if project.get("closed") is True:
            continue
        pid = project.get("id")
        if isinstance(pid, str) and project.get("groupId") == matched_folder_id:
            result.add(pid)

    return result


def _resolve_folder_selector(
    selector: str,
    api_key: str | None = None,
    client: TickTickClient | None = None,
) -> set[str]:
    """Try to resolve selector as a folder name. Returns set of project IDs."""
    if api_key:
        projects_with_group = _list_projects_with_api_key(api_key)
        return _resolve_folder_from_projects(selector, projects_with_group)

    if client is not None:
        state = getattr(client, "state", None) or {}
        raw_folders = state.get("project_folders", [])
        raw_projects = state.get("projects", [])
        return _resolve_folder_from_raw(selector, raw_folders, raw_projects)

    return set()


def resolve_selectors(
    selectors: list[str],
    api_key: str | None = None,
    client: TickTickClient | None = None,
) -> set[str]:
    """Resolve a list of project name/ID/folder selectors to project IDs."""
    projects = list_projects()
    resolved: set[str] = set()

    for selector in selectors:
        try:
            sub = resolve_project_ids(projects, [selector])
            resolved.update(sub)
            continue
        except RuntimeError:
            pass

        folder_ids = _resolve_folder_selector(selector, api_key=api_key, client=client)
        if folder_ids:
            resolved.update(folder_ids)
            continue

        raise RuntimeError(f"project or folder not found: {selector}")

    return resolved


# ---------------------------------------------------------------------------
# Task fetching
# ---------------------------------------------------------------------------

def fetch_all_tasks(
    selected_project_ids: set[str] | None = None,
    *,
    client: TickTickClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch all tasks, optionally filtered by project IDs.

    Returns list of {"raw": {...}, "meta": {"fetched_at": ..., "source": ...}}.
    Does NOT filter by open/closed status — callers are responsible.

    If `client` is provided and no API key is set, uses that client directly
    without building a new one (avoids double-authentication).
    """
    ensure_venv_active()
    api_key = os.environ.get("TICKTICK_API_KEY")

    if api_key:
        try:
            session = _make_retry_session()
            projects = _list_projects_with_api_key(api_key)
            raw_tasks: list[Any] = []
            for project in projects:
                project_id = project["id"]
                if selected_project_ids is not None and project_id not in selected_project_ids:
                    continue
                if not project_id:
                    continue
                project_data = open_api_get_json(
                    session=session,
                    url=f"https://api.ticktick.com/open/v1/project/{project_id}/data",
                    api_key=api_key,
                )
                if not isinstance(project_data, dict):
                    raise RuntimeError("unexpected response")
                project_tasks = project_data.get("tasks", [])
                if not isinstance(project_tasks, list):
                    raise RuntimeError("unexpected response")
                raw_tasks.extend(project_tasks)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError("sync failed") from exc
        source = "ticktick-open-api"
    else:
        if client is None:
            try:
                client = build_client()
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError("auth failed") from exc

        state = getattr(client, "state", None)
        if not isinstance(state, dict):
            raise RuntimeError("unexpected response")

        raw_tasks_list = state.get("tasks", [])
        if not isinstance(raw_tasks_list, list):
            raise RuntimeError("unexpected response")
        raw_tasks = raw_tasks_list
        source = "ticktick-py"

    fetched_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []
    for task in raw_tasks:
        raw = _task_raw(task)

        # Post-filter for client path (API path already pre-filtered by project)
        if api_key is None and selected_project_ids is not None:
            project_id_ = _task_project_id(raw)
            if project_id_ not in selected_project_ids:
                continue

        results.append(
            {
                "raw": raw,
                "meta": {
                    "fetched_at": fetched_at,
                    "source": source,
                },
            }
        )

    return results


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_projects(projects: list[dict[str, str]]) -> None:
    ordered = sorted(projects, key=lambda item: (item["name"].casefold(), item["id"]))
    for project in ordered:
        safe_name = project["name"].replace("\t", " ").replace("\n", " ")
        sys.stdout.write(f"{project['id']}\t{safe_name}\n")


def _write_output(data: list[dict[str, Any]], output_path: str | None) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
    else:
        sys.stdout.write(payload)
        sys.stdout.write("\n")
