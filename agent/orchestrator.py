"""The agent loop: LLM decides → orchestrator dispatches tools → observe → repeat.

The LLM NEVER scans anything itself. Every security/QA check is a real
subprocess tool from the ToolRegistry; the LLM only chooses order, reads
results, and produces the final plain-English report.
"""

from __future__ import annotations

import json

from agent.detect import ProjectProfile
from agent.llm import LLMClient, parse_tool_args
from agent.state import AgentState
from tools.base import ToolRegistry
from tools.registry import result_summary

SYSTEM_PROMPT = """\
You are a security & QA orchestration agent. You NEVER fabricate scan results —
every finding must come from a tool call you made.

You are auditing this project:
  path: {path}
  profile: {profile}

Rules:
1. Decide which tools to run based on the profile. For a Python project run
   bandit_scan and deps_scan; for a Node project use deps_scan with npm; for a
   website URL run crawl_links; run run_tests when a test runner exists.
2. After gathering results you may run additional targeted tools if a finding
   needs confirmation, but do not repeat a tool with identical arguments.
3. When you have enough evidence, STOP calling tools and write the final
   report in plain English: a ranked list (Critical / High / Medium / Low)
   where each entry names the tool that found it, the file/URL, what the
   problem is, why it matters, and a concrete suggested fix.
"""


class Orchestrator:
    def __init__(self, registry: ToolRegistry, llm, config=None):
        self.registry = registry
        self.llm = llm  # any object with .chat(messages, tools) -> dict
        from agent.config import get_config
        self.config = config or get_config()

    def run(self, profile: ProjectProfile, verbose: bool = False) -> AgentState:
        state = AgentState(profile=profile)
        messages = [
            {"role": "system",
             "content": SYSTEM_PROMPT.format(
                 path=profile.path, profile=profile.summary())},
            {"role": "user",
             "content": "Audit this project. Run the relevant tools, then "
                        "produce the final ranked report."},
        ]
        schemas = self.registry.function_schemas()

        while state.iterations < self.config.max_iterations:
            try:
                assistant = self.llm.chat(messages, tools=schemas)
            except Exception as exc:
                state.errors.append(f"LLM: {exc}")
                break
            messages.append(assistant)
            state.iterations += 1

            tool_calls = assistant.get("tool_calls")
            if not tool_calls:
                state.final_report = assistant.get("content", "")
                break  # final answer

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = parse_tool_args(fn.get("arguments", ""))
                if verbose:
                    print(f"  -> tool {name}({args})")
                result = self.registry.dispatch(name, args)
                state.record(result, args)
                # Observation fed back to the LLM: short summary + findings.
                observation = {
                    "summary": result_summary(result),
                    "findings": result.findings[:50],
                    "error": result.error or None,
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(observation)[:12000],
                })
        else:
            state.errors.append("Max iterations reached without final report.")

        return state
