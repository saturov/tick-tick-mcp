from __future__ import annotations

from typing import Any

from session import get_session


def handle_list_projects() -> dict[str, Any]:
    session = get_session()
    projects = session.projects
    return {"projects": projects, "count": len(projects)}


def handle_get_project(project_id: str) -> dict[str, Any]:
    session = get_session()
    resolved = session.resolve_project_id(project_id)
    client = session.get_web_client()
    project = client.get_by_id(resolved, search="projects")
    if not project:
        raise RuntimeError(f"project not found: {project_id}")
    return {"project": project}


def handle_create_project(
    name: str,
    color: str = "#51b9e3",
    project_type: str = "TASK",
    folder_id: str = "",
) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.create_project(
        name=name, color=color, project_type=project_type, folder_id=folder_id
    )
    session.invalidate_cache()
    return {"project": result}


def handle_update_project(
    project_id: str,
    name: str = "",
    color: str = "",
    view_mode: str = "",
    closed: bool | None = None,
) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved = session.resolve_project_id(project_id)
    result = client.update_project(
        project_id=resolved,
        name=name,
        color=color,
        view_mode=view_mode,
        closed=closed,
    )
    session.invalidate_cache()
    return {"project": result}


def handle_archive_project(project_id: str) -> dict[str, Any]:
    return handle_update_project(project_id=project_id, closed=True)


def handle_unarchive_project(project_id: str) -> dict[str, Any]:
    return handle_update_project(project_id=project_id, closed=False)


def handle_delete_project(project_ids: list[str]) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    resolved_ids = [session.resolve_project_id(pid) for pid in project_ids]
    result = client.delete_project(resolved_ids)
    session.invalidate_cache()
    return {"deleted": result}


def handle_create_project_folder(name: str) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.create_folder(name=name)
    return {"folder": result}


def handle_delete_project_folder(folder_ids: list[str]) -> dict[str, Any]:
    session = get_session()
    client = session.get_web_client()
    result = client.delete_folder(folder_ids)
    return {"deleted": result}