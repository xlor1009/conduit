"""Exact and regex string replacement helpers."""

from __future__ import annotations

import re
from pathlib import Path

# Characters that continue an identifier / model-id token. Prevents:
# - "davinci" matching inside text_davinci_003
# - "gpt-4" matching inside gpt-4-0613
# - replacements with "-" / "." breaking Python def names
_TOKEN_CHAR = r"A-Za-z0-9_.-"


def exact_replace(content: str, match: str, replace: str) -> tuple[str, int]:
    """Replace exact substrings that are not part of a larger token.

    Uses boundaries so model ids and identifiers are not partially rewritten
    (which can inject ``-`` / ``.`` into Python names and cause SyntaxError).
    """
    if not match or match not in content:
        return content, 0
    pattern = re.compile(
        rf"(?<![{_TOKEN_CHAR}]){re.escape(match)}(?![{_TOKEN_CHAR}])"
    )
    new_content, count = pattern.subn(replace, content)
    return new_content, count


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
