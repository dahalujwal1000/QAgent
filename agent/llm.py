"""OpenRouter LLM client (OpenAI-compatible function calling)."""

from __future__ import annotations

import json

from agent.config import Config, get_config


class LLMError(RuntimeError):
    pass


class LLMClient:
    """Thin wrapper over OpenRouter using the OpenAI SDK.

    Exposes a single `chat()` method returning the assistant message dict
    (OpenAI chat-completions format), so the orchestrator stays provider-neutral
    and can be swapped for a mock in tests.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        if not self.config.has_key():
            raise LLMError(
                "OPENROUTER_API_KEY is not set. Add it to your .env file "
                "(see .env.example)."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("The `openai` package is required: pip install openai") from exc

        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    def chat(self, messages: list, tools: list | None = None) -> dict:
        """Send a chat completion; returns the assistant message as a dict.

        The message may contain `content` (final answer) and/or `tool_calls`.
        """
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"OpenRouter request failed: {exc}") from exc

        choice = response.choices[0]
        message = choice.message
        out = {
            "role": "assistant",
            "content": message.content or "",
        }
        # Serialize tool_calls into plain dicts so state stays JSON-able.
        raw_calls = getattr(message, "tool_calls", None) or []
        if raw_calls:
            out["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in raw_calls
            ]
        if getattr(response, "usage", None):
            out["_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        return out


def parse_tool_args(arguments: str) -> dict:
    """Parse a tool-call arguments JSON string, tolerating empty/malformed."""
    if not arguments or not arguments.strip():
        return {}
    try:
        args = json.loads(arguments)
        return args if isinstance(args, dict) else {}
    except json.JSONDecodeError:
        return {}
