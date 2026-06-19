#!/usr/bin/env python3
"""TickTick MCP Server — full CRUD for tasks, projects, tags over stdio.

Implements MCP JSON-RPC 2.0 protocol without external dependencies.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from handlers.tasks import (
    handle_get_tasks, handle_get_task, handle_create_task,
    handle_update_task, handle_complete_task, handle_uncomplete_task,
    handle_delete_task, handle_delete_tasks, handle_move_task,
    handle_get_completed_tasks, handle_get_completed_tasks_range,
    handle_make_subtask, handle_remove_subtask,
)
from handlers.projects import (
    handle_list_projects, handle_get_project, handle_create_project,
    handle_update_project, handle_archive_project, handle_unarchive_project,
    handle_delete_project, handle_create_project_folder,
    handle_delete_project_folder,
)
from handlers.tags import (
    handle_list_tags, handle_create_tag, handle_update_tag,
    handle_delete_tag, handle_merge_tags, handle_batch_create_tags,
)

_SERVER_NAME = "ticktick-mcp"
_SERVER_VERSION = "0.1.0"

_TOOLS = [
    {
        "name": "get_tasks",
        "description": "List all open (uncompleted) tasks. Optionally filter by project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or name to filter by. Leave empty for all."},
            },
        },
    },
    {
        "name": "get_task",
        "description": "Get a single task by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or name"},
                "task_id": {"type": "string", "description": "Task ID"},
            },
            "required": ["project_id", "task_id"],
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "project_id": {"type": "string", "description": "Project ID or name"},
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD or ISO 8601)"},
                "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD or ISO 8601)"},
                "priority": {"type": "integer", "description": "0=none, 1=low, 3=medium, 5=high"},
                "content": {"type": "string", "description": "Task description/content"},
                "all_day": {"type": "boolean", "description": "Is this an all-day task?"},
                "time_zone": {"type": "string", "description": "Timezone string (e.g. Europe/Moscow)"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update task fields (title, dates, priority).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "title": {"type": "string", "description": "New title"},
                "start_date": {"type": "string", "description": "New start date (YYYY-MM-DD or ISO 8601)"},
                "due_date": {"type": "string", "description": "New due date (YYYY-MM-DD or ISO 8601)"},
                "priority": {"type": "integer", "description": "0=none, 1=low, 3=medium, 5=high"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "project_id": {"type": "string", "description": "Project ID or name"},
            },
            "required": ["task_id", "project_id"],
        },
    },
    {
        "name": "uncomplete_task",
        "description": "Remove completion status from a task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "project_id": {"type": "string", "description": "Project ID or name"},
            },
            "required": ["task_id", "project_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a single task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "project_id": {"type": "string", "description": "Project ID or name"},
            },
            "required": ["task_id", "project_id"],
        },
    },
    {
        "name": "delete_tasks_batch",
        "description": "Batch delete multiple tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "project_id": {"type": "string"},
                        },
                        "required": ["task_id", "project_id"],
                    },
                    "description": "List of {task_id, project_id} pairs",
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "move_task",
        "description": "Move a task to a different project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "from_project_id": {"type": "string", "description": "Source project ID or name"},
                "to_project_id": {"type": "string", "description": "Target project ID or name"},
            },
            "required": ["task_id", "from_project_id", "to_project_id"],
        },
    },
    {
        "name": "get_completed_tasks",
        "description": "Get tasks completed on a specific date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD. Defaults to today."},
                "project_id": {"type": "string", "description": "Filter by project ID or name"},
            },
        },
    },
    {
        "name": "get_completed_tasks_range",
        "description": "Get tasks completed in a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "project_id": {"type": "string", "description": "Filter by project ID or name"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "make_subtask",
        "description": "Turn a task into a subtask of a parent task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Child task ID"},
                "parent_id": {"type": "string", "description": "Parent task ID"},
                "project_id": {"type": "string", "description": "Project ID or name"},
            },
            "required": ["task_id", "parent_id", "project_id"],
        },
    },
    {
        "name": "remove_subtask",
        "description": "Remove subtask relationship (make it a regular task).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to un-parent"},
                "project_id": {"type": "string", "description": "Project ID or name"},
            },
            "required": ["task_id", "project_id"],
        },
    },
    {
        "name": "list_projects",
        "description": "List all active projects.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_project",
        "description": "Get a single project by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string", "description": "Project ID"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "create_project",
        "description": "Create a new project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name"},
                "color": {"type": "string", "description": "Hex color (e.g. #51b9e3)"},
                "project_type": {"type": "string", "description": "'TASK' or 'NOTE'"},
                "folder_id": {"type": "string", "description": "Parent folder ID"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_project",
        "description": "Update project fields.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "name": {"type": "string", "description": "New name"},
                "color": {"type": "string", "description": "New hex color"},
                "view_mode": {"type": "string", "description": "'kanban' or 'list'"},
                "closed": {"type": "boolean", "description": "Archive (true) or unarchive (false)"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "archive_project",
        "description": "Archive a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string", "description": "Project ID"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "unarchive_project",
        "description": "Unarchive a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string", "description": "Project ID"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "delete_project",
        "description": "Delete project(s).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of project IDs to delete",
                },
            },
            "required": ["project_ids"],
        },
    },
    {
        "name": "create_project_folder",
        "description": "Create a project folder (group).",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Folder name"}},
            "required": ["name"],
        },
    },
    {
        "name": "delete_project_folder",
        "description": "Delete project folder(s).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of folder IDs to delete",
                },
            },
            "required": ["folder_ids"],
        },
    },
    {
        "name": "list_tags",
        "description": "List all tags.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_tag",
        "description": "Create a new tag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Tag label"},
                "color": {"type": "string", "description": "Hex color"},
                "parent": {"type": "string", "description": "Parent tag label"},
                "sort_type": {"type": "integer", "description": "0=project, 1=dueDate, 2=title, 3=priority"},
            },
            "required": ["label"],
        },
    },
    {
        "name": "update_tag",
        "description": "Update a tag (rename, change color, change parent).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Current tag label"},
                "new_label": {"type": "string", "description": "New label (to rename)"},
                "color": {"type": "string", "description": "New hex color"},
                "parent": {"type": "string", "description": "New parent tag label (empty to ungroup)"},
            },
            "required": ["label"],
        },
    },
    {
        "name": "delete_tag",
        "description": "Delete a tag.",
        "inputSchema": {
            "type": "object",
            "properties": {"label": {"type": "string", "description": "Tag label to delete"}},
            "required": ["label"],
        },
    },
    {
        "name": "merge_tags",
        "description": "Merge source tag into target tag (deletes source).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_label": {"type": "string", "description": "Tag to merge (will be deleted)"},
                "target_label": {"type": "string", "description": "Tag to merge into (keeps)"},
            },
            "required": ["source_label", "target_label"],
        },
    },
    {
        "name": "batch_create_tags",
        "description": "Batch create multiple tags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "color": {"type": "string"},
                            "parent": {"type": "string"},
                            "sort_type": {"type": "integer"},
                        },
                        "required": ["label"],
                    },
                    "description": "List of tag objects to create",
                },
            },
            "required": ["tags"],
        },
    },
]

_TOOL_HANDLERS = {
    "get_tasks": handle_get_tasks,
    "get_task": handle_get_task,
    "create_task": handle_create_task,
    "update_task": handle_update_task,
    "complete_task": handle_complete_task,
    "uncomplete_task": handle_uncomplete_task,
    "delete_task": handle_delete_task,
    "delete_tasks_batch": handle_delete_tasks,
    "move_task": handle_move_task,
    "get_completed_tasks": handle_get_completed_tasks,
    "get_completed_tasks_range": handle_get_completed_tasks_range,
    "make_subtask": handle_make_subtask,
    "remove_subtask": handle_remove_subtask,
    "list_projects": lambda **kw: handle_list_projects(),
    "get_project": handle_get_project,
    "create_project": handle_create_project,
    "update_project": handle_update_project,
    "archive_project": handle_archive_project,
    "unarchive_project": handle_unarchive_project,
    "delete_project": handle_delete_project,
    "create_project_folder": handle_create_project_folder,
    "delete_project_folder": handle_delete_project_folder,
    "list_tags": lambda **kw: handle_list_tags(),
    "create_tag": handle_create_tag,
    "update_tag": handle_update_tag,
    "delete_tag": handle_delete_tag,
    "merge_tags": handle_merge_tags,
    "batch_create_tags": handle_batch_create_tags,
}


def _send_response(request_id: Any, result: Any) -> None:
    msg = json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False)
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _send_error(request_id: Any, code: int, message: str) -> None:
    msg = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
        ensure_ascii=False,
    )
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _handle_request(request: dict[str, Any]) -> None:
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        _send_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
        })
        return

    if method == "tools/list":
        _send_response(req_id, {"tools": _TOOLS})
        return

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = _TOOL_HANDLERS.get(tool_name)
        if handler is None:
            _send_response(req_id, {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            })
            return

        try:
            result = handler(**arguments)
            _send_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
            })
        except RuntimeError as exc:
            _send_response(req_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
        except Exception as exc:
            _send_response(req_id, {
                "content": [{"type": "text", "text": f"internal error: {exc}"}],
                "isError": True,
            })
        return

    if method == "notifications/initialized":
        return  # no response needed

    _send_error(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    while True:
        try:
            line = sys.stdin.readline()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _send_error(None, -32700, "Parse error")
            continue
        _handle_request(request)


if __name__ == "__main__":
    main()