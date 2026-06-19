"""Tests for ticktick_cli.tasks_undated — filtering and main."""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "skills" / "ticktick-skill" / "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import ticktick_cli.tasks_undated as mod


class FakeDateTime:
    @classmethod
    def now(cls, _tz):
        return datetime(2020, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# _missing_date
# ---------------------------------------------------------------------------

class TestMissingDate(unittest.TestCase):
    def test_none_is_missing(self):
        self.assertTrue(mod._missing_date(None))

    def test_empty_string_is_missing(self):
        self.assertTrue(mod._missing_date(""))

    def test_non_empty_not_missing(self):
        self.assertFalse(mod._missing_date("2020-01-01"))


# ---------------------------------------------------------------------------
# get_open_tasks_without_dates
# ---------------------------------------------------------------------------

class TestGetOpenTasksWithoutDates(unittest.TestCase):
    def test_api_key_path(self):
        with patch.object(mod, "fetch_all_tasks", return_value=[
            {"raw": {"status": 0, "dueDate": None, "startDate": "", "projectId": "p1"},
             "meta": {"fetched_at": "2020-01-01T00:00:00+00:00", "source": "ticktick-open-api"}},
            {"raw": {"status": 2, "dueDate": None, "startDate": None, "projectId": "p1"},
             "meta": {"fetched_at": "2020-01-01T00:00:00+00:00", "source": "ticktick-open-api"}},
            {"raw": {"status": 0, "dueDate": "2020-01-01", "startDate": None, "projectId": "p1"},
             "meta": {"fetched_at": "2020-01-01T00:00:00+00:00", "source": "ticktick-open-api"}},
        ]):
            result = mod.get_open_tasks_without_dates({"p1"})
        # Only open + no dates = 1 task
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["raw"]["projectId"], "p1")
        self.assertEqual(result[0]["meta"]["source"], "ticktick-open-api")

    def test_filters_out_completed(self):
        with patch.object(mod, "fetch_all_tasks", return_value=[
            {"raw": {"status": 2, "dueDate": None, "startDate": None},
             "meta": {"fetched_at": "...", "source": "test"}},
        ]):
            result = mod.get_open_tasks_without_dates()
        self.assertEqual(len(result), 0)

    def test_filters_out_dated(self):
        with patch.object(mod, "fetch_all_tasks", return_value=[
            {"raw": {"status": 0, "dueDate": "2020-01-01", "startDate": None},
             "meta": {"fetched_at": "...", "source": "test"}},
        ]):
            result = mod.get_open_tasks_without_dates()
        self.assertEqual(len(result), 0)

    def test_passes_selected_project_ids(self):
        captured = {}
        with patch.object(mod, "fetch_all_tasks",
                          side_effect=lambda selected_project_ids=None: captured.update(
                              {"ids": selected_project_ids}) or []):
            mod.get_open_tasks_without_dates(selected_project_ids={"p1", "p2"})
        self.assertEqual(captured["ids"], {"p1", "p2"})


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def test_with_project_filter(self):
        captured = {}
        with patch.object(mod, "list_projects", return_value=[{"id": "p1", "name": "Inbox"}]), \
             patch.object(mod, "resolve_project_ids", return_value={"p1"}), \
             patch.object(mod, "get_open_tasks_without_dates", return_value=[{"raw": {}}]), \
             patch.object(mod, "_write_output",
                          side_effect=lambda data, out: captured.update({"d": data, "o": out})):
            code = mod.main(["--project", "Inbox", "--output", "x.json"])
        self.assertEqual(code, 0)
        self.assertEqual(captured["d"], [{"raw": {}}])
        self.assertEqual(captured["o"], "x.json")

    def test_runtime_error(self):
        with patch.object(mod, "get_open_tasks_without_dates", side_effect=RuntimeError("sync failed")):
            err = io.StringIO()
            with redirect_stderr(err):
                code = mod.main([])
        self.assertEqual(code, 1)
        self.assertIn("sync failed", err.getvalue())

    def test_invalid_argument(self):
        err = io.StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit):
                mod.main(["--list-projects"])


if __name__ == "__main__":
    unittest.main()
