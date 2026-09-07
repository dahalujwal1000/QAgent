"""Build the default ToolRegistry wiring all available tool wrappers."""

from tools.base import ToolRegistry, ToolSpec, ToolResult
from tools.bandit_scan import bandit_scan
from tools.deps_scan import deps_scan
from tools.link_crawler import crawl_links
from tools.test_runner import run_tests


def build_default_registry() -> ToolRegistry:
    """Create a ToolRegistry with every implemented tool registered."""
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="bandit_scan",
            description=(
                "Scan a Python project directory (or a single .py file) for "
                "security issues (hardcoded secrets, SQL injection, XSS, "
                "unsafe eval/deserialization) using the `bandit` tool. "
                "Use only when the target is a Python project."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory or file to scan.",
                    },
                },
                "required": ["path"],
            },
        ),
        bandit_scan,
    )

    registry.register(
        ToolSpec(
            name="deps_scan",
            description=(
                "Scan installed/declared dependencies for known vulnerable "
                "or outdated packages using pip-audit (Python) or npm audit "
                "(Node). Auto-detects the package manager unless overridden."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project root directory.",
                    },
                    "package_manager": {
                        "type": "string",
                        "enum": ["auto", "pip", "npm"],
                        "description": "Override package manager (default auto).",
                    },
                },
                "required": ["path"],
            },
        ),
        deps_scan,
    )

    registry.register(
        ToolSpec(
            name="crawl_links",
            description=(
                "Crawl a website starting from a URL (same-origin), checking "
                "each link for 404/5xx/timeout/redirect problems. Returns a "
                "list of checked URLs; entries where kind == 'broken' are "
                "problems. Use when the target is a website URL."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "start_url": {
                        "type": "string",
                        "description": "Base URL to begin crawling.",
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Max pages to visit (default 100).",
                    },
                },
                "required": ["start_url"],
            },
        ),
        crawl_links,
    )

    registry.register(
        ToolSpec(
            name="run_tests",
            description=(
                "Run the project's test suite (pytest for Python, npm test "
                "for Node) and report pass/fail counts."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project root directory.",
                    },
                },
                "required": ["path"],
            },
        ),
        run_tests,
    )

    return registry


def result_summary(result: ToolResult) -> str:
    """Friendly one-line summary of a tool result (for the LLM observation)."""
    if not result.ok:
        return f"[{result.name}] FAILED: {result.error}"
    if result.findings:
        kinds = {f.get("tool", result.name) for f in result.findings}
        return (
            f"[{result.name}] ran ok; {len(result.findings)} finding(s) from "
            f"{sorted(kinds)}."
        )
    extra = result.meta.get("reason", "")
    if extra:
        return f"[{result.name}] ran ok; no findings ({extra})."
    return f"[{result.name}] ran ok; no findings."