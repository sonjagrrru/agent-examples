from __future__ import annotations

import json
import os

from client import AnthropicClient
from tools import TOOLS, RISKY_TOOLS, execute_tool, _EXECUTORS
from ui import UI


# ---------------------------------------------------------------------------
# Agent: orchestrates the conversation loop with the model
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful single-agent assistant running on the user's Windows computer. "
    "You have dedicated tools for common operations (files, folders, apps) and a run_command tool "
    "that can execute any PowerShell command for everything else (opening websites, system info, "
    "installing software, etc.). "
    "Use dedicated tools when they fit; use run_command for anything else. "
    "For general chat, just respond with text. "
    "Be concise.\n\n"
    f"Environment info:\n"
    f"- Home directory: {os.path.expanduser('~')}\n"
    f"- Desktop: {os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')}\n"
    f"- Current working directory: {os.getcwd()}\n"
    "Always use absolute paths when the user refers to locations like Desktop, Documents, etc."
)


class SimpleAgent:
    """Single-agent that uses Anthropic native tool_use for decisions."""

    def __init__(self) -> None:
        self._client = self._build_client()
        self._messages: list[dict] = []
        self._pending_confirmation: dict | None = None

    @staticmethod
    def _build_client() -> AnthropicClient | None:
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return None
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        return AnthropicClient(api_key=key, model=model)

    def handle(self, user_input: str) -> str:
        text = user_input.strip()
        if not text:
            UI.agent_say("Type something, or 'exit' to quit.")
            return ""

        if text.lower() in {"exit", "quit"}:
            self._pending_confirmation = None
            return "Goodbye!"

        # --- Confirmation flow for risky tools ---
        if self._pending_confirmation is not None:
            return self._handle_confirmation(text)

        # --- No API key? Fall back to direct commands ---
        if self._client is None:
            result = self._fallback(text)
            UI.agent_say(result)
            return result

        # --- Normal LLM flow with native tool_use ---
        self._messages.append({"role": "user", "content": text})
        return self._run_agent_loop()

    def _run_agent_loop(self) -> str:
        """Send to model, execute tools, loop until model produces final text."""
        while True:
            try:
                response = self._client.send(
                    self._messages, tools=TOOLS, system=SYSTEM_PROMPT,
                )
            except RuntimeError as exc:
                UI.error(str(exc))
                return f"[API error] {exc}"

            stop_reason = response.get("stop_reason")
            content_blocks = response.get("content", [])

            # Store assistant message exactly as the API returned it.
            self._messages.append({"role": "assistant", "content": content_blocks})

            # If model stopped without tool call, extract text and return.
            if stop_reason == "end_turn" or stop_reason != "tool_use":
                texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                final = "\n".join(t for t in texts if t).strip()
                UI.agent_say(final if final else "[no response]")
                return final if final else "[no response]"

            # Model wants to call tool(s).
            tool_results = []
            for block in content_blocks:
                if block.get("type") != "tool_use":
                    continue

                tool_name = block["name"]
                tool_input = block.get("input", {})
                tool_use_id = block["id"]

                # Risky tool? Ask user for confirmation first.
                if tool_name in RISKY_TOOLS:
                    self._pending_confirmation = {
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_use_id": tool_use_id,
                    }
                    UI.confirm_prompt(tool_name, tool_input)
                    return ""

                # Safe tool — execute immediately.
                UI.tool_call(tool_name, tool_input)
                result = execute_tool(tool_name, tool_input)
                UI.tool_result(result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result,
                })

            # Send tool results back to model so it can continue.
            self._messages.append({"role": "user", "content": tool_results})

    def _handle_confirmation(self, text: str) -> str:
        answer = text.lower().strip()
        pending = self._pending_confirmation

        if answer in {"yes", "y", "confirm"}:
            self._pending_confirmation = None
            UI.confirmed()
            UI.tool_call(pending["tool_name"], pending["tool_input"])
            result = execute_tool(pending["tool_name"], pending["tool_input"])
            UI.tool_result(result)

            # Feed tool result back into conversation.
            self._messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": pending["tool_use_id"],
                    "content": result,
                }],
            })
            return self._run_agent_loop()

        if answer in {"no", "n", "cancel"}:
            self._pending_confirmation = None
            UI.canceled()
            self._messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": pending["tool_use_id"],
                    "content": "User denied this action.",
                    "is_error": True,
                }],
            })
            return self._run_agent_loop()

        UI.agent_say("Type 'yes' to confirm or 'no' to cancel.")
        return ""

    def _fallback(self, text: str) -> str:
        """When no API key: parse direct commands like 'list_dir .'."""
        if text.lower() == "help":
            tools_list = "\n".join(f"  - {t['name']}: {t['description']}" for t in TOOLS)
            return (
                "Simple Agent (no API key — direct command mode)\n"
                f"Available tools:\n{tools_list}\n"
                "Usage: <tool_name> <json_args>  |  exit"
            )

        command, _, rest = text.partition(" ")
        command = command.lower().strip()
        if command in _EXECUTORS:
            try:
                args = json.loads(rest) if rest.strip() else {}
            except json.JSONDecodeError:
                schema = next((t for t in TOOLS if t["name"] == command), None)
                if schema:
                    required = schema["input_schema"].get("required", [])
                    if required:
                        args = {required[0]: rest.strip()}
                    else:
                        props = list(schema["input_schema"].get("properties", {}).keys())
                        args = {props[0]: rest.strip()} if props else {}
                else:
                    args = {}
            return execute_tool(command, args)

        return "No API key set. Use 'help' for direct commands, or set ANTHROPIC_API_KEY."
