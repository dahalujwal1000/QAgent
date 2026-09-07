"""Project-type detection — evidence-based classification of a repo path."""

import os
from dataclasses import dataclass, field


@dataclass
class ProjectProfile:
    path: str
    languages: list = field(default_factory=list)
    package_manager: str = "none"
    test_runner: str = "none"
    is_website: bool = False
    is_python: bool = False
    is_node: bool = False

    def summary(self) -> str:
        return (
            f"languages={','.join(self.languages) or 'unknown'} "
            f"pm={self.package_manager} tests={self.test_runner} "
            f"website={self.is_website}"
        )


_PY_MARKERS = ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]
_NODE_MARKERS = ["package.json", "package-lock.json", "yarn.lock"]


def _has(path, name):
    return os.path.exists(os.path.join(str(path), name))


def _find_files(root, predicate):
    matches = []
    try:
        for dirpath, _, files in os.walk(root):
            if ".git" in dirpath or "node_modules" in dirpath:
                continue
            if "__pycache__" in dirpath or ".venv" in dirpath or "venv" in dirpath:
                continue
            for fname in files:
                if predicate(fname):
                    matches.append(os.path.join(dirpath, fname))
    except (OSError, PermissionError):
        pass
    return matches


def _add_language(profile, lang):
    if lang not in profile.languages:
        profile.languages.append(lang)
    if lang == "python":
        profile.is_python = True
    if lang == "javascript":
        profile.is_node = True


def detect_project(path) -> ProjectProfile:
    """Detect the type of a local project rooted at `path`."""
    path = str(path)
    if not os.path.isdir(path):
        return ProjectProfile(path=path)
    profile = ProjectProfile(path=path)

    if any(_has(path, m) for m in _PY_MARKERS):
        _add_language(profile, "python")
        profile.package_manager = "pip"
    if any(_has(path, m) for m in _NODE_MARKERS):
        _add_language(profile, "javascript")
        profile.package_manager = "npm"

    # Django / Flask flags
    if _has(path, "manage.py"):
        _add_language(profile, "python")
        profile.is_website = True
    if _has(path, "flask_app.py"):
        _add_language(profile, "python")
        profile.is_website = True

    # No manifests but source files present → infer from extensions.
    if not profile.languages:
        source = _find_files(path, lambda n: n.lower().endswith((".py", ".js", ".ts")))
        for s in source:
            if s.endswith(".py"):
                _add_language(profile, "python")
            elif s.endswith((".js", ".ts")):
                _add_language(profile, "javascript")

    # Website: static html present AND (node project OR no language at all).
    html_files = _find_files(path, lambda n: n.lower().endswith((".html", ".htm")))
    if html_files:
        profile.is_website = True

    if not profile.package_manager:
        if profile.is_python:
            profile.package_manager = "pip"
        elif profile.is_node:
            profile.package_manager = "npm"

    if profile.is_python:
        profile.test_runner = "pytest"
    elif profile.is_node:
        profile.test_runner = "node"

    return profile