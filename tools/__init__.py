"""Tool wrappers — each wraps a real external CLI/checker.

Exports the shared base plumbing for tool modules.
"""

from tools.base import (
    Tool,
    ToolError,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    parse_json_output,
    run_cmd,
)

__all__ = [
    "Tool",
    "ToolError",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "parse_json_output",
    "run_cmd",
]