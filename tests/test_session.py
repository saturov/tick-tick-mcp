"""Tests for session.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

import session
from session import get_session, TickTickMCPSession


class TestTickTickMCPSession:
    def test_api_key_property(self):
        s = TickTickMCPSession()
        with patch.dict(os.environ, {"TICKTICK_API_KEY": "key"}, clear=False):
            assert s.api_key == "key"

    def test_get_web_client_creates_once(self):
        s = TickTickMCPSession()
        with patch.dict(os.environ, {"TICKTICK_USERNAME": "u", "TICKTICK_PASSWORD": "p"}, clear=False):
            with patch("session.TickTickClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.state = {"tasks": [], "tags": [], "projects": []}
                mock_client_class.return_value = mock_client

                c1 = s.get_web_client()
                c2 = s.get_web_client()
                assert c1 is c2
                mock_client_class.assert_called_once()

    def test_resolve_project_id_by_id(self):
        s = TickTickMCPSession()
        s._projects_cache = [
            {"id": "p1", "name": "Work"},
            {"id": "p2", "name": "Personal"},
        ]
        assert s.resolve_project_id("p1") == "p1"

    def test_resolve_project_id_by_name(self):
        s = TickTickMCPSession()
        s._projects_cache = [
            {"id": "p1", "name": "Work"},
            {"id": "p2", "name": "Personal"},
        ]
        assert s.resolve_project_id("work") == "p1"

    def test_resolve_project_id_not_found(self):
        s = TickTickMCPSession()
        s._projects_cache = [{"id": "p1", "name": "Work"}]
        try:
            s.resolve_project_id("nonexistent")
        except RuntimeError as exc:
            assert "project not found" in str(exc)

    def test_resolve_empty_raises(self):
        s = TickTickMCPSession()
        s._projects_cache = []
        try:
            s.resolve_project_id("")
        except RuntimeError as exc:
            assert "project identifier is required" in str(exc)

    def test_invalidate_cache(self):
        s = TickTickMCPSession()
        s._projects_cache = [{"id": "p1", "name": "Work"}]
        s.invalidate_cache()
        assert s._projects_cache is None

    def test_list_projects(self):
        s = TickTickMCPSession()
        with patch("session._cli_list_projects", return_value=[{"id": "p1", "name": "Work"}]):
            projects = s.list_projects()
            assert len(projects) == 1
            assert projects[0]["name"] == "Work"

    def test_list_tags(self):
        s = TickTickMCPSession()
        with patch.dict(os.environ, {"TICKTICK_USERNAME": "u", "TICKTICK_PASSWORD": "p"}, clear=False):
            with patch("session.TickTickClient") as mock_client_class:
                mock_client = MagicMock()
                mock_client.state = {"tags": [{"name": "tag1", "label": "Tag1"}]}
                mock_client_class.return_value = mock_client
                tags = s.list_tags()
                assert len(tags) == 1
                assert tags[0]["name"] == "tag1"


class TestGetSession:
    def test_returns_same_instance(self):
        with patch("session.TickTickMCPSession", return_value=MagicMock()):
            s1 = get_session()
            s2 = get_session()
            assert s1 is s2