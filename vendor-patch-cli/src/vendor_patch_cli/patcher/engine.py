"""Apply registry event rules to a target repository."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vendor_patch_cli.context_filter import file_has_vendor_context
from vendor_patch_cli.patcher.ast_param_rename import apply_param_rename
from vendor_patch_cli.patcher.dependency_update import apply_dependency_bump
from vendor_patch_cli.patcher.string_replace import exact_replace, regex_replace, write_if_changed
from vendor_patch_cli.scanner import SKIP_DIRS, SCAN_SUFFIXES


@dataclass
class ChangeRecord:
    event_id: str
    path: str
    rule_type: str
    detail: str


@dataclass
class PatchReport:
    changes: list[ChangeRecord] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    def add(self, record: ChangeRecord) -> None:
        self.changes.append(record)
        if record.path not in self.files_modified:
            self.files_modified.append(record.path)


def _iter_candidate_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.startswith(".env") or path.suffix.lower() in SCAN_SUFFIXES:
            out.append(path)
        elif path.name in {"requirements.txt", "pyproject.toml", "package.json"}:
            out.append(path)
    return out


def _glob_ok(path: Path, patterns: list[str], root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    name = path.name
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern):
            return True
    return False


def apply_events(
    root: Path,
    events: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    require_context: bool = True,
) -> PatchReport:
    root = root.resolve()
    report = PatchReport()
    files = _iter_candidate_files(root)

    for event in events:
        event_id = event.get("event_id", "")
        vendor = event.get("vendor", "")
        for rule in event.get("rules") or []:
            rule_type = rule.get("type")
            if rule_type == "DEPENDENCY_BUMP":
                for rel in apply_dependency_bump(root, rule, dry_run=dry_run):
                    report.add(
                        ChangeRecord(
                            event_id=event_id,
                            path=rel,
                            rule_type=rule_type,
                            detail=(
                                f"Bumped {rule.get('package')} "
                                f"{rule.get('from_version')} -> {rule.get('to_version')}"
                            ),
                        )
                    )
                continue

            target_files = rule.get("target_files") or ["*"]
            for path in files:
                if not _glob_ok(path, target_files, root):
                    continue
                try:
                    original = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                if require_context and not file_has_vendor_context(path, original, vendor):
                    continue

                updated = original
                detail = ""
                count = 0

                if rule_type == "EXACT_STRING_REPLACE":
                    updated, count = exact_replace(
                        original, rule.get("match", ""), rule.get("replace", "")
                    )
                    detail = f'Replaced "{rule.get("match")}" -> "{rule.get("replace")}" ({count}x)'
                elif rule_type == "REGEX_REPLACE":
                    updated, count = regex_replace(
                        original, rule.get("pattern", ""), rule.get("replace", "")
                    )
                    detail = f"Regex replace ({count}x)"
                elif rule_type == "AST_PARAM_RENAME":
                    updated, count = apply_param_rename(
                        path,
                        original,
                        function_target=rule.get("function_target", ""),
                        old_param=rule.get("old_param", ""),
                        new_param=rule.get("new_param", ""),
                    )
                    detail = (
                        f"Renamed param {rule.get('old_param')} -> "
                        f"{rule.get('new_param')} ({count}x)"
                    )
                else:
                    continue

                if count and write_if_changed(path, original, updated, dry_run=dry_run):
                    rel = str(path.relative_to(root))
                    report.add(
                        ChangeRecord(
                            event_id=event_id,
                            path=rel,
                            rule_type=rule_type or "UNKNOWN",
                            detail=detail,
                        )
                    )
    return report
