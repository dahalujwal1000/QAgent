"""Bandit wrapper — Python security scanner."""

import json

from tools.base import ToolError, ToolResult, run_cmd


def _parse(data):
    findings = []
    for item in (data.get("results") or []):
        findings.append({
            "tool": "bandit",
            "check_id": item.get("test_id"),
            "check_name": item.get("test_name"),
            "severity": item.get("issue_severity"),
            "confidence": item.get("issue_confidence"),
            "file": item.get("filename"),
            "line": item.get("line_number"),
            "code": item.get("code"),
            "message": item.get("issue_text"),
            "plain": item.get("issue_text"),
        })
    return findings


def bandit_scan(path: str, timeout: float = 180.0):
    cmd = ["bandit", "-f", "json", "-r", str(path), "-q"]
    try:
        proc = run_cmd(cmd, timeout=timeout)
    except ToolError as exc:
        return ToolResult(
            name="bandit_scan", ok=False, success=False, returncode=-1,
            error=str(exc), meta={"reason": "bandit_unavailable"})
    stdout = proc.stdout or ""
    if not stdout.strip():
        return ToolResult(
            name="bandit_scan", ok=True, success=True,
            returncode=proc.returncode, output=stdout,
            findings=[], meta={"issues": 0})
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return ToolResult(
            name="bandit_scan", ok=True, success=True,
            returncode=proc.returncode, output=stdout,
            error="bandit output was not JSON",
            findings=[], meta={"issues": 0, "parse": False})
    findings = _parse(data)
    return ToolResult(
        name="bandit_scan", ok=True, success=True,
        returncode=proc.returncode, output=stdout,
        findings=findings, meta={"issues": len(findings)})