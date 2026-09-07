# AI Security & QA Agent

Scans a codebase or website for security vulnerabilities, vulnerable
dependencies, broken links, and failing tests — then ranks everything by
severity and explains it in plain English.

**Core principle: the LLM orchestrates, it never scans.** Every check is a real
external tool run via subprocess; the LLM (via OpenRouter) decides which tools
to run, reads the raw output, dedupes false positives, and writes the report.

## What it checks

| Check | Tool (wrapped, not reinvented) |
|---|---|
| Security issues (secrets, SQLi, XSS, shell=True, weak hashing) | `bandit` |
| Vulnerable dependencies | `pip-audit` (Python) / `npm audit` (Node) |
| Broken links (404 / 5xx / timeouts / redirects) | built-in crawler (`requests`) |
| Test suite pass/fail | `pytest` (junit-xml) / `npm test` |

## Setup

```bash
pip install -r requirements.txt
pip install bandit pip-audit        # scanner CLIs
copy .env.example .env              # then add your OpenRouter key
```

`.env`:
```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=deepseek/deepseek-chat   # any OpenRouter model
```

## Usage

```bash
python cli.py path/to/repo          # local project
python cli.py https://github.com/u/r.git   # remote repo (cloned to temp)
python cli.py https://example.com   # website (link crawl)
python cli.py <target> --no-llm     # deterministic mode, no API key needed
python cli.py <target> --verbose    # show raw tool output
```

Without an API key the agent falls back to deterministic mode: runs every
relevant tool in fixed order and prints the ranked table (no plain-English
summary).

## Architecture

```
input (repo/URL) -> detect project type (agent/detect.py)
                 -> agent loop (agent/orchestrator.py)
                      LLM turn (agent/llm.py, OpenRouter function-calling)
                        -> ToolRegistry dispatch (tools/base.py, tools/registry.py)
                        -> observation fed back -> repeat
                 -> rank + dedupe (report/ranker.py)
                 -> Rich report (report/render.py)
```

- **agent/** — config (.env), project detection, LLM client, orchestrator loop, state
- **tools/** — one module per scanner; each returns structured findings
- **report/** — deterministic severity ranking + Rich CLI rendering
- **tests/** — mock-LLM end-to-end test of the agent loop (`python tests/test_mock_loop.py`)

The agent is advisory-only in v1: it never modifies your code; fix suggestions
appear in the report text.

## Limitations

- Not a pentest — it's a developer QA & hygiene scanner.
- `pip-audit` currently audits the active environment; pin exact versions in
  requirements.txt for best results.
- Link crawler is same-origin only, capped at ~100 pages by default.
