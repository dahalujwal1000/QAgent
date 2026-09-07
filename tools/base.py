"""Shared subprocess runner and tool registry."""

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


class ToolError(RuntimeError):
    pass


@dataclass
class ToolResult:
    name: str
    ok: bool
    success: bool
    returncode: int
    output: str = ""
    error: str = ""
    findings: list = field(default_factory=list)
    elapsed: float = 0.0
    meta: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def _full_path(exe: str) -> bool:
    if os.path.isabs(exe):
        return True
    return shutil.which(exe) is not None


def run_cmd(
    cmd: list,
    cwd: Optional[str] = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess:
    # Windows: npm/bandit etc. are .cmd scripts — CreateProcess can't launch
    # them by bare name, so resolve to the full path via shutil.which.
    exe = shutil.which(cmd[0]) or cmd[0]
    if not _full_path(cmd[0]):
        raise ToolError(f"Executable not found: {cmd[0]}")
    cmd = [exe] + cmd[1:]
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"Command timed out: {cmd}") from exc


def parse_json_output(stdout: str) -> Optional[dict]:
    """Best-effort parse of JSON from stdout; None if unparseable."""
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None

def now_ms() -> float:
    """Current time in milliseconds (perf counter."""
    return time.perf_counter()


class ToolSpec:
    """Metadata + JSON arg schema for one callable tool, exposed to the LLM."""

    def __init__(self, name: str, description: str, parameters: dict):
        self.name = name
        self.description = description
        self.parameters = parameters


class Tool:
    """One registered tool — knows how to bind args and dispatch execution."""

    def __init__(self, spec: ToolSpec, func: Callable):
        self.spec = spec
        self.func = func

    def dispatch(self, args: dict) -> ToolResult:
        result = self.func(**args)
        if not isinstance(result, ToolResult):
            return ToolResult(
                name=self.spec.name,
                ok=True,
                success=True,
                returncode=0,
                findings=result or [],
            )
        return result


class ToolRegistry:
    """Registers tools and dispatches calls by name."""

    def __init__(self):
        self._tools = {}

    def register(self, spec: ToolSpec, func: Callable) -> ToolRegistry:

        """Register a tool and return self (for chaining."""
        if spec.name in self._tools:
            raise ToolError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = Tool(spec, func)
        return self

    def spec_for(self, name: str) ->(ToolSpec):
        return self._tools.get(name)

    def function_schemas(self) -> list:
        """The tool list sent to the LLM (OpenAI function-calling format."""

        result = []
        for tool in self._tools.values():
            params = tool.spec.parameters or {"type": "object"}
            result.append({
                "type": "function",
                "function": {
                    "name": tool.spec.name,
                    "description": tool.spec.description,
                    "parameters": params,
                },
            })
        return result

    def names(self) -> list:
        return sorted(tool.spec.name for tool in self._tools.values())

    def dispatch(self, name: str, args: dict) -> ToolResult:

        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(self.names())
            return ToolResult(
                name=name, ok=False, success=False, returncode=-1,
                error=f"Unknown tool \"{name}\". Available: {available}",
            )
        try:
            return tool.dispatch(args)
        except TypeError as exc:
            return ToolResult(
                name=name, ok=False, success=False, returncode=-1,
                error=f"Bad args for tool \"{name}\": {exc}",
            )
        except ToolError as exc:
            return ToolResult(
                name=name, ok=False, success=False, returncode=-1,
                error=str(exc),
            )
        except Exception as exc:
            return ToolResult(
                name=name, ok=False, success=False, returncode=-1,
                error=f"Tool \"{name}\" raised {type(exc).__name__}: {exc}",
            )




