"""Tests for ticktick_cli.tasks_open — filtering and main."""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "skills" / "ticktick-skill" / "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import ticktick_cli.tasks_open as mod


# ---------------------------------------------------------------------------
# get_open_tasks
# ---------------------------------------------------------------------------

class TestGetOpenTasks(unittest.TestCase):
    def test_filters_completed(self):
        with patch.object(mod, "fetch_all_tasks", return_value=[
            {"raw": {"status": 0, "title": "open", "projectId": "p1"},
             "meta": {"source": "test"}},
            {"raw": {"status": 2, "title": "done", "projectId": "p1"},
             "meta": {"source": "test"}},
        ]):
            result = mod.get_open_tasks()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["raw"]["title"], "open")

    def test_passes_project_filter(self):
        captured = {}
        with patch.object(mod, "fetch_all_tasks",
                          side_effect=lambda selected_project_ids=None: captured.update(
                              {"ids": selected_project_ids}) or []):
            mod.get_open_tasks(selected_project_ids={"p1"})
        self.assertEqual(captured["ids"], {"p1"})

    def test_all_open_returned(self):
        with patch.object(mod, "fetch_all_tasks", return_value=[
            {"raw": {"status": 0, "title": "t1"}, "meta": {}},
            {"raw": {"status": 0, "title": "t2"}, "meta": {}},
            {"raw": {"status": 2, "title": "done"}, "meta": {}},
        ]):
            result = mod.get_open_tasks()
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def test_with_project(self):
        captured = {}
        with patch.object(mod, "resolve_selectors", return_value={"p1"}), \
             patch.object(mod, "get_open_tasks", return_value=[{"raw": {"id": "1"}}]), \
             patch.object(mod, "_write_output",
                          side_effect=lambda data, out: captured.update({"data": data, "output": out})):
            code = mod.main(["--project", "Work", "--output", "out.json"])
        self.assertEqual(code, 0)
        self.assertEqual(captured["data"], [{"raw": {"id": "1"}}])
        self.assertEqual(captured["output"], "out.json")

    def test_without_project(self):
        captured = {}
        with patch.object(mod, "get_open_tasks", return_value=[{"raw": {"id": "1"}}]), \
             patch.object(mod, "_write_output",
                          side_effect=lambda data, out: captured.update({"data": data, "output": out})):
            code = mod.main([])
        self.assertEqual(code, 0)
        self.assertIsNone(captured["output"])

    def test_runtime_error(self):
        with patch.object(mod, "get_open_tasks", side_effect=RuntimeError("sync failed")):
            err = io.StringIO()
            with redirect_stderr(err):
                code = mod.main([])
        self.assertEqual(code, 1)
        self.assertIn("sync failed", err.getvalue())

    def test_help(self):
        out = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                mod.main(["--help"])
        self.assertIn("open TickTick tasks", out.getvalue())


if __name__ == "__main__":
    unittest.main()
