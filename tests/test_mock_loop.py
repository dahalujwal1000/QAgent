"""Mock-LLM test: proves the orchestrator loop end-to-end with zero API calls."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.detect import detect_project
from agent.orchestrator import Orchestrator
from tools.registry import build_default_registry

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "vuln_app")


class ScriptedLLM:
    """Returns canned tool calls, then a final report."""

    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None):
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, dict):  # final answer
                return {"role": "assistant", "content": step["content"]}
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": f"call_{len(self.script)}",
                    "type": "function",
                    "function": {"name": step[0],
                                 "arguments": json.dumps(step[1])},
                }],
            }
        return {"role": "assistant", "content": "done"}


def main():
    profile = detect_project(FIXTURE)
    registry = build_default_registry()
    llm = ScriptedLLM([
        ("bandit_scan", {"path": FIXTURE}),
        ("run_tests", {"path": FIXTURE}),
        {"content": "FINAL REPORT: issues found."},
    ])
    state = Orchestrator(registry, llm).run(profile)

    assert state.iterations == 3, state.iterations
    assert state.tool_log[0]["name"] == "bandit_scan"
    assert any(f["tool"] == "bandit" for f in state.findings), "bandit findings missing"
    assert state.final_report == "FINAL REPORT: issues found."

    # Unknown tool returns a graceful ToolResult, not an exception.
    bad = registry.dispatch("nope", {})
    assert not bad.ok and "Unknown tool" in bad.error

    from report.ranker import rank, counts
    ranked = rank(state.findings)
    c = counts(ranked)
    print("state:", state.summary())
    print("counts:", c)
    print("sample finding:", {k: ranked[0].get(k) for k in
                              ("tool", "severity", "file", "line")})
    print("MOCK LOOP TEST PASSED")


if __name__ == "__main__":
    main()


def test_mock_loop():
    """Pytest entry point so `pytest` runs the full mock-LLM loop."""
    main()
