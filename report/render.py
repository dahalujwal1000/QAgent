"""Rich CLI rendering of the ranked report."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from report.ranker import counts


def _safe(text) -> str:
    """ASCII-safe text for legacy Windows consoles (cp1252/charmap)."""
    return str(text).encode("ascii", "replace").decode("ascii")

_SEV_STYLE = {
    "critical": "bold white on red",
    "high": "bold red",
    "medium": "yellow",
    "low": "cyan",
    "info": "dim",
}


def _location(f: dict) -> str:
    if f.get("tool") == "link-crawler":
        return f.get("url", "")
    if f.get("tool") == "tests":
        return f.get("test", "")
    loc = f.get("file") or f.get("filename") or ""
    if f.get("line") or f.get("line_number"):
        loc += f":{f.get('line') or f.get('line_number')}"
    return loc


def _title(f: dict) -> str:
    if f.get("tool") in ("pip-audit", "npm audit"):
        fix = f.get("fix")
        fix_s = f" (fix: {fix[0] if isinstance(fix, list) and fix else fix})" if fix else ""
        return (f"{f.get('package')}=={f.get('version')} - "
                f"{f.get('advisory')}{fix_s}")
    return (f.get("issue_text") or f.get("plain") or f.get("advisory")
            or f.get("title") or f.get("name") or f.get("message")
            or "finding")


def render(ranked: list, report_text: str = "", verbose: bool = False) -> None:
    # legacy_windows=False avoids cp1252 charmap crashes on old conhost.
    console = Console(legacy_windows=False)
    console.print()
    if ranked:
        table = Table(title="Findings (ranked)", show_lines=False)
        table.add_column("Sev", style="bold", width=8)
        table.add_column("Tool", width=12)
        table.add_column("Location", max_width=44, overflow="fold")
        table.add_column("Finding", max_width=60, overflow="fold")
        for f in ranked:
            sev = _safe(f["severity"])
            table.add_row(
                Text(sev, style=_SEV_STYLE.get(f["severity"], "")),
                Text(_safe(f.get("tool", ""))),
                Text(_safe(_location(f)), overflow="fold"),
                Text(_safe(_title(f))[:160], overflow="fold"),
            )
        console.print(table)
        console.print(counts(ranked))
    else:
        console.print("[bold green]No findings.[/]")

    if report_text:
        console.print("\n[bold]Agent summary[/]\n")
        console.print(_safe(report_text))

    if verbose:
        console.print("\n[bold dim]Raw findings JSON[/]")
        import json
        console.print(_safe(json.dumps(ranked, indent=2, default=str)))
