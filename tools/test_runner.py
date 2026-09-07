"""Test-runner wrapper — runs pytest or npm test, parses pass/fail summary."""

import json
import os
import re
import tempfile

from tools.base import ToolError, ToolResult, run_cmd


def _is_python(path):
    return (os.path.exists(os.path.join(str(path), "requirements.txt")) or
            os.path.exists(os.path.join(str(path), "pyproject.toml")) or
            os.path.exists(os.path.join(str(path), "setup.py")))


def _is_node(path):
    return os.path.exists(os.path.join(str(path), "package.json"))


def _extract_pytest_report(stdout):
    # pytest --json-report emits a JSON report to stdout last; we parse the last
    # JSON object that looks like a report summary.
    count = {"passed": 0, "failed": 0, "error": 0, "total": 0, "skipped": 0}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or "summary" not in obj:
            continue
        s = obj.get("summary", {})
        count.update({k: s.get(k, count[k]) for k in count})
def _extract_pytest_report(stdout):
    """Fallback parser for plain `pytest -q` text output."""
    count = {"passed": 0, "failed": 0, "error": 0, "total": 0, "skipped": 0}
    # JSON-report style lines, if the plugin is present.
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "summary" in obj:
            s = obj.get("summary", {})
            count.update({k: s.get(k, count[k]) for k in count})
    if count["total"] == 0:
        # "1 failed, 2 passed, 1 skipped in 0.1s" (timing suffix optional).
        m = re.search(
            r"(?:(\d+) failed)?[, ]*(?:(\d+) passed)?[, ]*"
            r"(?:(\d+) skipped)?[, ]*(?:(\d+) error)?", stdout)
        if m and any(m.groups()):
            count["failed"] = int(m.group(1) or 0)
            count["passed"] = int(m.group(2) or 0)
            count["skipped"] = int(m.group(3) or 0)
            count["error"] = int(m.group(4) or 0)
            count["total"] = sum(count[k] for k in
                                 ("failed", "passed", "skipped", "error"))
    return count


def _parse_junit(xml_path):
    """Parse pytest's native --junit-xml output (no plugin needed)."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(xml_path)
    suite = tree.getroot().find(".//testsuite")
    if suite is None:
        suite = tree.getroot()  # root may be <testsuites> containing attrs
    get = lambda a: int(float(suite.get(a, 0)))  # noqa: E731
    return {
        "total": get("tests"),
        "failed": get("failures"),
        "error": get("errors"),
        "skipped": get("skipped"),
        "passed": get("tests") - get("failures") - get("errors") - get("skipped"),
    }


def run_tests(path, timeout: float = 600.0):
    junit = None
    if _is_python(path):
        junit = os.path.join(tempfile.gettempdir(), "ai_sec_agent_junit.xml")
        cmd = ["python", "-m", "pytest", "-q", "--tb=short",
               "--junit-xml", junit, os.path.abspath(str(path))]
    elif _is_node(path):
        cmd = ["npm", "test", "--prefix", str(path)]
    else:
        return ToolResult(name="test_runner", ok=True, success=True,
                           returncode=0, findings=[],
                           meta={"reason": "no_test_runner_detected"})
    try:
        proc = run_cmd(cmd, cwd=str(path), timeout=timeout)
    except ToolError as exc:
        return ToolResult(name="test_runner", ok=False, success=False,
                           returncode=-1, error=str(exc),
                           meta={"reason": "runner_unavailable"})
    stdout = proc.stdout or ""
    passed = failed = 0
    if not _is_node(path):
        counts = None
        if junit and os.path.exists(junit):
            try:
                counts = _parse_junit(junit)
            except Exception:
                counts = None
        if counts is None:
            counts = _extract_pytest_report(stdout)
        passed, failed = counts["passed"], counts["failed"] + counts["error"]
    else:
        # Simple best-effort pass/fail marker for npm test text output.
        failed = stdout.lower().count("failed") - stdout.lower().count("failed 0")
        failed = max(0, failed)
    findings = []
    if failed:
        findings.append({
            "tool": "test_runner",
            "kind": "failures",
            "failed": failed,
            "passed": passed,
            "plain": f"{failed} test(s) failed",
        })
    meta = {"passed": passed, "failed": failed,
            "exit_code": proc.returncode, "output": stdout[:4000]}
    # pytest exits 1 when tests fail — that's a finding, not a tool error.
    return ToolResult(name="test_runner", ok=True, success=True,
                      returncode=proc.returncode,
                      output=stdout, findings=findings, meta=meta)