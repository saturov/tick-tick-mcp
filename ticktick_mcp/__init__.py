"""ticktick-mcp: public Python API for TickTick.

Re-exports the facade modules so consumers can do
`from ticktick_mcp import TickTickClient, fetch_all_tasks, create_task, ...`.
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

# --- MCP-style handlers are NOT re-exported here ---
# They are imported directly by server.py (from handlers.X).
# Re-exporting them here creates a circular import:
#   server.py -> handlers.tasks -> session.py -> ticktick_mcp.client ->
#   ticktick_mcp.__init__ -> handlers.tasks (still loading)
