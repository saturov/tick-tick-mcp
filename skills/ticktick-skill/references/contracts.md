# Artifact Contracts — ticktick-skill v1

## Рабочая папка пользователя

Скилл работает с текущим рабочим каталогом. Все файлы опциональны:

| Файл | Обязателен | Описание |
|------|-----------|----------|
| `.venv/` | да* | Виртуальное окружение Python с `ticktick-py` |
| `snapshot.json` | нет | Результат `ticktick-tasks-undated` (создаётся по `--output`) |
| `completed.json` | нет | Результат `ticktick-tasks-completed` (создаётся по `--output`) |

*Требуется для запуска скриптов.

## Переменные окружения

| Переменная | Обязательна | Описание |
|------------|------------|----------|
| `TICKTICK_API_KEY` | нет | Токен TickTick Open API. Если задан — используется Bearer-аутентификация |
| `TICKTICK_USERNAME` | нет | Логин TickTick (если не задан API key) |
| `TICKTICK_PASSWORD` | нет | Пароль TickTick (если не задан API key) |

## ticktick-projects

Выводит список активных проектов (закрытые исключаются).

### CLI

```
ticktick-projects [--help]
```

### Формат вывода

```
<project_id><TAB><project_name>
```

Строки отсортированы по имени проекта (case-insensitive). Табуляции и переносы строк в именах заменяются на пробелы.

### Поддерживаемые API

- Open API (`TICKTICK_API_KEY`) — `GET /open/v1/project`
- Web v2 API (логин/пароль) — через `_SessionTickTickClient` и `batch/check/0`

---

## ticktick-tasks-undated

Выгружает открытые задачи без `dueDate` и `startDate`.

### CLI

| Параметр | Обязателен | По умолчанию | Описание |
|----------|-----------|--------------|----------|
| `--output` | нет | stdout | Путь к JSON-файлу |
| `--project` | нет | все | Имя или ID проекта. Повторяемый. |

### Формат вывода

JSON-массив:

```json
[
  {
    "raw": { "id": "...", "title": "...", "projectId": "...", ... },
    "meta": {
      "fetched_at": "2026-05-17T...",
      "source": "ticktick-open-api" | "ticktick-py"
    }
  }
]
```

- `raw` — все поля задачи как есть из API
- `meta.fetched_at` — ISO-8601 UTC
- `meta.source` — `"ticktick-open-api"` (через API key) или `"ticktick-py"` (через сессию)

### Логика фильтрации

- `status != 2` (открытая)
- `dueDate is None or ""` (без даты выполнения)
- `startDate is None or ""` (без даты начала)
- Если задан `--project` — дополнительно `projectId in selected_project_ids`

### Поддерживаемые API

- Open API (`TICKTICK_API_KEY`) — `GET /open/v1/project` + `GET /open/v1/project/{id}/data`
- Web v2 API (логин/пароль) — через `_SessionTickTickClient` и `batch/check/0`

---

## ticktick-tasks-completed

Выгружает задачи, выполненные за указанную дату.

### CLI

| Параметр | Обязателен | По умолчанию | Описание |
|----------|-----------|--------------|----------|
| `--date` | нет | сегодня | Дата в YYYY-MM-DD |
| `--output` | нет | stdout | Путь к JSON-файлу |
| `--project` | нет | все | Имя или ID проекта. Повторяемый. |

### Формат вывода

JSON-массив, отсортированный по `completed_at`:

```json
[
  {
    "raw": { "id": "...", "title": "...", "completedTime": "2026-03-26T09:07:10.000+0000", "projectName": "Work", ... },
    "meta": {
      "completed_at": "2026-03-26T09:07:10.000+0000",
      "fetched_at": "2026-05-17T...",
      "source": "ticktick-web-v2-closed"
    }
  }
]
```

- `raw` — все поля задачи + `projectName` (имя проекта, разрешённое из состояния клиента)
- `meta.completed_at` — время выполнения в исходном формате TickTick
- `meta.fetched_at` — ISO-8601 UTC
- `meta.source` — всегда `"ticktick-web-v2-closed"`

### Логика

1. Запрашивает `/project/all/closed?status=Completed&limit=N` с прогрессивным расширением лимита
2. Останавливается когда самая старая задача в ответе достигла или прошла целевую дату
3. Фильтрует локально по `completedTime` и опционально по `projectId`
4. Лимит: начальный 200, максимальный 5000

### Поддерживаемые API

- **Только Web v2 API** (логин/пароль). Open API не поддерживает endpoint для истории выполненных задач.

---

## ticktick-tasks-open

Выгружает все открытые задачи (без фильтрации по датам).

### CLI

| Параметр | Обязателен | По умолчанию | Описание |
|----------|-----------|--------------|----------|
| `--output` | нет | stdout | Путь к JSON-файлу |
| `--project` | нет | все | Имя или ID проекта, или имя project folder. Повторяемый. |

### Формат вывода

JSON-массив:

```json
[
  {
    "raw": { "id": "...", "title": "...", "projectId": "...", ... },
    "meta": {
      "fetched_at": "2026-05-17T...",
      "source": "ticktick-open-api" | "ticktick-py"
    }
  }
]
```

- `raw` — все поля задачи как есть из API
- `meta.fetched_at` — ISO-8601 UTC
- `meta.source` — `"ticktick-open-api"` (через API key) или `"ticktick-py"` (через сессию)

### Логика фильтрации

- `status != 2` (открытая)
- Если задан `--project` — дополнительно `projectId in selected_project_ids`

### Project folders

`--project` поддерживает имена project folders (групп проектов). При совпадении с именем folder'а в выборку включаются все открытые проекты внутри него. Разрешение folder'ов:

- **Web v2 API** (логин/пароль): полная поддержка через `project_folders` из состояния клиента
- **Open API** (`TICKTICK_API_KEY`): ограниченная поддержка — folder разрешается по `groupId` проектов (имя folder'а из API недоступно, используется `groupId` как fallback-имя)

### Поддерживаемые API

- Open API (`TICKTICK_API_KEY`) — `GET /open/v1/project` + `GET /open/v1/project/{id}/data`
- Web v2 API (логин/пароль) — через `_SessionTickTickClient` и `batch/check/0`

---

## Разрешение имён проектов (`--project`)

| Сценарий | Результат |
|----------|----------|
| Точное совпадение ID | ID используется напрямую |
| Точное совпадение имени (case-insensitive) | ID проекта используется |
| Несколько проектов с одинаковым именем | Ошибка `project name is ambiguous: <name>. use id: <id1>, <id2>` |
| Имя не найдено | Ошибка `project not found: <name>` (или `project or folder not found: <name>` в `ticktick-tasks-open`) |

---

## Exit Codes

| Код | Значение |
|-----|---------|
| 0 | Успех |
| 1 | Ошибка (`auth failed`, `sync failed`, `unexpected response`, `project not found`, `invalid date`) |

## Сообщения об ошибках

| Сообщение | Причина |
|-----------|---------|
| `auth failed` | Неверный логин/пароль или API key |
| `sync failed` | Сетевая ошибка или превышен лимит запросов |
| `unexpected response` | Некорректный JSON или неожиданная структура ответа |
| `project not found: <name>` | Проект с указанным именем/ID не найден |
| `project or folder not found: <name>` | Проект или folder с указанным именем/ID не найден (в `ticktick-tasks-open`) |
| `project name is ambiguous: <name>. use id: <ids>` | Несколько проектов с одинаковым именем |
| `invalid date` | Неверный формат даты (нужен YYYY-MM-DD) |
