"""Deterministic severity ranking + dedupe of tool findings."""

from __future__ import annotations

_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Map tool-native severities into our scale.
_BANDIT_MAP = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
_PIP_MAP = {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium",
            "MEDIUM": "medium", "LOW": "low"}
_LINK_KIND_MAP = {"timeout": "medium", "server_error": "medium",
                  "not_found": "low", "redirect": "info", "broken": "low"}


def _bandit_sev(f):
    sev = _BANDIT_MAP.get(str(f.get("severity", "")).upper(), "low")
    conf = str(f.get("confidence", "")).upper()
    # High severity + low confidence gets downgraded one notch.
    if sev == "high" and conf == "LOW":
        return "medium"
    return sev


def severity_of(f: dict) -> str:
    tool = f.get("tool", "")
    if tool == "bandit":
        return _bandit_sev(f)
    if tool in ("pip-audit", "npm-audit"):
        return _PIP_MAP.get(str(f.get("severity", "")).upper(), "medium")
    if tool == "link-crawler":
        return _LINK_KIND_MAP.get(f.get("kind", "broken"), "low")
    if tool in ("tests", "test_runner"):
        return "medium" if (f.get("status") == "failed"
                            or f.get("kind") == "failures") else "info"
    return str(f.get("severity", "info")).lower()


def _key(f: dict) -> tuple:
    """Identity key for dedupe."""
    return (
        f.get("tool", ""),
        f.get("file") or f.get("filename") or f.get("url")
        or f.get("package") or f.get("test") or "",
        f.get("line") or f.get("line_number") or "",
        f.get("check_id") or f.get("name") or f.get("advisory") or "",
    )


def rank(findings: list) -> list:
    """Dedupe, attach severity, sort Critical→Info. Returns ranked copies."""
    seen, out = set(), []
    for f in findings:
        k = _key(f)
        if k in seen:
            continue
        seen.add(k)
        g = dict(f)
        g["severity"] = severity_of(g)
        out.append(g)
    out.sort(key=lambda f: (_ORDER.get(f["severity"], 9),
                            str(f.get("file") or f.get("filename")
                                or f.get("url") or "")))
    return out


def counts(ranked: list) -> dict:
    c = {k: 0 for k in _ORDER}
    for f in ranked:
        c[f["severity"]] = c.get(f["severity"], 0) + 1
    return c
