"""Test fixtures for ticktick-mcp tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS_DIR = str(
    Path(__file__).resolve().parents[2]
    / "skills"
    / "tick-tick-skill"
    / "skills"
    / "ticktick-skill"
    / "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

import pytest


@pytest.fixture(autouse=True)
def clear_session():
    import session as smod
    smod._session = None
    yield
    smod._session = None


@pytest.fixture
def mock_api_key():
    with patch.dict(os.environ, {"TICKTICK_API_KEY": "test-key-123"}, clear=False):
        yield


@pytest.fixture
def mock_web_creds():
    with patch.dict(os.environ, {
        "TICKTICK_USERNAME": "u",
        "TICKTICK_PASSWORD": "p",
    }, clear=False):
        yield


@pytest.fixture
def mock_both_auth(mock_api_key, mock_web_creds):
    yield