"""Broken-link crawler — BFS over same-origin links using requests."""

import re
from urllib.parse import urljoin, urlparse

import requests
from requests.exceptions import RequestException, Timeout

from tools.base import ToolResult

_URL_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

_SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".css", ".js",
             ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".mp4",
             ".mp3", ".webp", ".avif"}


def _is_same_origin(base, url):
    bp = urlparse(base)
    up = urlparse(url)
    if up.scheme and up.scheme != bp.scheme:
        return False
    if up.netloc and up.netloc != bp.netloc:
        return False
    return True


def _skip(url):
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _SKIP_EXT)


def crawl_links(start_url, max_pages: int = 100, timeout: float = 15.0):
    """Crawl starting from start_url, collecting status of each fetched link.

    Returns a ToolResult whose findings include both broken links (4xx/5xx,
    timeout, error) and healthy links (marked ok=True). The LLM can use the
    'broken' count to decide how to report.
    """
    session = requests.Session()
    session.headers["User-Agent"] = "ai-security-qa-agent/0.1"
    visited = set()
    queued = [start_url]
    results = []

    while queued and len(visited) < max_pages:
        url = queued.pop(0)
        if url in visited:
            continue
        visited.add(url)
        entry = {"url": url, "status": None, "kind": "ok", "note": None}
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            entry["status"] = resp.status_code
            entry["redirects"] = len(resp.history)
            if resp.status_code >= 400:
                entry["kind"] = "broken"
                entry["note"] = f"HTTP {resp.status_code}"
            elif resp.status_code >= 300:
                entry["kind"] = "broken"
                entry["note"] = "redirect without resolution"
            else:
                entry["kind"] = "ok"
            if "text/html" in resp.headers.get("Content-Type", "") or \
                    resp.url.endswith(("/", ".html", ".htm")):
                for href in _URL_RE.findall(resp.text or ""):
                    target = urljoin(url, href)
                    if _skip(target) or not _is_same_origin(start_url, target):
                        continue
                    if target not in visited and target not in queued:
                        queued.append(target)
        except Timeout:
            entry["kind"] = "broken"
            entry["note"] = "timeout"
        except RequestException as exc:
            entry["kind"] = "broken"
            entry["note"] = f"request error: {type(exc).__name__}"
        results.append(entry)

    broken = [r for r in results if r["kind"] == "broken"]
    for entry in results:
        entry["tool"] = "crawl_links"
        entry["plain"] = entry["note"]
    return ToolResult(
        name="crawl_links", ok=True, success=True, returncode=0,
        findings=results,
        meta={"urls_visited": len(results), "broken": len(broken)})