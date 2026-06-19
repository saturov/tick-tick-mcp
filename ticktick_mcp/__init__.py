"""ticktick-mcp: public Python API for TickTick.

Re-exports the facade modules so consumers can do
`from ticktick_mcp import handle_get_tasks, TickTickClient, ...`.
"""

from __future__ import annotations

# --- Low-level client (auth, retry, sessions) ---
from ticktick_mcp.client import (  # noqa: F401
    TickTickClient,
    build_client,
    _make_retry_session,
    _session_headers,
)

# --- Mid-level API (list/fetch/resolve) ---
from ticktick_mcp.api import (  # noqa: F401
    fetch_all_tasks,
    list_projects,
    resolve_project_ids,
    resolve_selectors,
)

# --- Write paths (create/update with verification) ---
from ticktick_mcp.cli.task_update import (  # noqa: F401
    create_task,
    update_task,
)

# --- Completed tasks (Web API only) ---
from ticktick_mcp.cli.tasks_completed import (  # noqa: F401
    get_completed_tasks_for_date,
    get_completed_tasks_range,
)

# --- MCP-style handlers (return JSON-RPC-shaped dicts) ---
from tools.tasks import (  # noqa: F401
    handle_get_tasks,
    handle_get_task,
    handle_create_task,
    handle_update_task,
    handle_complete_task,
    handle_uncomplete_task,
    handle_delete_task,
    handle_delete_tasks,
    handle_move_task,
    handle_get_completed_tasks,
    handle_get_completed_tasks_range,
    handle_make_subtask,
    handle_remove_subtask,
)
from tools.projects import (  # noqa: F401
    handle_list_projects,
    handle_get_project,
    handle_create_project,
    handle_update_project,
    handle_archive_project,
    handle_unarchive_project,
    handle_delete_project,
    handle_create_project_folder,
    handle_delete_project_folder,
)
from tools.tags import (  # noqa: F401
    handle_list_tags,
    handle_create_tag,
    handle_update_tag,
    handle_delete_tag,
    handle_merge_tags,
    handle_batch_create_tags,
)
