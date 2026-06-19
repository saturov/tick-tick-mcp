from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import sys
SCRIPTS_DIR = str(Path(__file__).resolve().parents[1] / "skills" / "ticktick-skill" / "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import ticktick_cli.plan as mod


class TestResolveTimezone(unittest.TestCase):
    def test_from_client_timezone(self):
        client = type("FakeClient", (), {"time_zone": "Europe/Moscow"})
        result = mod.resolve_timezone(client)
        self.assertEqual(result, ZoneInfo("Europe/Moscow"))

    def test_client_no_timezone_falls_back_to_local(self):
        client = type("FakeClient", (), {"time_zone": ""})
        result = mod.resolve_timezone(client)
        local = datetime.now().astimezone().tzinfo
        self.assertEqual(result, local)

    def test_client_none_falls_back_to_local(self):
        result = mod.resolve_timezone(None)
        local = datetime.now().astimezone().tzinfo
        self.assertEqual(result, local)

    def test_client_bad_timezone_falls_back_to_local(self):
        client = type("FakeClient", (), {"time_zone": "Mars/Nonexistent"})
        result = mod.resolve_timezone(client)
        local = datetime.now().astimezone().tzinfo
        self.assertEqual(result, local)


class TestResolvePeriod(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Europe/Moscow")

    def _mock_date_today(self, date_value):
        mock_date = MagicMock(wraps=date)
        mock_date.today.return_value = date_value
        return patch("ticktick_cli.plan.date", mock_date)

    def test_today(self):
        with self._mock_date_today(date(2026, 5, 25)):
            start, end = mod.resolve_period("today", self.tz)
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 25))

    def test_tomorrow(self):
        with self._mock_date_today(date(2026, 5, 25)):
            start, end = mod.resolve_period("tomorrow", self.tz)
        self.assertEqual(start, date(2026, 5, 26))
        self.assertEqual(end, date(2026, 5, 26))

    def test_week(self):
        with self._mock_date_today(date(2026, 5, 25)):
            start, end = mod.resolve_period("week", self.tz)
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 29))

    def test_week_wednesday(self):
        with self._mock_date_today(date(2026, 5, 27)):
            start, end = mod.resolve_period("week", self.tz)
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 29))

    def test_single_date(self):
        start, end = mod.resolve_period("2026-05-25", self.tz)
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 25))

    def test_date_range(self):
        start, end = mod.resolve_period("2026-05-25", self.tz, "2026-05-27")
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 27))

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            mod.resolve_period("garbage", self.tz)

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            mod.resolve_period("2026-13-01", self.tz)


