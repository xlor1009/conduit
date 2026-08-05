"""Fast import-string pre-filter before AST/patch work."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
    ".conduit",
}

SCAN_SUFFIXES = {".py", ".ts", ".js", ".tsx", ".jsx"}


def _import_patterns(package: str) -> list[re.Pattern[str]]:
    pkg = re.escape(package)
    return [
        re.compile(rf"\bfrom\s+{pkg}\b"),
        re.compile(rf"\bimport\s+{pkg}\b"),
        re.compile(rf"""from\s+['"]{pkg}['"]"""),
        re.compile(rf"""import\s*\(\s*['"]{pkg}['"]"""),
        re.compile(rf"""require\s*\(\s*['"]{pkg}['"]\s*\)"""),
        re.compile(rf"""from\s+['"]{pkg}/"""),
    ]


def iter_source_files(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SCAN_SUFFIXES:
            yield path


def prune_by_imports(root: Path, packages: Iterable[str]) -> list[Path]:
    """Return files that appear to import any of the given packages."""
    pkgs = [p for p in packages if p]
    if not pkgs:
        return list(iter_source_files(root))

    patterns = {pkg: _import_patterns(pkg) for pkg in pkgs}
    hits: list[Path] = []
    for path in iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pkg, pats in patterns.items():
            if any(p.search(text) for p in pats):
                hits.append(path)
                break
            # soft: package name appears near import-like tokens
            if pkg in text and ("import" in text or "require" in text):
                hits.append(path)
                break
    return hits
