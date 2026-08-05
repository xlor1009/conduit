"""Exact and regex string replacement helpers."""

from __future__ import annotations

import re
from pathlib import Path


def exact_replace(content: str, match: str, replace: str) -> tuple[str, int]:
    if not match or match not in content:
        return content, 0
    count = content.count(match)
    return content.replace(match, replace), count


def regex_replace(content: str, pattern: str, replace: str) -> tuple[str, int]:
    compiled = re.compile(pattern)
    new_content, count = compiled.subn(replace, content)
    return new_content, count


def write_if_changed(path: Path, original: str, updated: str, *, dry_run: bool) -> bool:
    if original == updated:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True
