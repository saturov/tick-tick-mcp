"""TickTick planning utility — timezone-aware day/week plan builder."""

from __future__ import annotations

import argparse
import json as _json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, time, timezone
import re
from zoneinfo import ZoneInfo

from ticktick_cli.mcp import (
    build_client,
    ensure_venv_active,
    fetch_all_tasks,
    list_projects,
    resolve_project_ids,
    resolve_selectors,
)


def resolve_timezone(client=None):
    if client is not None:
        tz_name = getattr(client, "time_zone", None)
        if tz_name:
            try:
                return ZoneInfo(tz_name)
            except Exception:
                pass
    return datetime.now().astimezone().tzinfo


def resolve_period(start_str, tz, end_str=None):
    if start_str == "today":
        today = date.today()
        return today, today
    if start_str == "tomorrow":
        today = date.today()
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    if start_str == "week":
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        return monday, friday
    start_date = date.fromisoformat(start_str)
    if end_str:
        return start_date, date.fromisoformat(end_str)
    return start_date, start_date


@dataclass
class DateInfo:
    dt: datetime
    is_all_day: bool
    date: date

    @staticmethod
    def from_raw(raw, tz):
        if not raw:
            return None
        s = str(raw).strip()
        s = s.replace("Z", "+00:00")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return DateInfo._from_date_only(s, tz)
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
        dt = datetime.fromisoformat(s)
        utc_dt = dt.astimezone(timezone.utc)
        local_dt = utc_dt.astimezone(tz)
        is_all_day = (utc_dt.hour == 21 and utc_dt.minute == 0 and utc_dt.second == 0)
        task_date = utc_dt.date() if is_all_day else local_dt.date()
        return DateInfo(dt=local_dt, is_all_day=is_all_day, date=task_date)

    @staticmethod
    def _from_date_only(s, tz):
        d = date.fromisoformat(s)
        dt = datetime.combine(d, time(0, 0), tzinfo=tz)
        return DateInfo(dt=dt, is_all_day=True, date=d)


@dataclass
class ClassifiedTasks:
    fixed: list = field(default_factory=list)
    dated_flexible: list = field(default_factory=list)
    overdue: list = field(default_factory=list)
    backlog: list = field(default_factory=list)


def classify_tasks(tasks, period_dates, tz, project_map):
    classified = ClassifiedTasks()

    for task_wrapper in tasks:
        raw = task_wrapper.get("raw", task_wrapper)
        if raw.get("status") == 2:
            continue

        due_info = normalize_task_date(raw.get("dueDate"), tz)
        start_info = normalize_task_date(raw.get("startDate"), tz)

        pid = raw.get("projectId", "")
        proj_name = project_map.get(pid, pid)

        flat = {
            "id": raw.get("id", ""),
            "title": raw.get("title", ""),
            "project_name": proj_name,
            "projectId": pid,
            "priority": raw.get("priority", 0),
        }

        if due_info:
            flat["due_date"] = due_info.date.isoformat()
            if not due_info.is_all_day:
                flat["due_dt"] = due_info.dt
        if start_info:
            flat["start_date"] = start_info.date.isoformat()
            if not start_info.is_all_day:
                flat["start_dt"] = start_info.dt

        date_candidates = []
        has_time = False

        for info in (due_info, start_info):
            if info is None:
                continue
            date_candidates.append(info.date)
            if not info.is_all_day:
                has_time = True

        if not date_candidates:
            classified.backlog.append(flat)
            continue

        for d in date_candidates:
            if d in period_dates:
                if has_time and not _all_dates_all_day(due_info, start_info):
                    classified.fixed.append(flat)
                else:
                    classified.dated_flexible.append(flat)
                break
        else:
            if any(d < min(period_dates) for d in date_candidates):
                classified.overdue.append(flat)

    return classified


def _all_dates_all_day(due_info, start_info):
    return all(
        info is None or info.is_all_day
        for info in (due_info, start_info)
        if info is not None
    )


