"""Tests for ticktick_mcp.api — focused on ISO timestamp normalization."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

MCP_DIR = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, MCP_DIR)

from ticktick_mcp.api import (
    _normalize_iso_datetime,
    _normalize_task_dates,
    fetch_all_tasks,
)


class TestNormalizeIsoDatetime:
    """The TickTick Open API returns timestamps like '2026-06-14T21:00:00.000+0000'
    — missing colon in the offset. `datetime.fromisoformat()` rejects this on
    Python <3.11, so the MCP layer has to rewrite the string before it crosses
    the boundary."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # The exact shape that broke the assistant on 2026-06-19.
            ("2026-06-14T21:00:00.000+0000", "2026-06-14T21:00:00.000+00:00"),
            # Same problem with a positive offset.
            ("2026-06-14T21:00:00.000+0300", "2026-06-14T21:00:00.000+03:00"),
            # Bare date — no time component, must be left alone.
            ("2026-06-14", "2026-06-14"),
            # Already-valid strings (3.11+ accepts Z; 3.9/3.10 don't) pass
            # through unchanged so we never corrupt a working value.
            ("2026-06-14T21:00:00.000+00:00", "2026-06-14T21:00:00.000+00:00"),
            # None / empty stay as None / empty.
            (None, None),
            ("", ""),
            # Garbage that we can't parse: leave it alone rather than
            # silently rewrite into something misleading.
            ("not-a-date", "not-a-date"),
        ],
    )
    def test_round_trip(self, raw, expected):
        normalized = _normalize_iso_datetime(raw)
        assert normalized == expected
        # And every non-trivial output must be parseable on Python 3.9+.
        if isinstance(normalized, str) and "T" in normalized:
            datetime.fromisoformat(normalized)  # must not raise

    def test_normalize_handles_zulu_suffix(self):
        # `Z` is only valid on 3.11+. On 3.9/3.10 we'd rather leave the
        # value alone than corrupt it, so this is a passthrough.
        normalized = _normalize_iso_datetime("2026-06-14T21:00:00Z")
        assert normalized == "2026-06-14T21:00:00Z"


class TestNormalizeTaskDates:
    def test_rewrites_known_iso_fields_in_place(self):
        task = {
            "id": "t1",
            "dueDate": "2026-06-14T21:00:00.000+0000",
            "startDate": "2026-06-15T21:00:00.000+0000",
            "completedTime": "2026-06-16T21:00:00.000+0000",
            "title": "Untouched",
        }
        _normalize_task_dates(task)

        assert task["dueDate"] == "2026-06-14T21:00:00.000+00:00"
        assert task["startDate"] == "2026-06-15T21:00:00.000+00:00"
        assert task["completedTime"] == "2026-06-16T21:00:00.000+00:00"
        assert task["title"] == "Untouched"

    def test_ignores_non_dict(self):
        # Defensive: ticktick-py client occasionally yields non-dict entries
        # (e.g. dataclass-like objects). Don't crash on those.
        _normalize_task_dates(None)
        _normalize_task_dates("not a task")


class TestFetchAllTasksNormalizesDates:
    """End-to-end: a task dict that arrived with `+0000` offsets should come
    out the other side of `fetch_all_tasks` already fixed, so MCP handlers
    can parse it without per-call workarounds."""

    def test_api_key_path_normalizes_dates(self, monkeypatch):
        monkeypatch.setenv("TICKTICK_API_KEY", "test-key")

        fake_session = MagicMock()
        # `_make_retry_session()` is called inside fetch_all_tasks; the
        # project data is fetched via `open_api_get_json`. Mock that helper
        # to return one project containing one task with the broken date.
        from ticktick_mcp import api as api_mod

        def fake_open_api_get_json(*, session, url, api_key):
            assert "/project/p1/data" in url
            return {
                "tasks": [
                    {
                        "id": "t1",
                        "projectId": "p1",
                        "title": "All-day",
                        "dueDate": "2026-06-14T21:00:00.000+0000",
                        "startDate": "2026-06-14T21:00:00.000+0000",
                        "status": 0,
                    }
                ]
            }

        monkeypatch.setattr(api_mod, "_make_retry_session", lambda: fake_session)
        monkeypatch.setattr(api_mod, "open_api_get_json", fake_open_api_get_json)
        monkeypatch.setattr(
            api_mod,
            "_list_projects_with_api_key",
            lambda api_key: [{"id": "p1", "name": "Inbox"}],
        )

        results = fetch_all_tasks()
        assert len(results) == 1
        raw = results[0]["raw"]
        assert raw["dueDate"] == "2026-06-14T21:00:00.000+00:00"
        assert raw["startDate"] == "2026-06-14T21:00:00.000+00:00"
        # ...and a real `fromisoformat` call now succeeds.
        datetime.fromisoformat(raw["dueDate"])