class TestNormalizeTaskDate(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Europe/Moscow")

    def test_utc_with_offset_to_local(self):
        result = mod.normalize_task_date("2026-05-25T10:00:00.000+0000", self.tz)
        self.assertIsNotNone(result)
        self.assertEqual(result.date, date(2026, 5, 25))
        self.assertEqual(result.dt.hour, 13)  # UTC+3 = 13:00 MSK
        self.assertEqual(result.dt.minute, 0)
        self.assertFalse(result.is_all_day)

    def test_all_day_21_utc(self):
        result = mod.normalize_task_date("2026-05-25T21:00:00.000+0000", self.tz)
        self.assertIsNotNone(result)
        self.assertEqual(result.date, date(2026, 5, 25))
        self.assertTrue(result.is_all_day)

    def test_none_value(self):
        result = mod.normalize_task_date(None, self.tz)
        self.assertIsNone(result)

    def test_empty_string(self):
        result = mod.normalize_task_date("", self.tz)
        self.assertIsNone(result)

    def test_z_suffix(self):
        result = mod.normalize_task_date("2026-05-25T10:00:00.000Z", self.tz)
        self.assertIsNotNone(result)
        self.assertEqual(result.dt.hour, 13)
        self.assertFalse(result.is_all_day)

    def test_non_utc_timezone(self):
        result = mod.normalize_task_date("2026-05-25T10:00:00.000+0500", self.tz)
        self.assertIsNotNone(result)
        self.assertEqual(result.dt.hour, 8)  # +0500 to MSK(+0300) = 10-2 = 8


class TestClassifyTasks(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Europe/Moscow")
        self.period_dates = {date(2026, 5, 25)}
        self.project_map = {"proj1": "Project A", "proj2": "Project B"}

    def _task(self, **kw):
        return {
            "raw": kw,
            "meta": {"fetched_at": "2026-05-25T00:00:00.000+00:00", "source": "test"},
        }

    def test_fixed_has_time_today(self):
        tasks = [
            self._task(
                id="t1", title="Meeting", projectId="proj1", status=0,
                startDate="2026-05-25T10:00:00.000+0000",
                dueDate="2026-05-25T11:00:00.000+0000",
            )
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(len(result.fixed), 1)
        self.assertEqual(result.fixed[0]["title"], "Meeting")
        self.assertEqual(result.fixed[0]["project_name"], "Project A")

    def test_dated_flexible_all_day_today(self):
        tasks = [
            self._task(
                id="t2", title="Write post", projectId="proj1", status=0,
                dueDate="2026-05-25T21:00:00.000+0000",
            )
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(len(result.dated_flexible), 1)
        self.assertEqual(result.dated_flexible[0]["title"], "Write post")

    def test_dated_flexible_date_only_today(self):
        tasks = [
            self._task(
                id="t2", title="Write post", projectId="proj1", status=0,
                dueDate="2026-05-25",
            )
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(len(result.dated_flexible), 1)

    def test_overdue(self):
        tasks = [
            self._task(
                id="t3", title="Old task", projectId="proj1", status=0,
                dueDate="2026-05-20T21:00:00.000+0000",
            )
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(len(result.overdue), 1)
        self.assertEqual(result.overdue[0]["title"], "Old task")

    def test_backlog_no_dates(self):
        tasks = [
            self._task(id="t4", title="Someday", projectId="proj1", status=0)
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(len(result.backlog), 1)
        self.assertEqual(result.backlog[0]["title"], "Someday")

    def test_skips_completed(self):
        tasks = [
            self._task(id="t5", title="Done", projectId="proj1", status=2,
                       dueDate="2026-05-20T21:00:00.000+0000")
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(len(result.fixed), 0)
        self.assertEqual(len(result.overdue), 0)

    def test_fixed_other_day_in_period(self):
        tasks = [
            self._task(
                id="t6", title="Friday meeting", projectId="proj2", status=0,
                startDate="2026-05-29T09:00:00.000+0000",
                dueDate="2026-05-29T10:00:00.000+0000",
            )
        ]
        period = {date(2026, 5, 25), date(2026, 5, 29)}
        result = mod.classify_tasks(tasks, period, self.tz, self.project_map)
        self.assertEqual(len(result.fixed), 1)

    def test_unknown_project_name(self):
        tasks = [
            self._task(
                id="t7", title="Task", projectId="unknown_proj", status=0,
                dueDate="2026-05-20T21:00:00.000+0000",
            )
        ]
        result = mod.classify_tasks(tasks, self.period_dates, self.tz, self.project_map)
        self.assertEqual(result.overdue[0]["project_name"], "unknown_proj")


class TestBuildCalendar(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Europe/Moscow")
        self.period_dates = [date(2026, 5, 25)]

    def test_no_fixed_one_window(self):
        result = mod.build_calendar([], self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz)
        day = result[0]
        self.assertEqual(day["date"], "2026-05-25")
        self.assertEqual(len(day["free_windows"]), 1)
        self.assertEqual(day["free_windows"][0]["start"], "10:30")
        self.assertEqual(day["free_windows"][0]["end"], "19:00")
        self.assertEqual(day["free_windows"][0]["duration_min"], 510)

    def test_one_fixed_two_windows(self):
        fixed = [
            {"start": datetime(2026, 5, 25, 13, 0, tzinfo=self.tz),
             "due": datetime(2026, 5, 25, 14, 0, tzinfo=self.tz),
             "task": {"title": "Meeting"}}
        ]
        result = mod.build_calendar(fixed, self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz)
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 2)
        self.assertEqual(day["free_windows"][0], {"start": "10:30", "end": "13:00", "duration_min": 150})
        self.assertEqual(day["free_windows"][1], {"start": "14:00", "end": "19:00", "duration_min": 300})

    def test_overlapping_fixed_merged(self):
        fixed = [
            {"start": datetime(2026, 5, 25, 13, 0, tzinfo=self.tz),
             "due": datetime(2026, 5, 25, 14, 0, tzinfo=self.tz),
             "task": {"title": "M1"}},
            {"start": datetime(2026, 5, 25, 13, 30, tzinfo=self.tz),
             "due": datetime(2026, 5, 25, 14, 30, tzinfo=self.tz),
             "task": {"title": "M2"}},
        ]
        result = mod.build_calendar(fixed, self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz)
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 2)
        self.assertEqual(day["free_windows"][0], {"start": "10:30", "end": "13:00", "duration_min": 150})
        self.assertEqual(day["free_windows"][1], {"start": "14:30", "end": "19:00", "duration_min": 270})

    def test_fixed_before_work_clipped(self):
        fixed = [
            {"start": datetime(2026, 5, 25, 8, 0, tzinfo=self.tz),
             "due": datetime(2026, 5, 25, 11, 0, tzinfo=self.tz),
             "task": {"title": "Early"}}
        ]
        result = mod.build_calendar(fixed, self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz)
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 1)
        self.assertEqual(day["free_windows"][0]["start"], "11:00")

    def test_fixed_after_work_clipped(self):
        fixed = [
            {"start": datetime(2026, 5, 25, 18, 0, tzinfo=self.tz),
             "due": datetime(2026, 5, 25, 21, 0, tzinfo=self.tz),
             "task": {"title": "Late"}}
        ]
        result = mod.build_calendar(fixed, self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz)
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 1)
        self.assertEqual(day["free_windows"][0]["end"], "18:00")

    def test_lunch_without_fixed(self):
        result = mod.build_calendar([], self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz,
                                     lunch_start=time(13, 0),
                                     lunch_end=time(14, 0))
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 2)
        self.assertEqual(day["free_windows"][0], {"start": "10:30", "end": "13:00", "duration_min": 150})
        self.assertEqual(day["free_windows"][1], {"start": "14:00", "end": "19:00", "duration_min": 300})

    def test_lunch_merged_with_fixed(self):
        fixed = [
            {"start": datetime(2026, 5, 25, 12, 0, tzinfo=self.tz),
             "due": datetime(2026, 5, 25, 13, 30, tzinfo=self.tz),
             "task": {"title": "Meeting"}}
        ]
        result = mod.build_calendar(fixed, self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz,
                                     lunch_start=time(13, 0),
                                     lunch_end=time(14, 0))
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 2)
        self.assertEqual(day["free_windows"][0], {"start": "10:30", "end": "12:00", "duration_min": 90})
        self.assertEqual(day["free_windows"][1], {"start": "14:00", "end": "19:00", "duration_min": 300})

    def test_lunch_outside_work_hours_ignored(self):
        result = mod.build_calendar([], self.period_dates,
                                     work_start=time(14, 0),
                                     work_end=time(19, 0), tz=self.tz,
                                     lunch_start=time(13, 0),
                                     lunch_end=time(14, 0))
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 1)
        self.assertEqual(day["free_windows"][0]["start"], "14:00")

    def test_no_lunch_when_none(self):
        result = mod.build_calendar([], self.period_dates,
                                     work_start=time(10, 30),
                                     work_end=time(19, 0), tz=self.tz)
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 1)
        self.assertEqual(day["free_windows"][0]["duration_min"], 510)

    def test_now_dt_clamps_day_start(self):
        """now_dt mid-day should clip free windows to start from now, not work_start."""
        from datetime import datetime as dt
        day_date = self.period_dates[0]
        now = dt.combine(day_date, time(14, 30), tzinfo=self.tz)
        result = mod.build_calendar([], self.period_dates,
                                     work_start=time(9, 0),
                                     work_end=time(18, 0),
                                     tz=self.tz,
                                     now_dt=now)
        day = result[0]
        self.assertEqual(len(day["free_windows"]), 1)
        w = day["free_windows"][0]
        self.assertEqual(w["start"], "14:30")
        self.assertEqual(w["end"], "18:00")
        self.assertEqual(w["duration_min"], 210)

    def test_now_dt_after_work_end_gives_no_windows(self):
        """If now is past work_end, no free windows should remain."""
        from datetime import datetime as dt
        day_date = self.period_dates[0]
        now = dt.combine(day_date, time(19, 0), tzinfo=self.tz)
        result = mod.build_calendar([], self.period_dates,
                                     work_start=time(9, 0),
                                     work_end=time(18, 0),
                                     tz=self.tz,
                                     now_dt=now)
        day = result[0]
        self.assertEqual(day["free_windows"], [])

    def test_now_dt_only_clamps_today(self):
        """now_dt should not affect future days in the period."""
        from datetime import datetime as dt, timedelta
        today = self.period_dates[0]
        tomorrow = today + timedelta(days=1)
        now = dt.combine(today, time(16, 0), tzinfo=self.tz)
        result = mod.build_calendar([], [today, tomorrow],
                                     work_start=time(9, 0),
                                     work_end=time(18, 0),
                                     tz=self.tz,
                                     now_dt=now)
        # today: clamped to 16:00–18:00 = 120 min
        self.assertEqual(result[0]["free_windows"][0]["start"], "16:00")
        self.assertEqual(result[0]["free_windows"][0]["duration_min"], 120)
        # tomorrow: full 9:00–18:00 = 540 min
        self.assertEqual(result[1]["free_windows"][0]["start"], "09:00")
        self.assertEqual(result[1]["free_windows"][0]["duration_min"], 540)


class TestEstimateDuration(unittest.TestCase):
    def test_write_answer(self):
        self.assertEqual(mod.estimate_duration("Написать отчет"), 15)

    def test_check_review(self):
        self.assertEqual(mod.estimate_duration("Проверить логи"), 30)

    def test_call_discuss(self):
        self.assertEqual(mod.estimate_duration("Созвониться с командой"), 45)

    def test_prepare_plan(self):
        self.assertEqual(mod.estimate_duration("Подготовить презентацию"), 90)

    def test_design_analyze(self):
        self.assertEqual(mod.estimate_duration("Спроектировать архитектуру"), 180)

    def test_razobratsya_timebox(self):
        self.assertEqual(mod.estimate_duration("Разобраться с новым фреймворком"), 60)

    def test_default(self):
        self.assertEqual(mod.estimate_duration("Сделать что-то"), 60)

    def test_case_insensitive(self):
        self.assertEqual(mod.estimate_duration("НАПИСАТЬ пост"), 15)


class TestEstimateFocusType(unittest.TestCase):
    def test_quick_writing(self):
        self.assertEqual(mod.estimate_focus_type("Написать ответ"), "quick")

    def test_focus_design(self):
        self.assertEqual(mod.estimate_focus_type("Спроектировать модуль"), "focus")

    def test_communication_meeting(self):
        self.assertEqual(mod.estimate_focus_type("Обсудить план с Фисейским"), "communication")

    def test_decision_choose(self):
        self.assertEqual(mod.estimate_focus_type("Решить какой подход выбрать"), "decision")

    def test_default(self):
        self.assertEqual(mod.estimate_focus_type("Какая-то задача"), "quick")


class TestDetectWarnings(unittest.TestCase):
    def test_blocker_detected(self):
        tasks = [
            {"title": "Назначить встречу (жду ответ от Сапрыкина)", "priority": 0},
            {"title": "Обсудить план", "priority": 0},
        ]
        warnings = mod.detect_warnings(tasks, [], [], None)
        blocker = [w for w in warnings if w["type"] == "blocker"]
        self.assertEqual(len(blocker), 1)

    def test_no_blocker(self):
        tasks = [{"title": "Обсудить план", "priority": 0}]
        warnings = mod.detect_warnings(tasks, [], [], None)
        self.assertEqual(len(warnings), 0)

    def test_waiting_english(self):
        tasks = [{"title": "Waiting for feedback from team", "priority": 0}]
        warnings = mod.detect_warnings(tasks, [], [], None)
        blocker = [w for w in warnings if w["type"] == "blocker"]
        self.assertEqual(len(blocker), 1)

    def test_overload_warning(self):
        warnings = mod.detect_warnings([], [], [], {"total_free_min": 300, "total_planned_min": 450})
        overload = [w for w in warnings if w["type"] == "overload"]
        self.assertEqual(len(overload), 1)

    def test_no_overload(self):
        warnings = mod.detect_warnings([], [], [], {"total_free_min": 300, "total_planned_min": 240})
        overload = [w for w in warnings if w["type"] == "overload"]
        self.assertEqual(len(overload), 0)

    def test_many_overdue(self):
        tasks = [{"title": f"Task {i}", "project_name": "Найм", "priority": 0}
                 for i in range(10)]
        warnings = mod.detect_warnings(tasks, [], [], None)
        many = [w for w in warnings if w["type"] == "many_overdue"]
        self.assertEqual(len(many), 1)
        self.assertIn("10", many[0]["message"])

    def test_few_overdue_no_warning(self):
        tasks = [{"title": f"Task {i}", "project_name": "Найм", "priority": 0}
                 for i in range(3)]
        warnings = mod.detect_warnings(tasks, [], [], None)
        many = [w for w in warnings if w["type"] == "many_overdue"]
        self.assertEqual(len(many), 0)


class TestPlaceTasks(unittest.TestCase):
    def test_simple_placement(self):
        tasks = [
            {"title": "Quick task", "estimated_min": 15, "focus_type": "quick",
             "priority": 0, "id": "t1"}
        ]
        free_windows = [{"start": "10:30", "end": "13:00", "duration_min": 150}]
        plan, overflow = mod.place_tasks(tasks, free_windows, buffer_pct=20)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["tasks"][0]["title"], "Quick task")
        self.assertEqual(len(overflow), 0)

    def test_focus_not_in_small_window(self):
        tasks = [
            {"title": "Big focus", "estimated_min": 120, "focus_type": "focus",
             "priority": 5, "id": "t1"},
            {"title": "Quick task", "estimated_min": 15, "focus_type": "quick",
             "priority": 0, "id": "t2"},
        ]
        free_windows = [{"start": "10:30", "end": "11:00", "duration_min": 30}]
        plan, overflow = mod.place_tasks(tasks, free_windows, buffer_pct=0)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["tasks"][0]["title"], "Quick task")
        self.assertEqual(len(overflow), 1)
        self.assertEqual(overflow[0]["title"], "Big focus")

    def test_buffer_respected(self):
        tasks = [
            {"title": "Task", "estimated_min": 100, "focus_type": "quick",
             "priority": 0, "id": "t1"}
        ]
        free_windows = [{"start": "10:30", "end": "13:00", "duration_min": 150}]
        plan, overflow = mod.place_tasks(tasks, free_windows, buffer_pct=50)
        self.assertEqual(len(overflow), 1)

    def test_overflow_too_big_for_any_window(self):
        tasks = [
            {"title": "Huge task", "estimated_min": 300, "focus_type": "focus",
             "priority": 5, "id": "t1"},
        ]
        free_windows = [{"start": "10:30", "end": "13:00", "duration_min": 150}]
        plan, overflow = mod.place_tasks(tasks, free_windows, buffer_pct=0)
        self.assertEqual(len(plan), 0)
        self.assertEqual(len(overflow), 1)


