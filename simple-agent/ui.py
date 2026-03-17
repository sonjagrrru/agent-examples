from __future__ import annotations

import json
import os


class UI:
    """Simple colored terminal output for Windows/ANSI terminals."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"

    @staticmethod
    def enable_ansi() -> None:
        """Enable ANSI escape codes on Windows 10+."""
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    @classmethod
    def banner(cls) -> None:
        print(f"\n{cls.BOLD}{cls.CYAN}{'=' * 50}")
        print(f"   Simple Agent")
        print(f"{'=' * 50}{cls.RESET}")

    @classmethod
    def status(cls, text: str) -> None:
        print(f"{cls.DIM}{text}{cls.RESET}")

    @classmethod
    def user_prompt(cls) -> str:
        return input(f"\n{cls.BOLD}{cls.GREEN}You > {cls.RESET}")

    @classmethod
    def agent_say(cls, text: str) -> None:
        print(f"\n{cls.BOLD}{cls.CYAN}Agent > {cls.RESET}{text}")

    @classmethod
    def tool_call(cls, name: str, args: dict) -> None:
        args_str = json.dumps(args, ensure_ascii=False)
        print(f"  {cls.DIM}{cls.MAGENTA}[tool] {name}({args_str}){cls.RESET}")

    @classmethod
    def tool_result(cls, result: str) -> None:
        short = result[:200] + "..." if len(result) > 200 else result
        print(f"  {cls.DIM}{cls.MAGENTA}[result] {short}{cls.RESET}")

    @classmethod
    def confirm_prompt(cls, tool_name: str, args: dict) -> None:
        args_str = json.dumps(args, ensure_ascii=False)
        print(f"\n{cls.BOLD}{cls.YELLOW}[!] Risky action: {tool_name}({args_str})")
        print(f"    Type 'yes' to confirm or 'no' to cancel.{cls.RESET}")

    @classmethod
    def confirmed(cls) -> None:
        print(f"  {cls.GREEN}[confirmed]{cls.RESET}")

    @classmethod
    def canceled(cls) -> None:
        print(f"  {cls.RED}[canceled]{cls.RESET}")

    @classmethod
    def error(cls, text: str) -> None:
        print(f"\n{cls.RED}[Error] {text}{cls.RESET}")
