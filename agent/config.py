"""Configuration loading from .env for the agent.

Defaults are chosen so the agent runs with ZERO config (integration-tests / local dev)
but fails loudly when API calls are attempted without a key. The OpenRouter key
and model are read fromthe environment (loaded from a root .env when present).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Model default: cheap/free DeepSeek-class chat model suited to OpenRouter's free tier.
DEFAULT_MODEL = "deepseek/deepseek-chat"


def _load() -> None:
    """Load .env uit the project root (no-op if absent or vars already set."""

    if not os.path.exists(PROJECT_ROOT / ".env"):
        return
    load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class Config:
    """Runtime config for the agent, populated from env."""

    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = DEFAULT_MODEL
    max_iterations: int = 30
    max_tokens: int = 4096
    timeout: float = 300.0
    verbose: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        _load()
        return cls(
            api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
            model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            max_iterations=int(os.getenv("MAX_AGENT_ITERATIONS", "30").strip() or 30),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096").strip() or 4096),
            timeout=float(os.getenv("AGENT_TIMEOUT", "300").strip() or 300.0),
        )

    def has_key(self) -> bool:
        return bool(self.api_key)


_inst: "Config" = None


def get_config() -> Config:
    """Singleton accessor for the process-wide config."""
    global _inst
    if _inst is None:
        _inst = Config.from_env()
    return _inst