class TestFormatMarkdown(unittest.TestCase):
    def test_empty_plan(self):
        plan_data = {
            "meta": {"period": {"start": "2026-05-25", "end": "2026-05-25"},
                     "timezone": "Europe/Moscow"},
            "calendar": [{"date": "2026-05-25", "work_start": "10:30", "work_end": "19:00",
                          "fixed_blocks": [], "free_windows": []}],
            "classified": mod.ClassifiedTasks(),
            "plan": [],
            "overflow": [],
            "warnings": [],
        }
        output = mod.format_markdown(plan_data)
        self.assertIn("# План на 25 мая", output)
        self.assertIn("Задач на сегодня нет", output)

    def test_with_tasks_and_warnings(self):
        plan_data = {
            "meta": {"period": {"start": "2026-05-25", "end": "2026-05-25"},
                     "timezone": "Europe/Moscow"},
            "calendar": [{"date": "2026-05-25", "work_start": "10:30", "work_end": "19:00",
                          "fixed_blocks": [
                              {"start": "13:00", "end": "14:00",
                               "task": {"title": "Ретроспектива"}}
                          ],
                          "free_windows": [
                              {"start": "10:30", "end": "13:00", "duration_min": 150}
                          ]}],
            "classified": mod.ClassifiedTasks(
                overdue=[{"title": "Old task", "project_name": "Найм", "priority": 5}],
            ),
            "plan": [{
                "window": {"start": "10:30", "end": "13:00", "duration_min": 150},
                "tasks": [{"title": "Quick", "estimated_min": 15, "focus_type": "quick"}],
            }],
            "overflow": [{"title": "Too big", "reason": "Не помещается"}],
            "warnings": [{"type": "blocker", "message": "Заблокирована"}],
        }
        output = mod.format_markdown(plan_data)
        self.assertIn("Ретроспектива", output)
        self.assertIn("Quick", output)
        self.assertIn("Too big", output)
        self.assertIn("Заблокирована", output)

    def test_fixed_blocks_as_tuples(self):
        """format_markdown should handle tuple fixed_blocks (from build_calendar)."""
        tz = ZoneInfo("Europe/Moscow")
        plan_data = {
            "meta": {"period": {"start": "2026-05-25", "end": "2026-05-25"},
                     "timezone": "Europe/Moscow"},
            "calendar": [{"date": "2026-05-25", "work_start": "10:30", "work_end": "19:00",
                          "fixed_blocks": [
                              (datetime(2026, 5, 25, 14, 0, tzinfo=tz),
                               datetime(2026, 5, 25, 15, 0, tzinfo=tz)),
                          ],
                          "free_windows": [
                              {"start": "10:30", "end": "14:00", "duration_min": 210},
                              {"start": "15:00", "end": "19:00", "duration_min": 240},
                          ]}],
            "classified": mod.ClassifiedTasks(),
            "plan": [],
            "overflow": [],
            "warnings": [],
        }
        output = mod.format_markdown(plan_data)
        self.assertIn("14:00–15:00", output)


