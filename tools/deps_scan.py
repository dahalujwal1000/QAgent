"""Dependency vulnerability scan — dispatches pip-audit or npm audit."""

import json
import os

from tools.base import ToolError, ToolResult, run_cmd


def _has_file(path, name):
    return os.path.exists(os.path.join(str(path), name))


def _is_python(path):
    return (_has_file(path, "requirements.txt") or
            _has_file(path, "pyproject.toml") or
            _has_file(path, "Pipfile") or
            _has_file(path, "setup.py"))


def _is_node(path):
    return _has_file(path, "package.json")


def _parse_pip(stdout):
    findings = []
    data = json.loads(stdout)
    for dep in (data.get("dependencies") or []):
        for v in (dep.get("vulns") or []):
            aliases = v.get("aliases") or [None]
            findings.append({
                "tool": "pip-audit",
                "package": dep.get("name"),
                "version": dep.get("version"),
                "fix": v.get("fix_versions"),
                "severity": "MEDIUM",
                "advisory": aliases[0],
                "plain": v.get("description") or aliases[0],
            })
    return findings


def _parse_npm(stdout):
    findings = []
    data = json.loads(stdout)
    for name, info in (data.get("vulnerabilities") or {}).items():
        for v in (info.get("via") or []):
            if not isinstance(v, dict):
                continue
            findings.append({
                "tool": "npm audit",
                "package": name,
                "version": info.get("range"),
                "fix": v.get("range"),
                "severity": info.get("severity"),
                "advisory": v.get("title") or v.get("url"),
                "plain": v.get("title") or v.get("name") or v.get("id"),
            })
    return findings


def deps_scan(path, package_manager="auto", timeout: float = 240.0):
    if package_manager == "auto":
        if _is_python(path):
            package_manager = "pip"
        elif _is_node(path):
            package_manager = "npm"
        else:
            return ToolResult(
                name="deps_scan", ok=True, success=True, returncode=0,
                findings=[], meta={"reason": "no_package_manager_detected"})
    if package_manager == "pip":
        cmd = ["pip-audit", "--format", "json"]
        parser = _parse_pip
    elif package_manager == "npm":
        cmd = ["npm", "audit", "--json"]
        parser = _parse_npm
    else:
        return ToolResult(
            name="deps_scan", ok=False, success=False, returncode=-1,
            error=f"unknown package_manager: {package_manager}")
    try:
        proc = run_cmd(cmd, cwd=str(path), timeout=timeout)
    except ToolError as exc:
        return ToolResult(
            name="deps_scan", ok=False, success=False, returncode=-1,
            error=str(exc), meta={"reason": "audit_unavailable"})
    stdout = proc.stdout or ""
    if not stdout.strip():
        return ToolResult(
            name="deps_scan", ok=True, success=True,
            returncode=proc.returncode, output=stdout,
            findings=[], meta={"issues": 0})
    try:
        findings = parser(stdout)
    except (json.JSONDecodeError, KeyError, TypeError):
        return ToolResult(
            name="deps_scan", ok=True, success=True,
            returncode=proc.returncode, output=stdout,
            error="unparseable audit output",
            findings=[], meta={"issues": 0, "parse": False})
    return ToolResult(
        name="deps_scan", ok=True, success=True,
        returncode=proc.returncode, output=stdout,
        findings=findings, meta={"issues": len(findings),
                                 # pip-audit exits 1 when vulns exist — not an error.
                                 "tool_rc": proc.returncode})