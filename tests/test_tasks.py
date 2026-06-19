"""Tests for handlers/tasks.py handlers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

import handlers.tasks as tasks_mod
from session import _session


class TestGetTasks:
    def test_all_tasks(self):
        s = MagicMock()
        s.projects = []
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "fetch_all_tasks", return_value=[
                {"raw": {"id": "t1", "title": "Test", "status": 0}, "meta": {}}
            ]):
                result = tasks_mod.handle_get_tasks()
                assert result["count"] == 1
                assert result["tasks"][0]["title"] == "Test"

    def test_filtered_by_project(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "fetch_all_tasks", return_value=[
                {"raw": {"id": "t1", "title": "Test", "status": 0, "projectId": "p1"}, "meta": {}}
            ]) as mock_fetch:
                result = tasks_mod.handle_get_tasks(project_id="Work")
                mock_fetch.assert_called_once_with(selected_project_ids={"p1"})
                assert result["count"] == 1

    def test_excludes_completed(self):
        s = MagicMock()
        s.projects = []
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "fetch_all_tasks", return_value=[
                {"raw": {"id": "t1", "title": "Open", "status": 0}, "meta": {}},
                {"raw": {"id": "t2", "title": "Done", "status": 2}, "meta": {}},
            ]):
                result = tasks_mod.handle_get_tasks()
                assert result["count"] == 1
                assert result["tasks"][0]["title"] == "Open"


class TestGetTask:
    def test_found(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "fetch_all_tasks", return_value=[
                {"raw": {"id": "t1", "title": "Target"}, "meta": {}}
            ]):
                result = tasks_mod.handle_get_task(project_id="Work", task_id="t1")
                assert result["task"]["title"] == "Target"

    def test_not_found(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "fetch_all_tasks", return_value=[]):
                try:
                    tasks_mod.handle_get_task(project_id="Work", task_id="missing")
                except RuntimeError as exc:
                    assert "task not found" in str(exc)


class TestCreateTask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "_cli_create_task", return_value={"id": "new1", "title": "New"}):
                result = tasks_mod.handle_create_task(title="New")
                assert result["task"]["id"] == "new1"

    def test_with_project(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "_cli_create_task", return_value={"id": "new1"}) as mock_create:
                tasks_mod.handle_create_task(title="New", project_id="Work", priority=5)
                mock_create.assert_called_once_with(
                    title="New", project_id="p1",
                    start_date=None, due_date=None,
                    priority=5, content=None, all_day=None, time_zone=None
                )


class TestUpdateTask:
    def test_success(self):
        with patch.object(tasks_mod, "_cli_update_task", return_value={"id": "t1", "title": "Updated"}):
            result = tasks_mod.handle_update_task(task_id="t1", title="Updated")
            assert result["task"]["title"] == "Updated"


class TestCompleteTask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.complete_task.return_value = {"id": "t1", "completed": True}
        s.get_web_client.return_value = client
        with patch.object(tasks_mod, "get_session", return_value=s):
            result = tasks_mod.handle_complete_task(task_id="t1", project_id="Work")
            assert result["task"]["completed"] is True


class TestDeleteTask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.delete_task.return_value = {"id": "t1", "deleted": True}
        s.get_web_client.return_value = client
        with patch.object(tasks_mod, "get_session", return_value=s):
            result = tasks_mod.handle_delete_task(task_id="t1", project_id="Work")
            assert result["task"]["deleted"] is True


class TestMoveTask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id = MagicMock(side_effect=["p1", "p2"])
        client = MagicMock()
        client.move_task.return_value = {"id": "t1", "projectId": "p2"}
        s.get_web_client.return_value = client
        with patch.object(tasks_mod, "get_session", return_value=s):
            result = tasks_mod.handle_move_task(
                task_id="t1", from_project_id="Work", to_project_id="Personal"
            )
            assert result["task"]["projectId"] == "p2"


class TestGetCompletedTasks:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "get_completed_tasks_for_date", return_value=[
                {"raw": {"id": "t1", "title": "Done"}, "meta": {"completed_at": "2026-01-01"}}
            ]):
                result = tasks_mod.handle_get_completed_tasks(date="2026-01-01")
                assert result["count"] == 1


class TestMakeSubtask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.make_subtask.return_value = {"id": "t1", "parentId": "p1"}
        s.get_web_client.return_value = client
        with patch.object(tasks_mod, "get_session", return_value=s):
            result = tasks_mod.handle_make_subtask(
                task_id="t1", parent_id="p1", project_id="Work"
            )
            assert result["task"]["parentId"] == "p1"


class TestUncompleteTask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        s.api_key = "key"
        with patch.object(tasks_mod, "get_session", return_value=s):
            with patch.object(tasks_mod, "fetch_all_tasks", return_value=[
                {"raw": {"id": "t1", "status": 2}, "meta": {}}
            ]):
                with patch("ticktick_mcp.task_update._send_task_update", return_value={"id": "t1"}):
                    with patch("ticktick_mcp.task_update._make_retry_session", return_value=MagicMock()):
                        result = tasks_mod.handle_uncomplete_task(task_id="t1", project_id="Work")
                        assert result["task"]["id"] == "t1"


class TestRemoveSubtask:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.remove_subtask.return_value = {"id": "t1", "parentId": None}
        s.get_web_client.return_value = client
        with patch.object(tasks_mod, "get_session", return_value=s):
            result = tasks_mod.handle_remove_subtask(task_id="t1", project_id="Work")
            assert result["task"]["parentId"] is None