"""Tests for tools/projects.py handlers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

import tools.projects as proj_mod


class TestListProjects:
    def test_success(self):
        s = MagicMock()
        s.projects = [{"id": "p1", "name": "Work"}]
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_list_projects()
            assert result["count"] == 1
            assert result["projects"][0]["name"] == "Work"


class TestGetProject:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.get_by_id.return_value = {"id": "p1", "name": "Work"}
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_get_project(project_id="p1")
            assert result["project"]["name"] == "Work"

    def test_not_found(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.get_by_id.return_value = {}
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            try:
                proj_mod.handle_get_project(project_id="p1")
            except RuntimeError as exc:
                assert "project not found" in str(exc)


class TestCreateProject:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.create_project.return_value = {"id": "p1", "name": "Test"}
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_create_project(name="Test")
            assert result["project"]["name"] == "Test"
            s.invalidate_cache.assert_called_once()


class TestUpdateProject:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.update_project.return_value = {"id": "p1", "name": "Updated"}
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_update_project(project_id="p1", name="Updated")
            assert result["project"]["name"] == "Updated"


class TestArchiveProject:
    def test_success(self):
        with patch.object(proj_mod, "handle_update_project", return_value={"project": {"id": "p1", "closed": True}}):
            result = proj_mod.handle_archive_project(project_id="p1")
            assert result["project"]["closed"] is True


class TestUnarchiveProject:
    def test_success(self):
        with patch.object(proj_mod, "handle_update_project", return_value={"project": {"id": "p1", "closed": False}}):
            result = proj_mod.handle_unarchive_project(project_id="p1")
            assert result["project"]["closed"] is False


class TestDeleteProject:
    def test_success(self):
        s = MagicMock()
        s.resolve_project_id.return_value = "p1"
        client = MagicMock()
        client.delete_project.return_value = [{"id": "p1", "deleted": True}]
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_delete_project(project_ids=["p1"])
            assert result["deleted"][0]["deleted"] is True


class TestCreateProjectFolder:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.create_folder.return_value = {"id": "f1", "name": "Folder"}
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_create_project_folder(name="Folder")
            assert result["folder"]["name"] == "Folder"


class TestDeleteProjectFolder:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.delete_folder.return_value = [{"id": "f1", "deleted": True}]
        s.get_web_client.return_value = client
        with patch.object(proj_mod, "get_session", return_value=s):
            result = proj_mod.handle_delete_project_folder(folder_ids=["f1"])
            assert result["deleted"][0]["deleted"] is True