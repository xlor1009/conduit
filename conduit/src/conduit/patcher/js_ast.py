"""JS/TS AST helpers via tree-sitter when available, else regex/string fallbacks."""

from __future__ import annotations

import re
from typing import Callable


def _try_tree_sitter_replace(
    content: str,
    *,
    language: str,
    query_and_replace: Callable[[object, bytes], tuple[str, int] | None],
) -> tuple[str, int] | None:
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    lang_obj = None
    try:
        if language in {"javascript", "js", "jsx"}:
            import tree_sitter_javascript as tsjs

            lang_obj = Language(tsjs.language())
        elif language in {"typescript", "ts", "tsx"}:
            try:
                import tree_sitter_typescript as tsts

                lang_obj = Language(tsts.language_typescript())
            except Exception:
                import tree_sitter_javascript as tsjs

                lang_obj = Language(tsjs.language())
    except Exception:
        return None

    if lang_obj is None:
        return None

    parser = Parser(lang_obj)
    source = content.encode("utf-8")
    tree = parser.parse(source)
    try:
        return query_and_replace(tree, source)
    except Exception:
        return None


def rewrite_imports_js(content: str, old_import: str, new_import: str) -> tuple[str, int]:
    if not old_import:
        return content, 0

    def via_ts(tree: object, source: bytes) -> tuple[str, int] | None:
        # Lightweight: still use string replace on import string literals found in tree
        # Full node rewrite is complex; validate presence then replace.
        text = source.decode("utf-8")
        if old_import not in text:
            return text, 0
        updated = text.replace(old_import, new_import)
        return updated, text.count(old_import)

    result = _try_tree_sitter_replace(
        content, language="javascript", query_and_replace=via_ts
    )
    if result is not None:
        return result

    patterns = [
        (rf"""(from\s+['"]){re.escape(old_import)}(['"])""", rf"\1{new_import}\2"),
        (
            rf"""(import\s*\(\s*['"]){re.escape(old_import)}(['"]\s*\))""",
            rf"\1{new_import}\2",
        ),
        (
            rf"""(require\s*\(\s*['"]){re.escape(old_import)}(['"]\s*\))""",
            rf"\1{new_import}\2",
        ),
    ]
    updated = content
    count = 0
    for pat, repl in patterns:
        updated, n = re.subn(pat, repl, updated)
        count += n
    if count == 0 and old_import in content:
        updated = content.replace(old_import, new_import)
        count = content.count(old_import)
    return updated, count


def rewrite_attr_js(content: str, old_attr: str, new_attr: str) -> tuple[str, int]:
    if not old_attr or old_attr not in content:
        return content, 0
    # Word-boundary-ish replace for dotted paths
    pattern = re.compile(rf"(?<![\w.]){re.escape(old_attr)}(?![\w])")
    updated, count = pattern.subn(new_attr, content)
    return updated, count
