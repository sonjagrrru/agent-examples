from __future__ import annotations

import os
from pathlib import Path
import subprocess


# ---------------------------------------------------------------------------
# Tool definitions — JSON schemas that the Anthropic model sees natively
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "open_app",
        "description": "Start an application on the user's Windows computer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Executable name or full path, e.g. 'notepad.exe'."},
            },
            "required": ["target"],
        },
    },
    {
        "name": "close_app",
        "description": "Stop a running process by name or PID (uses taskkill /F). RISKY — requires user confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Process name (e.g. 'notepad.exe') or PID."},
            },
            "required": ["target"],
        },
    },
    {
        "name": "mkdir",
        "description": "Create a directory (and parents). Allowed anywhere on the computer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative folder path."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_file",
        "description": "Create a new file with optional content. Fails if it already exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path."},
                "content": {"type": "string", "description": "Initial file content.", "default": ""},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write (or append) content to a file. RISKY — requires user confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path."},
                "content": {"type": "string", "description": "Text to write."},
                "append": {"type": "boolean", "description": "If true, append instead of overwrite.", "default": False},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a text file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and subdirectories in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path. Defaults to current directory.", "default": "."},
            },
            "required": [],
        },
    },
    {
        "name": "delete",
        "description": "Delete a file or folder (recursively). RISKY — requires user confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to file or folder to delete."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command (PowerShell) and return the output. RISKY — requires user confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute."},
            },
            "required": ["command"],
        },
    },
]

# Tools that need yes/no from the user before execution.
RISKY_TOOLS = {"close_app", "write_file", "delete", "run_command"}


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

def execute_tool(name: str, args: dict) -> str:
    executor = _EXECUTORS.get(name)
    if executor is None:
        return f"Unknown tool: {name}"
    return executor(args)


def _exec_open_app(args: dict) -> str:
    target = args.get("target", "").strip()
    if not target:
        return "No target provided."
    target_path = Path(target)
    try:
        if target_path.exists():
            os.startfile(str(target_path))
            return f"Opened: {target_path}"
        try:
            subprocess.Popen([target], shell=False)
        except OSError:
            subprocess.Popen(target, shell=True)
    except Exception as exc:
        return f"Failed to open app: {exc}"
    return f"Started: {target}"


def _exec_close_app(args: dict) -> str:
    target = args.get("target", "").strip()
    if not target:
        return "No target provided."
    try:
        flag = "/PID" if target.isdigit() else "/IM"
        result = subprocess.run(
            ["taskkill", flag, target, "/F"],
            capture_output=True, text=True, check=False,
        )
    except Exception as exc:
        return f"Failed to close app: {exc}"
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        return f"taskkill failed: {details or 'unknown error'}"
    return (result.stdout or "Process terminated.").strip()


def _exec_mkdir(args: dict) -> str:
    raw = args.get("path", "").strip()
    if not raw:
        return "No path provided."
    try:
        folder = Path(raw).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return f"Failed: {exc}"
    return f"Folder ready: {folder}"


def _exec_create_file(args: dict) -> str:
    raw = args.get("path", "").strip()
    if not raw:
        return "No path provided."
    content = args.get("content", "")
    try:
        fp = Path(raw).expanduser()
        fp.parent.mkdir(parents=True, exist_ok=True)
        if fp.exists():
            return f"File already exists: {fp}"
        fp.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Failed: {exc}"
    return f"Created: {fp}"


def _exec_write_file(args: dict) -> str:
    raw = args.get("path", "").strip()
    if not raw:
        return "No path provided."
    content = args.get("content", "")
    append = bool(args.get("append", False))
    try:
        fp = Path(raw).expanduser()
        fp.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with fp.open(mode, encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        return f"Failed: {exc}"
    verb = "Appended to" if append else "Wrote"
    return f"{verb}: {fp}"


def _exec_read_file(args: dict) -> str:
    raw = args.get("path", "").strip()
    if not raw:
        return "No path provided."
    try:
        fp = Path(raw).expanduser()
        if not fp.exists():
            return f"File not found: {fp}"
        if not fp.is_file():
            return f"Not a file: {fp}"
        text = fp.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Failed: {exc}"
    if len(text) > 4000:
        return text[:4000] + "\n... [truncated]"
    return text if text else "[empty file]"


def _exec_list_dir(args: dict) -> str:
    raw = args.get("path", ".").strip() or "."
    try:
        folder = Path(raw).expanduser()
        if not folder.exists():
            return f"Not found: {folder}"
        if not folder.is_dir():
            return f"Not a directory: {folder}"
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        if not entries:
            return f"{folder}: [empty]"
        lines = []
        for e in entries[:200]:
            lines.append(f"- {e.name}{'/' if e.is_dir() else ''}")
        if len(entries) > 200:
            lines.append("... [truncated]")
        return "\n".join(lines)
    except Exception as exc:
        return f"Failed: {exc}"


def _exec_delete(args: dict) -> str:
    raw = args.get("path", "").strip()
    if not raw:
        return "No path provided."
    try:
        target = Path(raw).expanduser()
        if not target.exists():
            return f"Not found: {target}"
        if target.is_dir():
            import shutil
            shutil.rmtree(target)
        else:
            target.unlink()
    except Exception as exc:
        return f"Failed: {exc}"
    return f"Deleted: {target}"


def _exec_run_command(args: dict) -> str:
    cmd = args.get("command", "").strip()
    if not cmd:
        return "No command provided."
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return "Command timed out (30s limit)."
    except Exception as exc:
        return f"Failed: {exc}"
    if not output:
        return "[no output]"
    if len(output) > 4000:
        return output[:4000] + "\n... [truncated]"
    return output


_EXECUTORS = {
    "open_app": _exec_open_app,
    "close_app": _exec_close_app,
    "mkdir": _exec_mkdir,
    "create_file": _exec_create_file,
    "write_file": _exec_write_file,
    "read_file": _exec_read_file,
    "list_dir": _exec_list_dir,
    "delete": _exec_delete,
    "run_command": _exec_run_command,
}