class TestFormatJson(unittest.TestCase):
    def test_valid_json_output(self):
        plan_data = {
            "meta": {"period": {"start": "2026-05-25", "end": "2026-05-25"},
                     "timezone": "Europe/Moscow"},
            "calendar": [{"date": "2026-05-25", "work_start": "10:30", "work_end": "19:00",
                          "fixed_blocks": [], "free_windows": []}],
            "classified": mod.ClassifiedTasks(),
            "plan": [],
            "overflow": [],
            "warnings": [],
        }
        output = mod.format_json(plan_data)
        parsed = json.loads(output)
        self.assertEqual(parsed["meta"]["period"]["start"], "2026-05-25")
        self.assertIn("calendar", parsed)
        self.assertIn("tasks", parsed)



class FakeDateTime:
    fromisoformat = staticmethod(datetime.fromisoformat)
    combine = staticmethod(datetime.combine)
    timedelta = timedelta
    timezone = timezone
    time = time
    date = date

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc)


class TestMain(unittest.TestCase):
    def _make_project(self, pid, name):
        return {"id": pid, "name": name}

    def _make_wrapped_task(self, tid, title="Task", project_id="p1", status=0,
                           due_date=None, start_date=None, priority=0):
        return {
            "raw": {
                "id": tid, "title": title, "projectId": project_id,
                "status": status, "priority": priority,
                "dueDate": due_date, "startDate": start_date,
            },
            "meta": {"fetched_at": "2026-05-25T10:00:00+00:00", "source": "ticktick-open-api"},
        }

    @patch.object(mod, "ensure_venv_active")
    @patch.object(mod, "datetime", FakeDateTime)
    @patch("ticktick_cli.plan.date", wraps=date)
    def test_main_json_output(self, mock_date, mock_venv):
        mock_date.today.return_value = date(2026, 5, 25)

        proj_list = [self._make_project("p1", "Work"), self._make_project("p2", "Personal")]
        wrapped_tasks = [
            self._make_wrapped_task("t1", "Plan meeting", "p1",
                                    due_date="2026-05-25T21:00:00.000+0000"),
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            with patch.dict(os.environ, {"TICKTICK_API_KEY": "key123"}), \
                 patch.object(mod, "fetch_all_tasks", return_value=wrapped_tasks), \
                 patch.object(mod, "list_projects", return_value=proj_list):
                rc = mod.main(["--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("plan", data)

    @patch.object(mod, "ensure_venv_active")
    @patch.object(mod, "datetime", FakeDateTime)
    @patch("ticktick_cli.plan.date", wraps=date)
    def test_main_with_plan_project(self, mock_date, mock_venv):
        mock_date.today.return_value = date(2026, 5, 25)

        proj_list = [self._make_project("p1", "Work"), self._make_project("p2", "Personal")]
        wrapped_tasks = [
            self._make_wrapped_task("t2", "Work task", "p1",
                                    due_date="2026-05-25T10:00:00.000+0000",
                                    start_date="2026-05-25T10:00:00.000+0000"),
            self._make_wrapped_task("t1", "Personal task", "p2",
                                    due_date="2026-05-25T21:00:00.000+0000"),
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            with patch.dict(os.environ, {"TICKTICK_API_KEY": "key123"}), \
                 patch.object(mod, "fetch_all_tasks", return_value=wrapped_tasks), \
                 patch.object(mod, "list_projects", return_value=proj_list), \
                 patch.object(mod, "resolve_selectors", return_value={"p1"}):
                rc = mod.main(["--plan-project", "Work", "--json"])
        self.assertEqual(rc, 0)

    def test_main_invalid_period(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(mod, "ensure_venv_active"):
                rc = mod.main(["--period", "garbage"])
        self.assertEqual(rc, 1)
        self.assertIn("invalid period", buf.getvalue())

    def test_main_invalid_work_time(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(mod, "ensure_venv_active"):
                rc = mod.main(["--work-start", "25:00"])
        self.assertEqual(rc, 1)
        self.assertIn("invalid time", buf.getvalue())

    def test_main_invalid_lunch_time(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(mod, "ensure_venv_active"):
                rc = mod.main(["--lunch-start", "25:00", "--lunch-end", "26:00"])
        self.assertEqual(rc, 1)
        self.assertIn("invalid time", buf.getvalue())

    def test_main_lunch_passed_to_calendar(self):
        """Verify lunch params propagate correctly."""
        with patch.object(mod, "ensure_venv_active"), \
             patch.object(mod, "build_calendar", return_value=[]) as mock_cal:
            with patch.dict(os.environ, {"TICKTICK_API_KEY": "test"}), \
                 patch.object(mod, "fetch_all_tasks", return_value=[]), \
                 patch.object(mod, "list_projects", return_value=[]), \
                 patch.object(mod, "resolve_timezone", return_value=ZoneInfo("Europe/Moscow")):
                mod.main(["--lunch-start", "14:00", "--lunch-end", "15:00"])
                self.assertEqual(mock_cal.call_count, 1)
                args, _ = mock_cal.call_args
                self.assertEqual(args[5], time(14, 0))
                self.assertEqual(args[6], time(15, 0))

    def test_main_no_lunch_by_default(self):
        """Verify lunch is None when not explicitly set."""
        with patch.object(mod, "ensure_venv_active"), \
             patch.object(mod, "build_calendar", return_value=[]) as mock_cal:
            with patch.dict(os.environ, {"TICKTICK_API_KEY": "test"}), \
                 patch.object(mod, "fetch_all_tasks", return_value=[]), \
                 patch.object(mod, "list_projects", return_value=[]), \
                 patch.object(mod, "resolve_timezone", return_value=ZoneInfo("Europe/Moscow")):
                mod.main([])
                self.assertEqual(mock_cal.call_count, 1)
                args, _ = mock_cal.call_args
                self.assertIsNone(args[5])
                self.assertIsNone(args[6])

    def test_main_help(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            with patch.dict(os.environ, {}, clear=True):
                try:
                    rc = mod.main(["--help"])
                except SystemExit:
                    rc = 0
        self.assertEqual(rc, 0)
        self.assertIn("usage:", buf.getvalue())