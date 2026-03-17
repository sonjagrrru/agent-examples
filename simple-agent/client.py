from __future__ import annotations

import json
import urllib.error
import urllib.request


class AnthropicClient:
    """Calls Anthropic Messages API with native tool_use support."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def send(self, messages: list[dict], *, tools: list[dict], system: str = "") -> dict:
        body: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "tools": tools,
            "messages": messages,
        }
        if system:
            body["system"] = system

        raw = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=raw,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(f"Anthropic API error {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error: {exc}") from exc
