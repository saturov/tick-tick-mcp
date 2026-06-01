"""Tests for config.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

import config


class TestGetApiKey:
    def test_from_env(self):
        with patch.dict(os.environ, {"TICKTICK_API_KEY": "key"}, clear=False):
            assert config.get_api_key() == "key"

    def test_missing_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            try:
                config.get_api_key()
            except RuntimeError as exc:
                assert "TICKTICK_API_KEY" in str(exc)


class TestGetWebCredentials:
    def test_from_env(self):
        env = {"TICKTICK_USERNAME": "u", "TICKTICK_PASSWORD": "p"}
        with patch.dict(os.environ, env, clear=False):
            u, p = config.get_web_credentials()
            assert u == "u"
            assert p == "p"

    def test_missing_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            try:
                config.get_web_credentials()
            except RuntimeError as exc:
                assert "TICKTICK_USERNAME" in str(exc)