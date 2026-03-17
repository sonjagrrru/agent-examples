"""GUI frontend for Simple Agent — Tkinter chat window."""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

# Ensure imports work when running this file directly.
sys.path.insert(0, os.path.dirname(__file__))

from agent import SimpleAgent  # noqa: E402
from tools import TOOLS, RISKY_TOOLS  # noqa: E402
import ui as _ui_mod  # noqa: E402

# ---------------------------------------------------------------------------
# Color palette (Catppuccin Mocha-ish)
# ---------------------------------------------------------------------------
BG = "#1e1e2e"
BG_INPUT = "#2a2a3c"
FG = "#cdd6f4"
ACCENT = "#89b4fa"  # blue  — user
GREEN = "#a6e3a1"  # green — agent
ORANGE = "#fab387"  # orange — tool
RED = "#f38ba8"  # red   — error
YELLOW = "#f9e2af"  # yellow — confirm
GRAY = "#6c7086"  # gray  — system


class ChatGUI:
    """Tkinter GUI that wraps SimpleAgent."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Simple Agent")
        self.root.geometry("780x560")
        self.root.configure(bg=BG)
        self.root.minsize(400, 300)

        mono = tkfont.Font(family="Consolas", size=11)

        # --- Chat area ---
        chat_frame = tk.Frame(self.root, bg=BG)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        scrollbar = tk.Scrollbar(chat_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat = tk.Text(
            chat_frame, wrap=tk.WORD, bg=BG, fg=FG, font=mono,
            insertbackground=FG, relief=tk.FLAT, padx=12, pady=8,
            state=tk.DISABLED, cursor="arrow",
            yscrollcommand=scrollbar.set,
        )
        self.chat.pack(fill=tk.BOTH, expand=True)
        scrollbar.configure(command=self.chat.yview)

        # Color tags
        self.chat.tag_configure("user", foreground=ACCENT)
        self.chat.tag_configure("agent", foreground=GREEN)
        self.chat.tag_configure("tool", foreground=ORANGE)
        self.chat.tag_configure("error", foreground=RED)
        self.chat.tag_configure("confirm", foreground=YELLOW)
        self.chat.tag_configure("system", foreground=GRAY)

        # --- Input bar ---
        input_frame = tk.Frame(self.root, bg=BG)
        input_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.entry = tk.Entry(
            input_frame, font=mono, bg=BG_INPUT, fg=FG,
            insertbackground=FG, relief=tk.FLAT,
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))
        self.entry.bind("<Return>", self._on_send)

        self.send_btn = tk.Button(
            input_frame, text="Send", font=mono,
            bg=ACCENT, fg=BG, activebackground="#b4d0fb",
            relief=tk.FLAT, padx=14, pady=4,
            command=self._on_send,
        )
        self.send_btn.pack(side=tk.RIGHT)

        # --- Agent ---
        self.agent = SimpleAgent()
        self._patch_ui()

        # Thread-safe message queue
        self._queue: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self.root.after(50, self._poll)

        # Welcome text
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        key_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
        status = f"Model: {model}" if key_set else "No API key — fallback mode"
        tools_safe = [t["name"] for t in TOOLS if t["name"] not in RISKY_TOOLS]
        tools_risky = [t["name"] for t in TOOLS if t["name"] in RISKY_TOOLS]
        self._append(f"Simple Agent  |  {status}\n", "system")
        self._append(f"Safe tools: {', '.join(tools_safe)}\n", "system")
        self._append(f"Risky tools (need yes/no): {', '.join(tools_risky)}\n\n", "confirm")

        self.entry.focus_set()

    # ------------------------------------------------------------------
    # Patch UI class so agent output goes to the chat window
    # ------------------------------------------------------------------
    def _patch_ui(self) -> None:
        gui = self

        @staticmethod
        def agent_say(text):
            gui._enqueue("agent", f"Agent > {text}\n\n")

        @staticmethod
        def tool_call(name, args):
            gui._enqueue("tool", f"  [tool] {name}({args})\n")

        @staticmethod
        def tool_result(result):
            gui._enqueue("tool", f"  [result] {result}\n")

        @staticmethod
        def confirm_prompt(name, args):
            gui._enqueue("confirm", f"  ⚠ {name}({args})\n  Type yes or no:\n")

        @staticmethod
        def confirmed():
            gui._enqueue("system", "  ✓ Confirmed\n")

        @staticmethod
        def canceled():
            gui._enqueue("system", "  ✗ Canceled\n")

        @staticmethod
        def error(text):
            gui._enqueue("error", f"  [Error] {text}\n")

        _ui_mod.UI.agent_say = agent_say
        _ui_mod.UI.tool_call = tool_call
        _ui_mod.UI.tool_result = tool_result
        _ui_mod.UI.confirm_prompt = confirm_prompt
        _ui_mod.UI.confirmed = confirmed
        _ui_mod.UI.canceled = canceled
        _ui_mod.UI.error = error

    # ------------------------------------------------------------------
    # Thread-safe queue → GUI updates
    # ------------------------------------------------------------------
    def _enqueue(self, tag: str, text: str) -> None:
        with self._lock:
            self._queue.append((tag, text))

    def _poll(self) -> None:
        with self._lock:
            msgs, self._queue = self._queue[:], []
        for tag, text in msgs:
            self._append(text, tag)
        self.root.after(50, self._poll)

    def _append(self, text: str, tag: str = "system") -> None:
        self.chat.configure(state=tk.NORMAL)
        self.chat.insert(tk.END, text, tag)
        self.chat.see(tk.END)
        self.chat.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Send / receive
    # ------------------------------------------------------------------
    def _on_send(self, _event=None) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        self._append(f"You > {text}\n", "user")

        if text.lower() in {"exit", "quit"}:
            self.root.after(300, self.root.destroy)
            return

        # Disable input while model is thinking
        self.entry.configure(state=tk.DISABLED)
        self.send_btn.configure(state=tk.DISABLED)

        thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        thread.start()

    def _run(self, text: str) -> None:
        try:
            self.agent.handle(text)
        except Exception as exc:
            self._enqueue("error", f"[Error] {exc}\n")
        self.root.after(0, self._unlock)

    def _unlock(self) -> None:
        self.entry.configure(state=tk.NORMAL)
        self.send_btn.configure(state=tk.NORMAL)
        self.entry.focus_set()

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    ChatGUI().run()
