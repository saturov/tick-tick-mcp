# Design Doc: ticktick-skill

## Purpose

OpenCode-скилл для работы с задачами TickTick через CLI. Семь режимов:
список проектов, выгрузка всех открытых задач, выгрузка открытых задач без дат,
выгрузка выполненных задач за дату, помощь, обновление задачи и планирование дня/недели.

## Runtime Flow

```
Рабочая папка пользователя
├── .venv/                (опционально — виртуальное окружение)
├── tasks.json            (создаётся режимом 2)
├── snapshot.json         (создаётся режимом 3)
└── completed.json        (создаётся режимом 4)

При запуске скилла:
1. Агент проверяет окружение (venv, зависимости, TICKTICK_API_KEY)
2. Сообщает пользователю статус и что доступно
3. Выполняет запрошенный режим с учётом доступных данных

[Режим 1: projects]
  ticktick-projects
  → вывод id<TAB>name в stdout

[Режим 2: open-tasks]
  ticktick-tasks-open [--output file.json] [--project "Name"]
  → JSON со всеми открытыми задачами (опционально отфильтрованными по проекту или project folder)

[Режим 3: undated-tasks]
  ticktick-tasks-undated [--output file.json] [--project "Name"]
  → JSON с открытыми задачами без dueDate и startDate

[Режим 4: completed-tasks]
  ticktick-tasks-completed [--date YYYY-MM-DD] [--output file.json] [--project "Name"]
  → JSON с выполненными задачами за дату (только через логин/пароль)

[Режим 5: help]
  справка по всем командам

[Режим 6: update]
  ticktick-task-update <ID> [--due-date DATE] [--start-date DATE] [--title TEXT] [--priority N]
  → обновляет поля задачи через Open API (требует TICKTICK_API_KEY)

[Режим 7: planning]
  ticktick-plan [--period today|week|YYYY-MM-DD] [--work-start HH:MM] [--work-end HH:MM]
  → timezone-aware план дня/недели: календарь + эвристическое размещение задач
```

## Файловая структура

```
skills/ticktick-skill/
├── SKILL.md                  — инструкции агенту (все 7 режимов)
├── AGENTS.md                 — правила безопасности и валидация
├── ai/design-doc.md          — этот файл
├── references/
│   └── contracts.md          — параметры CLI и форматы вывода
└── scripts/
    ├── ticktick-projects       — список проектов
    ├── ticktick-tasks-open     — все открытые задачи
    ├── ticktick-tasks-undated  — открытые задачи без дат
    ├── ticktick-tasks-completed — выполненные задачи за дату
    ├── ticktick-task-update    — обновление полей задачи
    ├── ticktick-plan           — планирование дня/недели
    ├── requirements.txt        — зависимости (requests)
    └── ticktick_cli/
        ├── client.py           — HTTP транспорт, TickTickClient, аутентификация
        ├── api.py              — бизнес-логика: проекты, задачи, резолюция папок
        ├── projects.py         — команда ticktick-projects
        ├── tasks_open.py       — команда ticktick-tasks-open
        ├── tasks_undated.py    — команда ticktick-tasks-undated
        ├── tasks_completed.py  — команда ticktick-tasks-completed
        ├── task_update.py      — команда ticktick-task-update
        └── plan.py             — команда ticktick-plan
```

## Архитектура модулей

Трёхслойная структура с односторонними зависимостями:

```
client.py  ←  api.py  ←  command modules (tasks_*.py, projects.py, plan.py)
```

- **`client.py`** — HTTP, сессии, `TickTickClient`, `build_client()`, `open_api_get_json()`, `_make_retry_session()`
- **`api.py`** — `list_projects()`, `fetch_all_tasks()`, `resolve_project_ids()`, `resolve_selectors()`, output helpers
- **Command modules** — только фильтрация, форматирование и `main()`

## Key Design Decisions

- **Рабочая папка как workspace**: скилл работает в контексте папки, которую
  пользователь открыл в OpenCode. Все выходные файлы создаются там же.
- **Деградирующая функциональность**: каждый режим проверяет готовность окружения
  перед запуском. Никогда не падает молча — всегда объясняет что не так.
- **Python для всего детерминированного**: вся бизнес-логика — в Python-скриптах.
  Агент только оркестрирует запуск и интерпретирует результаты.
- **Два API-режима**: Open API (Bearer-токен, быстрее) и Web v2 (сессионная
  аутентификация, полный доступ). Режим 4 (`ticktick-tasks-completed`) работает
  только через Web v2, так как Open API не предоставляет endpoint для истории
  выполненных задач.
- **`fetch_all_tasks()` как единая точка входа**: заменяет дублировавшиеся функции
  `get_open_tasks()` и `get_open_tasks_without_dates()`. Принимает опциональный
  prebuilt client — избегает двойной аутентификации.
- **Без ticktick-py**: зависимость удалена. HTTP retry реализован напрямую через
  `requests.adapters.HTTPAdapter` + `urllib3.util.retry.Retry`.
- **Прогрессивное расширение лимита**: `ticktick-tasks-completed` автоматически
  увеличивает лимит запроса (200 → 400 → 800 → ... → 5000) для аккаунтов с большим
  количеством закрытых задач.
