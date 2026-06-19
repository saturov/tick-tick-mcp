"""ticktick-mcp: public Python API for TickTick.

Re-exports the facade modules so consumers can do
`from ticktick_mcp import TickTickClient, fetch_all_tasks, create_task, ...`.
"""

from __future__ import annotations

# --- Low-level client (auth, retry, sessions) ---
from ticktick_mcp.client import (  # noqa: F401
    TickTickClient,
    build_client,
    ensure_venv_active,
    _make_retry_session,
    _session_headers,
)

# --- Mid-level API (list/fetch/resolve) ---
from ticktick_mcp.api import (  # noqa: F401
    fetch_all_tasks,
    list_projects,
    resolve_project_ids,
    resolve_selectors,
    unwrap_task,
)

# --- Write paths (create/update with verification) ---
from ticktick_mcp.task_update import (  # noqa: F401
    create_task,
    update_task,
)

# --- Completed tasks (Web API only) ---
from ticktick_mcp.tasks_completed import (  # noqa: F401
    get_completed_tasks_for_date,
    get_completed_tasks_range,
)

_LAZY_EXPORTS = {
    "handle_archive_project": ("handlers.projects", "handle_archive_project"),
    "handle_create_project": ("handlers.projects", "handle_create_project"),
    "handle_create_project_folder": ("handlers.projects", "handle_create_project_folder"),
    "handle_delete_project": ("handlers.projects", "handle_delete_project"),
    "handle_delete_project_folder": ("handlers.projects", "handle_delete_project_folder"),
    "handle_get_project": ("handlers.projects", "handle_get_project"),
    "handle_list_projects": ("handlers.projects", "handle_list_projects"),
    "handle_unarchive_project": ("handlers.projects", "handle_unarchive_project"),
    "handle_update_project": ("handlers.projects", "handle_update_project"),
    "handle_batch_create_tags": ("handlers.tags", "handle_batch_create_tags"),
    "handle_create_tag": ("handlers.tags", "handle_create_tag"),
    "handle_delete_tag": ("handlers.tags", "handle_delete_tag"),
    "handle_list_tags": ("handlers.tags", "handle_list_tags"),
    "handle_merge_tags": ("handlers.tags", "handle_merge_tags"),
    "handle_update_tag": ("handlers.tags", "handle_update_tag"),
    "handle_complete_task": ("handlers.tasks", "handle_complete_task"),
    "handle_create_task": ("handlers.tasks", "handle_create_task"),
    "handle_delete_task": ("handlers.tasks", "handle_delete_task"),
    "handle_delete_tasks": ("handlers.tasks", "handle_delete_tasks"),
    "handle_get_completed_tasks": ("handlers.tasks", "handle_get_completed_tasks"),
    "handle_get_completed_tasks_range": ("handlers.tasks", "handle_get_completed_tasks_range"),
    "handle_get_task": ("handlers.tasks", "handle_get_task"),
    "handle_get_tasks": ("handlers.tasks", "handle_get_tasks"),
    "handle_make_subtask": ("handlers.tasks", "handle_make_subtask"),
    "handle_move_task": ("handlers.tasks", "handle_move_task"),
    "handle_remove_subtask": ("handlers.tasks", "handle_remove_subtask"),
    "handle_uncomplete_task": ("handlers.tasks", "handle_uncomplete_task"),
    "handle_update_task": ("handlers.tasks", "handle_update_task"),
    "Session": ("session", "TickTickMCPSession"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
