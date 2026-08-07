"""Shared tree-sitter parse helpers (optional dependency)."""

from __future__ import annotations

from typing import Any, Callable


def try_parse(content: str, *, language: str) -> tuple[Any, bytes] | None:
    """Return ``(tree, source_bytes)`` or ``None`` if grammar/parser unavailable."""
    try:
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    lang_obj = _load_language(language)
    if lang_obj is None:
        return None
    try:
        parser = Parser(lang_obj)
        source = content.encode("utf-8")
        tree = parser.parse(source)
        return tree, source
    except Exception:
        return None


def _load_language(language: str) -> Any | None:
    try:
        from tree_sitter import Language
    except ImportError:
        return None

    try:
        if language in {"javascript", "js", "jsx"}:
            import tree_sitter_javascript as tsjs

            return Language(tsjs.language())
        if language in {"typescript", "ts"}:
            import tree_sitter_typescript as tsts

            return Language(tsts.language_typescript())
        if language == "tsx":
            import tree_sitter_typescript as tsts

            try:
                return Language(tsts.language_tsx())
            except Exception:
                return Language(tsts.language_typescript())
        if language == "java":
            import tree_sitter_java as tsjava

            return Language(tsjava.language())
        if language == "go":
            import tree_sitter_go as tsgo

            return Language(tsgo.language())
    except Exception:
        return None
    return None


def walk(node: Any) -> list[Any]:
    """Depth-first list of nodes including ``node``."""
    out = [node]
    cursor = getattr(node, "children", None)
    if not cursor:
        return out
    for child in cursor:
        out.extend(walk(child))
    return out


def node_text(source: bytes, node: Any) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def with_tree(
    content: str,
    *,
    language: str,
    fn: Callable[[Any, bytes], tuple[str, int] | None],
) -> tuple[str, int] | None:
    parsed = try_parse(content, language=language)
    if parsed is None:
        return None
    tree, source = parsed
    try:
        return fn(tree.root_node, source)
    except Exception:
        return None
