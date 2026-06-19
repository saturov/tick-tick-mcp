from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "skills" / "ticktick-skill" / "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import ticktick_cli.task_update as mod


class TestMainCLI(unittest.TestCase):
    def test_mandatory_task_id_missing(self):
        with self.assertRaises(SystemExit):
            mod.main(argv=[])

    def test_no_updates_provided(self):
        with patch.object(mod, "update_task", side_effect=RuntimeError("at least one field to update is required")):
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                rc = mod.main(argv=["t1"])
        self.assertEqual(rc, 1)
        self.assertIn("at least one field", stderr.getvalue())

    def test_api_error_propagates(self):
        with patch.object(mod, "update_task", side_effect=RuntimeError("auth failed")):
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                rc = mod.main(argv=["t1", "--title", "X"])
        self.assertEqual(rc, 1)
        self.assertIn("auth failed", stderr.getvalue())

    def test_success_output(self):
        with patch.object(mod, "update_task", return_value={"id": "t1"}):
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                rc = mod.main(argv=["t1", "--title", "New"])
        self.assertEqual(rc, 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["id"], "t1")

    def test_with_all_args(self):
        with patch.object(mod, "update_task", return_value={"id": "t1"}) as mock_update:
            with patch("sys.stdout", new_callable=io.StringIO):
                rc = mod.main(argv=[
                    "t1",
                    "--start-date", "2026-05-19",
                    "--due-date", "2026-05-20",
                    "--title", "Updated",
                    "--priority", "5",
                ])
        self.assertEqual(rc, 0)
        mock_update.assert_called_once_with(
            task_id="t1",
            start_date="2026-05-19",
            due_date="2026-05-20",
            title="Updated",
            priority="5",
            complete=False,
            wont_do=False,
        )

    def test_complete_flag(self):
        with patch.object(mod, "update_task", return_value={"id": "t1", "completed": True}) as mock_update:
            with patch("sys.stdout", new_callable=io.StringIO):
                rc = mod.main(argv=["t1", "--complete"])
        self.assertEqual(rc, 0)
        self.assertTrue(mock_update.call_args.kwargs["complete"])

    def test_wont_do_flag(self):
        with patch.object(mod, "update_task", return_value={"id": "t1", "completed": True}) as mock_update:
            with patch("sys.stdout", new_callable=io.StringIO):
                rc = mod.main(argv=["t1", "--wont-do"])
        self.assertEqual(rc, 0)
        self.assertTrue(mock_update.call_args.kwargs["wont_do"])

    def test_complete_and_wont_do_conflict(self):
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            rc = mod.main(argv=["t1", "--complete", "--wont-do"])
        self.assertEqual(rc, 1)
        self.assertIn("cannot use", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
