# ticktick-mcp

MCP (Model Context Protocol) server for [TickTick](https://ticktick.com). Exposes full CRUD for tasks, projects, and tags to MCP-compatible AI clients (e.g., Claude Desktop).

## Features

**Tasks**
- List open tasks (all projects or filtered by project)
- Get a single task by ID
- Create, update, complete, uncomplete, delete tasks
- Batch delete tasks
- Move tasks between projects
- Make/remove subtask relationships
- Get completed tasks by date or date range

**Projects**
- List, get, create, update projects
- Archive/unarchive projects
- Delete projects
- Create/delete project folders

**Tags**
- List, create, update, delete tags
- Merge tags
- Batch create tags

## Requirements

- Python 3.9+
- A [TickTick](https://ticktick.com) account

## Setup

This repo is self-contained — no sibling package needed.

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install the package:

```bash
pip install -e .
```

3. Set environment variables (or put them in your shell profile):

```bash
export TICKTICK_API_KEY="your_open_api_bearer_token"
export TICKTICK_USERNAME="your@email.com"
export TICKTICK_PASSWORD="your_password"
```

| Variable | Description |
|----------|-------------|
| `TICKTICK_API_KEY` | Bearer token from [TickTick Open API](https://developer.ticktick.com) |
| `TICKTICK_USERNAME` | TickTick account email |
| `TICKTICK_PASSWORD` | TickTick account password |

## Running

```bash
ticktick-mcp
```

The server communicates over `stdio` using JSON-RPC 2.0 (MCP protocol).

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "/path/to/.venv/bin/ticktick-mcp",
      "env": {
        "TICKTICK_API_KEY": "your_open_api_bearer_token",
        "TICKTICK_USERNAME": "your@email.com",
        "TICKTICK_PASSWORD": "your_password"
      }
    }
  }
}
```

## Development

Run tests:

```bash
pytest
```

## License

MIT
