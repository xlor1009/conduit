"""Scan a codebase for registry event patterns."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from vendor_patch_cli.context_filter import file_has_vendor_context

SCAN_SUFFIXES = {".py", ".ts", ".js", ".tsx", ".jsx", ".yaml", ".yml", ".json"}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
}


@dataclass
class Match:
    event_id: str
    vendor: str
    path: Path
    line: int
    column: int
    snippet: str
    pattern: str
    rule_type: str


@dataclass
class ScanResult:
    matches: list[Match] = field(default_factory=list)
    events_with_hits: list[dict[str, Any]] = field(default_factory=list)

    @property
    def files(self) -> set[Path]:
        return {m.path for m in self.matches}


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        name = path.name
        if name.startswith(".env") or path.suffix.lower() in SCAN_SUFFIXES:
            yield path


def _glob_match(path: Path, patterns: list[str], root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    name = path.name
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern):
            return True
        # Also allow patterns like **/*.py via name-only *.py
        if pattern.startswith("*.") and name.endswith(pattern[1:]):
            return True
    return False


def _find_string_matches(
    path: Path,
    content: str,
    pattern: str,
    *,
    event_id: str,
    vendor: str,
    rule_type: str,
) -> list[Match]:
    hits: list[Match] = []
    if not pattern:
        return hits
    for lineno, line in enumerate(content.splitlines(), start=1):
        col = line.find(pattern)
        while col >= 0:
            hits.append(
                Match(
                    event_id=event_id,
                    vendor=vendor,
                    path=path,
                    line=lineno,
                    column=col + 1,
                    snippet=line.strip()[:200],
                    pattern=pattern,
                    rule_type=rule_type,
                )
            )
            col = line.find(pattern, col + len(pattern))
    return hits


def scan_path(
    root: Path,
    events: list[dict[str, Any]],
    *,
    require_context: bool = True,
) -> ScanResult:
    root = root.resolve()
    result = ScanResult()
    events_hit: dict[str, dict[str, Any]] = {}

    files = list(_iter_files(root))
    contents: dict[Path, str] = {}
    for path in files:
        try:
            contents[path] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

    pattern_scan_types = {
        "MODEL_DEPRECATION",
        "MODEL_REMOVED",
        "PARAM_RENAME",
        "API_BREAKING",
    }

    for event in events:
        event_id = event.get("event_id", "")
        vendor = event.get("vendor", "")
        affected = event.get("affected_pattern") or ""
        change_type = event.get("change_type") or ""
        rules = event.get("rules") or []

        # Scan affected_pattern only for code-literal style changes (not SDK package names)
        if change_type in pattern_scan_types and affected and len(affected) >= 3:
            for path, content in contents.items():
                if require_context and not file_has_vendor_context(path, content, vendor):
                    continue
                for match in _find_string_matches(
                    path,
                    content,
                    affected,
                    event_id=event_id,
                    vendor=vendor,
                    rule_type="AFFECTED_PATTERN",
                ):
                    result.matches.append(match)
                    events_hit[event_id] = event

        for rule in rules:
            rule_type = rule.get("type")
            target_files = rule.get("target_files") or ["*"]
            if rule_type == "EXACT_STRING_REPLACE":
                needle = rule.get("match") or ""
                for path, content in contents.items():
                    if not _glob_match(path, target_files, root):
                        continue
                    if require_context and not file_has_vendor_context(
                        path, content, vendor
                    ):
                        continue
                    hits = _find_string_matches(
                        path,
                        content,
                        needle,
                        event_id=event_id,
                        vendor=vendor,
                        rule_type=rule_type,
                    )
                    if hits:
                        result.matches.extend(hits)
                        events_hit[event_id] = event
            elif rule_type == "AST_PARAM_RENAME":
                old_param = rule.get("old_param") or ""
                for path, content in contents.items():
                    if not _glob_match(path, target_files, root):
                        continue
                    if require_context and not file_has_vendor_context(
                        path, content, vendor
                    ):
                        continue
                    # Keyword-arg style: old_param=
                    needle = f"{old_param}="
                    hits = _find_string_matches(
                        path,
                        content,
                        needle,
                        event_id=event_id,
                        vendor=vendor,
                        rule_type=rule_type,
                    )
                    if hits:
                        result.matches.extend(hits)
                        events_hit[event_id] = event
            elif rule_type == "DEPENDENCY_BUMP":
                package = rule.get("package") or affected
                # Hit if a dependency manifest pins this package
                for manifest_name in ("requirements.txt", "pyproject.toml", "package.json"):
                    manifest = root / manifest_name
                    if not manifest.is_file():
                        continue
                    try:
                        text = manifest.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    if package and package in text:
                        result.matches.append(
                            Match(
                                event_id=event_id,
                                vendor=vendor,
                                path=manifest,
                                line=1,
                                column=1,
                                snippet=f"dependency pin for {package}",
                                pattern=package,
                                rule_type=rule_type,
                            )
                        )
                        events_hit[event_id] = event

    # Deduplicate matches
    unique: dict[tuple, Match] = {}
    for m in result.matches:
        key = (m.event_id, str(m.path), m.line, m.column, m.pattern, m.rule_type)
        unique[key] = m
    result.matches = list(unique.values())
    result.events_with_hits = list(events_hit.values())
    return result