def build_calendar(fixed_tasks, period_dates, work_start, work_end, tz,
                   lunch_start=None, lunch_end=None, now_dt=None):
    result = []

    for day_date in period_dates:
        day_start = datetime.combine(day_date, work_start, tzinfo=tz)
        day_end = datetime.combine(day_date, work_end, tzinfo=tz)

        if now_dt is not None and day_date == now_dt.date():
            now_floored = now_dt.replace(second=0, microsecond=0)
            if now_floored > day_start:
                day_start = min(now_floored, day_end)

        day_fixed = []
        for ft in fixed_tasks:
            s = ft["start"]
            d = ft.get("due", s + timedelta(hours=1))
            if s.date() != day_date and d.date() != day_date:
                continue
            day_fixed.append((max(s, day_start), min(d, day_end)))

        if lunch_start is not None and lunch_end is not None:
            lunch_s = datetime.combine(day_date, lunch_start, tzinfo=tz)
            lunch_e = datetime.combine(day_date, lunch_end, tzinfo=tz)
            if lunch_s < lunch_e and lunch_s >= day_start and lunch_e <= day_end:
                day_fixed.append((lunch_s, lunch_e, "lunch"))

        day_fixed.sort(key=lambda x: x[0])
        merged = []
        for item in day_fixed:
            s, e = item[0], item[1]
            tag = item[2] if len(item) > 2 else None
            if s >= e:
                continue
            if merged and s <= merged[-1][1]:
                existing_tag = merged[-1][2] if len(merged[-1]) > 2 else None
                new_tag = None
                if existing_tag or tag:
                    new_tag = existing_tag or tag
                merged[-1] = (merged[-1][0], max(merged[-1][1], e), new_tag) if new_tag else (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append(item if tag else (s, e))

        free_windows = []
        cursor = day_start
        for item in merged:
            s, e = item[0], item[1]
            if cursor < s:
                free_windows.append(_window_dict(cursor, s))
            cursor = max(cursor, e)
        if cursor < day_end:
            free_windows.append(_window_dict(cursor, day_end))

        total_free = sum(w["duration_min"] for w in free_windows)

        result.append({
            "date": day_date.isoformat(),
            "work_start": work_start.strftime("%H:%M"),
            "work_end": work_end.strftime("%H:%M"),
            "fixed_blocks": merged,
            "free_windows": free_windows,
            "total_free_min": total_free,
        })

    return result


def _window_dict(start, end):
    diff = (end - start).total_seconds() / 60
    return {
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
        "duration_min": int(diff),
    }


_DURATION_RULES = [
    (["написать", "ответить", "уточнить", "пингнуть", "скинуть", "отправить"], 15),
    (["проверить", "посмотреть", "залить", "смержить"], 30),
    (["созвониться", "обсудить", "согласовать", "обговорить", "встретиться"], 45),
    (["заполнить", "оформить", "завести", "навести порядок", "настроить"], 60),
    (["подготовить", "сформулировать", "разобрать", "наладить"], 90),
    (["спроектировать", "проанализировать", "распланировать"], 180),
    (["стратегия", "доклад", "презентация", "исследование", "ресёрч"], 240),
]


def estimate_duration(title):
    if not title:
        return 60
    lower = title.casefold()
    if lower.startswith("разобраться"):
        return 60
    for keywords, minutes in _DURATION_RULES:
        for kw in keywords:
            if kw in lower:
                return minutes
    return 60


_FOCUS_RULES = [
    (["спроектировать", "проанализировать", "подготовить", "реализовать",
      "разработать", "провести", "тестировать", "отладить"], "focus"),
    (["созвониться", "обсудить", "встретиться", "согласовать",
      "познакомиться", "обговорить", "назначить встречу", "назначить собеседование"], "communication"),
    (["решить", "выбрать", "принять решение", "утвердить"], "decision"),
]


def estimate_focus_type(title):
    if not title:
        return "quick"
    lower = title.casefold()
    for keywords, ftype in _FOCUS_RULES:
        for kw in keywords:
            if kw in lower:
                return ftype
    return "quick"


def detect_warnings(overdue_tasks, backlog_tasks, plan_tasks, plan_summary):
    warnings = []

    for task in overdue_tasks + backlog_tasks:
        title = task.get("title", "")
        low = title.casefold()
        if "жду" in low or "waiting" in low:
            warnings.append({
                "type": "blocker",
                "task_id": task.get("id", ""),
                "title": title,
                "message": f"Заблокирована: {title}",
            })

    if plan_summary:
        free = plan_summary.get("total_free_min", 0)
        planned = plan_summary.get("total_planned_min", 0)
        if planned > free and free > 0:
            warnings.append({
                "type": "overload",
                "free_min": free,
                "planned_min": planned,
                "message": f"Задачи на {planned//60}ч при {free//60}ч свободного времени",
            })

    overdue_per_project = {}
    for t in overdue_tasks:
        proj = t.get("project_name", "unknown")
        overdue_per_project.setdefault(proj, 0)
        overdue_per_project[proj] += 1

    for proj, count in overdue_per_project.items():
        if count >= 5:
            warnings.append({
                "type": "many_overdue",
                "project": proj,
                "count": count,
                "message": f"{count} просроченных задач в проекте «{proj}»",
            })

    return warnings


_FOCUS_MIN_WINDOW = {"focus": 60, "communication": 30, "decision": 30, "quick": 10}


def place_tasks(tasks, free_windows, buffer_pct=20):
    windows = [dict(w) for w in free_windows]
    total_free = sum(w["duration_min"] for w in windows)
    buffer_min = total_free * buffer_pct / 100.0
    available_min = total_free - buffer_min

    sorted_tasks = sorted(tasks,
                          key=lambda t: (-t.get("priority", 0),
                                         -t.get("estimated_min", 60)))

    sorted_windows = sorted(windows, key=lambda w: w["duration_min"])

    placed = []
    overflow = []

    for task in sorted_tasks:
        est = task.get("estimated_min", 60)
        ftype = task.get("focus_type", "quick")
        min_window = _FOCUS_MIN_WINDOW.get(ftype, 15)

        total_used = sum(w.get("used", 0) for w in windows)
        if total_used + est > available_min:
            overflow.append(dict(task, reason="Не помещается в оставшиеся окна"))
            continue

        best_win = None
        for w in sorted_windows:
            remaining = w["duration_min"] - w.get("used", 0)
            if remaining >= est and w["duration_min"] >= min_window:
                if best_win is None or remaining < best_win["duration_min"] - best_win.get("used", 0):
                    best_win = w

        if best_win is None:
            overflow.append(dict(task, reason="Не помещается в оставшиеся окна"))
            continue

        used = best_win.get("used", 0)
        if used == 0:
            placed.append({
                "window": {"start": best_win["start"], "end": best_win["end"],
                           "duration_min": best_win["duration_min"]},
                "tasks": [],
                "buffer_min": 0,
            })
        place = placed[-1]
        place["tasks"].append(task)
        best_win["used"] = used + est

    return placed, overflow


def format_markdown(plan_data):
    meta = plan_data["meta"]
    calendar = plan_data["calendar"]
    day = calendar[0] if calendar else {}
    start = meta["period"]["start"]
    end = meta["period"].get("end", start)

    if start == end:
        dt = date.fromisoformat(start)
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                   "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        date_str = f"{dt.day} {months[dt.month - 1]} ({weekdays[dt.weekday()]})"
    else:
        date_str = f"{start} — {end}"

    lines = [f"# План на {date_str}"]

    lines.append("")
    lines.append("## Фиксированные встречи")
    if day.get("fixed_blocks"):
        lines.append("")
        lines.append("| Время | Задача |")
        lines.append("|-------|--------|")
        for fb in day["fixed_blocks"]:
            if isinstance(fb, tuple):
                label = "Обед" if len(fb) > 2 and fb[2] == "lunch" else "—"
                lines.append(f"| {fb[0].strftime('%H:%M')}–{fb[1].strftime('%H:%M')} | {label} |")
            else:
                title = fb.get("task", {}).get("title", "—")
                lines.append(f"| {fb['start']}–{fb['end']} | {title} |")
    else:
        lines.append("")
        lines.append("Нет фиксированных встреч.")

    lines.append("")
    lines.append("## Свободные окна")
    if day.get("free_windows"):
        lines.append("")
        lines.append("| Окно | Длительность |")
        lines.append("|------|-------------|")
        for fw in day["free_windows"]:
            h = fw["duration_min"] // 60
            m = fw["duration_min"] % 60
            dur = f"{h}ч {m}м" if m else f"{h}ч"
            lines.append(f"| {fw['start']}–{fw['end']} | {dur} |")
        total = day.get("total_free_min", 0)
        lines.append(f"\n**Всего свободного времени:** {total // 60}ч {total % 60}м")

    lines.append("")
    lines.append("## Предлагаемый план")
    if plan_data["plan"]:
        for item in plan_data["plan"]:
            w = item["window"]
            h = w["duration_min"] // 60
            m = w["duration_min"] % 60
            dur = f"{h}ч {m}м" if m else f"{h}ч"
            lines.append("")
            lines.append(f"**{w['start']}–{w['end']}** ({dur})")
            for t in item["tasks"]:
                est = t.get("estimated_min", "?")
                lines.append(f"  • {t['title']} (~{est} мин)")
    else:
        lines.append("")
        lines.append("Задач на сегодня нет.")

    if plan_data["warnings"]:
        lines.append("")
        lines.append("## Предупреждения")
        for w in plan_data["warnings"]:
            lines.append(f"⚠ {w['message']}")

    if plan_data["overflow"]:
        lines.append("")
        lines.append("## Что не влезло")
        for item in plan_data["overflow"]:
            lines.append(f"• {item['title']} — {item.get('reason','')}")

    return "\n".join(lines)


def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return obj


def format_json(plan_data):
    simple = {
        "meta": plan_data["meta"],
        "calendar": _simplify_calendar(plan_data["calendar"]),
        "tasks": _simplify_classified(plan_data["classified"]),
        "plan": _serialize(plan_data["plan"]),
        "overflow": _serialize(plan_data["overflow"]),
        "warnings": plan_data["warnings"],
    }
    return _json.dumps(simple, ensure_ascii=False, indent=2)


def _simplify_calendar(calendar):
    result = []
    for day in calendar:
        result.append({
            "date": day["date"],
            "work_start": day["work_start"],
            "work_end": day["work_end"],
            "fixed_blocks": [{"start": fb[0].strftime("%H:%M"),
                               "end": fb[1].strftime("%H:%M"),
                               **({"label": fb[2]} if len(fb) > 2 else {})}
                             for fb in day.get("fixed_blocks", [])],
            "free_windows": day["free_windows"],
            "total_free_min": day.get("total_free_min", 0),
        })
    return result


def _simplify_classified(cls):
    def simplify(items):
        return [{"id": t.get("id",""), "title": t.get("title",""),
                 "project_name": t.get("project_name",""),
                 "priority": t.get("priority",0),
                 "estimated_min": t.get("estimated_min"),
                 "focus_type": t.get("focus_type")} for t in items]

    return {
        "fixed": simplify(cls.fixed),
        "dated_flexible": simplify(cls.dated_flexible),
        "overdue": simplify(cls.overdue),
        "backlog": simplify(cls.backlog),
    }


normalize_task_date = DateInfo.from_raw


_epilog = """
Examples:
  ticktick-plan                                       plan today, all projects
  ticktick-plan --period week                         plan this week
  ticktick-plan --work-start 10:30 --work-end 19:00   custom work hours
  ticktick-plan --plan-project Work                   focus on Work project
  ticktick-plan --skip-fixed-project Регулярное       skip recurring tasks from fixed blocks
  ticktick-plan --json                                machine-readable output
  ticktick-plan --output plan.json                    save to file
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plan your TickTick tasks with timezone-aware scheduling.",
        epilog=_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--period", nargs="+", default=["today"],
                        help="Planning period: today, tomorrow, week, YYYY-MM-DD [YYYY-MM-DD]")
    parser.add_argument("--work-start", default="09:00",
                        help="Work day start (HH:MM, default: 09:00)")
    parser.add_argument("--work-end", default="18:00",
                        help="Work day end (HH:MM, default: 18:00)")
    parser.add_argument("--lunch-start", default=None,
                        help="Lunch break start (HH:MM). Only applied when explicitly set.")
    parser.add_argument("--lunch-end", default=None,
                        help="Lunch break end (HH:MM). Only applied when explicitly set.")
    parser.add_argument("--plan-project", action="append", default=[],
                        metavar="NAME_OR_ID",
                        help="Project or folder to plan (repeatable)")
    parser.add_argument("--skip-fixed-project", action="append", default=[],
                        metavar="NAME_OR_ID",
                        help="Exclude project from fixed-block detection (repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of markdown")
    parser.add_argument("--output", help="Write to file instead of stdout")
    parser.add_argument("--timezone", help="Override auto-detected timezone")

    args = parser.parse_args(argv)

    try:
        ensure_venv_active()

        tz = resolve_timezone(None)
        if args.timezone:
            try:
                tz = ZoneInfo(args.timezone)
            except Exception:
                raise ValueError(f"invalid timezone: {args.timezone}")

        try:
            wh_start = time.fromisoformat(args.work_start)
            wh_end = time.fromisoformat(args.work_end)
        except ValueError:
            raise ValueError(f"invalid time format: {args.work_start} or {args.work_end}")

        lunch_start = None
        lunch_end = None
        if args.lunch_start is not None and args.lunch_end is not None:
            try:
                lunch_start = time.fromisoformat(args.lunch_start)
                lunch_end = time.fromisoformat(args.lunch_end)
            except ValueError:
                raise ValueError(f"invalid time format: {args.lunch_start} or {args.lunch_end}")

        period_args = args.period
        start_str = period_args[0]
        end_str = period_args[1] if len(period_args) > 1 else None
        try:
            period_start, period_end = resolve_period(start_str, tz, end_str)
        except (ValueError, IndexError) as e:
            raise ValueError(f"invalid period: {e}")

        period_dates = set()
        d = period_start
        while d <= period_end:
            period_dates.add(d)
            d += timedelta(days=1)

        api_key = os.environ.get("TICKTICK_API_KEY")

        if api_key:
            all_wrapped = fetch_all_tasks()
            client_for_tz = None
        else:
            client_for_tz = build_client()
            if not args.timezone:
                tz = resolve_timezone(client_for_tz)
            all_wrapped = fetch_all_tasks(client=client_for_tz)

        skip_fixed_ids: set[str] = set()
        if args.skip_fixed_project:
            projects = list_projects()
            for sp in args.skip_fixed_project:
                skip_fixed_ids.update(resolve_project_ids(projects, [sp]))

        plan_project_ids = None
        if args.plan_project:
            plan_project_ids = resolve_selectors(
                args.plan_project,
                api_key=api_key,
                client=client_for_tz,
            )

        projects_list = list_projects()
        project_map = {p["id"]: p["name"] for p in projects_list}

        plan_wrapped = all_wrapped
        if plan_project_ids:
            plan_wrapped = [
                w for w in all_wrapped
                if w["raw"].get("projectId") in plan_project_ids
            ]

        classified_all = classify_tasks(all_wrapped, period_dates, tz, project_map)
        classified_plan = classify_tasks(plan_wrapped, period_dates, tz, project_map)

        fixed_for_calendar = [
            tf for tf in classified_all.fixed
            if tf.get("projectId") not in skip_fixed_ids
        ]
        fixed_entries = []
        for tf in fixed_for_calendar:
            s = tf.get("start_dt") or tf.get("due_dt")
            d = tf.get("due_dt") or tf.get("start_dt")
            if s and d:
                fixed_entries.append({
                    "start": s, "due": d,
                    "task": {"title": tf.get("title", "")},
                })

        calendar = build_calendar(fixed_entries, sorted(period_dates),
                                  wh_start, wh_end, tz,
                                  lunch_start, lunch_end,
                                  now_dt=datetime.now(tz))

        for cat in [classified_plan.fixed, classified_plan.dated_flexible,
                     classified_plan.overdue, classified_plan.backlog]:
            for t in cat:
                t["estimated_min"] = estimate_duration(t.get("title", ""))
                t["focus_type"] = estimate_focus_type(t.get("title", ""))

        all_free = [fw for day in calendar for fw in day["free_windows"]]
        to_place = (classified_plan.dated_flexible +
                    classified_plan.overdue +
                    classified_plan.backlog)
        plan, overflow = place_tasks(to_place, all_free, buffer_pct=20)

        warnings = detect_warnings(
            classified_plan.overdue, classified_plan.backlog,
            plan, None)

        plan_data = {
            "meta": {
                "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
                "timezone": str(tz),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            "calendar": calendar,
            "classified": classified_plan,
            "plan": plan,
            "overflow": overflow,
            "warnings": warnings,
        }

        if args.json:
            output = format_json(plan_data)
        else:
            output = format_markdown(plan_data)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
                f.write("\n")
        else:
            sys.stdout.write(output)
            sys.stdout.write("\n")

    except (ValueError, RuntimeError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    return 0
