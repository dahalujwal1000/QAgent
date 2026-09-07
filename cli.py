"""CLI entry point: python cli.py <repo-path | repo-url | website-url>

LLM orchestrates; fallback deterministic mode runs when no API key is set.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from agent.config import get_config
from agent.detect import ProjectProfile, detect_project
from agent.orchestrator import Orchestrator
from report.ranker import rank
from report.render import render
from tools.base import ToolRegistry
from tools.registry import build_default_registry


def resolve_target(target: str) -> tuple[str, str | None]:
    """Return (local_path, temp_dir_or_None). Clones remote git/website URLs."""
    if Path(target).exists():
        return target, None

    if target.startswith(("http://", "https://")):
        if target.lower().endswith(".git") or "github.com" in target:
            import git
            tmp = tempfile.mkdtemp(prefix="ai_sec_agent_")
            print(f"Cloning {target} -> {tmp}")
            git.Repo.clone_from(target, tmp)
            return tmp, tmp
        # Website URL: point profile at a pseudo-path; crawl_links uses the URL.
        return target, None

    sys.exit(f"error: target not found and not a URL: {target}")


def run_deterministic(profile: ProjectProfile, registry: ToolRegistry,
                      url: str | None) -> list:
    """No-API-key fallback: run every relevant tool in fixed order."""
    findings = []
    if profile.is_website and url:
        r = registry.dispatch("crawl_links", {"start_url": url})
        findings += r.findings
    if profile.is_python:
        r = registry.dispatch("bandit_scan", {"path": profile.path})
        findings += r.findings
    if profile.package_manager in ("pip", "npm"):
        r = registry.dispatch("deps_scan", {"path": profile.path})
        findings += r.findings
    if profile.test_runner != "none":
        r = registry.dispatch("run_tests", {"path": profile.path})
        findings += r.findings
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Security & QA Agent — scans a repo/website for "
                    "vulnerabilities, vulnerable deps, broken links, and "
                    "failing tests, then explains findings in plain English.")
    parser.add_argument("target", help="Local repo path, git URL, or website URL")
    parser.add_argument("--verbose", action="store_true", help="Show raw output")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM; run tools deterministically")
    args = parser.parse_args()

    path, tmp = resolve_target(args.target)
    url = args.target if args.target.startswith(("http://", "https://")) else None

    from rich.console import Console
    console = Console()
    if not Path(path).exists():
        profile = ProjectProfile(path=path, is_website=bool(url))
    else:
        profile = detect_project(path)
    if url and not Path(path).exists():
        profile.is_website = True
    console.print(f"[bold]Profile:[/] {profile.summary()}")

    registry = build_default_registry()
    config = get_config()

    report_text = ""
    if args.no_llm or not config.has_key():
        if not config.has_key():
            console.print("[yellow]No OPENROUTER_API_KEY set — deterministic "
                          "mode (raw tool findings, no plain-English report).[/]")
        findings = run_deterministic(profile, registry, url)
    else:
        from agent.llm import LLMClient
        try:
            llm = LLMClient(config)
        except Exception as exc:
            console.print(f"[red]{exc}[/]")
            findings = run_deterministic(profile, registry, url)
        else:
            console.print(f"[bold]Agent ([/]{config.model}[bold]) "
                          "orchestrating tools...[/]")
            orch = Orchestrator(registry, llm, config)
            state = orch.run(profile, verbose=args.verbose)
            console.print(f"[dim]state: {state.summary()}[/]")
            for e in state.errors:
                console.print(f"[red]error:[/] {e}")
            findings = state.findings
            report_text = getattr(state, "final_report", "")

    render(rank(findings), report_text, verbose=args.verbose)

    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
