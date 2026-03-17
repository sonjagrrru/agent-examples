# Simple Agent

A minimal single-agent in Python using the **Anthropic native tool_use API**.
It has dedicated tools for common operations plus a `run_command` tool that can execute any PowerShell command.

## Structure

```
simple-agent/
├── main.py      ← Terminal entry point
├── gui.py       ← GUI entry point (Tkinter chat window)
├── agent.py     ← SimpleAgent class (orchestration)
├── client.py    ← AnthropicClient (HTTP calls to Anthropic API)
├── tools.py     ← Tool definitions (JSON schemas) + executors
├── ui.py        ← Terminal UI (colors, prompts)
└── README.md
```

## How it works

```
User -> message -> Anthropic model (with tools JSON schemas)
                       |
                  model picks tool + arguments (natively)
                       |
                  agent executes tool -> result back to model
                       |
                  model returns final text to user
```

The model decides on its own: use a tool or respond with text.
For general questions (chat, math, dates...) the model answers directly.
For actions on the computer (files, apps, shell commands) it uses tools.

## Running

Terminal mode:
```powershell
$env:ANTHROPIC_API_KEY = "your_key"
python main.py
```

GUI mode (Tkinter chat window):
```powershell
python gui.py
```

Optional:
```powershell
$env:ANTHROPIC_MODEL = "claude-haiku-4-5"   # default
```

Without an API key the agent runs in fallback mode (direct commands only).

## Tools (model chooses automatically)

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `open_app` | Start an application | no |
| `close_app` | Kill a process | **yes** |
| `mkdir` | Create a folder | no |
| `create_file` | Create a file | no |
| `write_file` | Write to a file | **yes** |
| `read_file` | Read a file | no |
| `list_dir` | List directory contents | no |
| `delete` | Delete a file or folder (recursively) | **yes** |
| `run_command` | Run any PowerShell command | **yes** |

## Adding a new tool

1. Add a JSON schema to the `TOOLS` list in `tools.py`
2. Write an executor function (`def _exec_my_tool(args: dict) -> str`)
3. Register it in the `_EXECUTORS` dict
4. If risky, add its name to the `RISKY_TOOLS` set

The model will automatically see and use the new tool.
