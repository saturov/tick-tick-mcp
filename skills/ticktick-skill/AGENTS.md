# Local Rules for ticktick-skill

## Source of truth

- `SKILL.md` defines the runtime workflow for all 6 modes.
- `references/contracts.md` defines CLI parameters, output formats, and API boundaries.
- `ai/design-doc.md` describes architecture decisions.
- Low-level TickTick API and CRUD behavior lives in `ticktick_mcp/`.
- User workflows such as planning, filtering "today" tasks, and report formatting live in this bundled skill, not in MCP handlers.

## Working Directory

- Скилл работает в текущем рабочем каталоге пользователя.
- При запуске **всегда** проверяй наличие `.venv`, активирован ли он, и установлены ли зависимости.
- Не предполагай наличие `TICKTICK_API_KEY` — проверяй и сообщай пользователю статус.
- Скрипты живут в `skills/ticktick-skill/scripts/` относительно репозитория скилла.

## Safety

- Не выполняй команды TickTick без явного запроса пользователя (кроме `ls` и проверок окружения).
- Не запрашивай пароль интерактивно без предупреждения пользователя — сообщи что сейчас будет запрос.
- Выходные JSON-файлы могут содержать личные данные — напоминай пользователю об этом.
- Не перезаписывай существующие output-файлы без подтверждения.

## TickTick API Modes

Скилл поддерживает два режима аутентификации:

1. **Open API** (`TICKTICK_API_KEY`) — работает для `ticktick-projects`, `ticktick-tasks-open` и `ticktick-tasks-undated`. Быстрее, не требует логина/пароля.
2. **Web v2 API** (логин/пароль) — работает для всех четырёх команд. Единственный режим для `ticktick-tasks-completed`.

Если пользователь хочет `ticktick-tasks-completed` с API key — объясни ограничение и предложи использовать логин/пароль.

## Commands

- `skills/ticktick-skill/scripts/ticktick-plan`: планирует день/неделю: timezone-aware классификация задач, календарь свободных окон, эвристическое размещение с учётом приоритетов. Вывод в markdown или JSON (`--json`).

## Validation

```bash
python3 -m py_compile skills/ticktick-skill/scripts/ticktick-projects
python3 -m py_compile skills/ticktick-skill/scripts/ticktick-tasks-open
python3 -m py_compile skills/ticktick-skill/scripts/ticktick-tasks-undated
python3 -m py_compile skills/ticktick-skill/scripts/ticktick-tasks-completed
python3 -m py_compile skills/ticktick-skill/scripts/ticktick-plan
python3 skills/ticktick-skill/scripts/ticktick-projects --help
python3 skills/ticktick-skill/scripts/ticktick-tasks-open --help
python3 skills/ticktick-skill/scripts/ticktick-tasks-undated --help
python3 skills/ticktick-skill/scripts/ticktick-tasks-completed --help
python3 skills/ticktick-skill/scripts/ticktick-plan --help
```
