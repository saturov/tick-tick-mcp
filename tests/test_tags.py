"""Tests for tools/tags.py handlers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

import tools.tags as tags_mod


class TestListTags:
    def test_success(self):
        s = MagicMock()
        s.list_tags.return_value = [{"name": "t1", "label": "Tag1"}]
        with patch.object(tags_mod, "get_session", return_value=s):
            result = tags_mod.handle_list_tags()
            assert result["count"] == 1
            assert result["tags"][0]["name"] == "t1"


class TestCreateTag:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.create_tag.return_value = {"name": "tag1", "label": "Tag1"}
        s.get_web_client.return_value = client
        with patch.object(tags_mod, "get_session", return_value=s):
            result = tags_mod.handle_create_tag(label="Tag1")
            assert result["tag"]["name"] == "tag1"


class TestUpdateTag:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.update_tag.return_value = {"name": "tag1", "label": "NewTag"}
        s.get_web_client.return_value = client
        with patch.object(tags_mod, "get_session", return_value=s):
            result = tags_mod.handle_update_tag(label="Tag1", new_label="NewTag")
            assert result["tag"]["label"] == "NewTag"


class TestDeleteTag:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.delete_tag.return_value = {"name": "Tag1", "deleted": True}
        s.get_web_client.return_value = client
        with patch.object(tags_mod, "get_session", return_value=s):
            result = tags_mod.handle_delete_tag(label="Tag1")
            assert result["tag"]["deleted"] is True


class TestMergeTags:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.merge_tags.return_value = {"name": "target", "label": "Target"}
        s.get_web_client.return_value = client
        with patch.object(tags_mod, "get_session", return_value=s):
            result = tags_mod.handle_merge_tags(source_label="Src", target_label="Target")
            assert result["tag"]["name"] == "target"


class TestBatchCreateTags:
    def test_success(self):
        s = MagicMock()
        client = MagicMock()
        client.create_tag.side_effect = [
            {"name": "a", "label": "A"},
            {"name": "b", "label": "B"},
        ]
        s.get_web_client.return_value = client
        with patch.object(tags_mod, "get_session", return_value=s):
            result = tags_mod.handle_batch_create_tags(
                tags=[{"label": "A"}, {"label": "B"}]
            )
            assert len(result["tags"]) == 2