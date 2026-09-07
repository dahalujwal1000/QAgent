"""Agent state — accumulates findings, tool log, and iteration count."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.detect import ProjectProfile
from tools.base import ToolResult


@dataclass
class AgentState:
    profile: ProjectProfile
    findings: list = field(default_factory=list)
    tool_log: list = field(default_factory=list)  # {name, args, ok, n_findings}
    iterations: int = 0
    errors: list = field(default_factory=list)

    def record(self, result: ToolResult, args: dict) -> None:
        self.tool_log.append(
            {"name": result.name, "args": args, "ok": result.ok,
             "n_findings": len(result.findings)}
        )
        if result.findings:
            self.findings.extend(result.findings)
        if not result.ok and result.error:
            self.errors.append(f"{result.name}: {result.error}")

    def summary(self) -> str:
        return (
            f"tools_run={self.iterations} findings={len(self.findings)} "
            f"errors={len(self.errors)}"
        )
