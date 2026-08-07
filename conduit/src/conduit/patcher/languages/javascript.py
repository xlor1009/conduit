"""JS/TS language engine via tree-sitter with regex/string fallbacks."""

from __future__ import annotations

import re
from typing import Any

from conduit.patcher.languages.edits import SourceEdit, apply_edits
from conduit.patcher.languages.format import maybe_format
from conduit.patcher.languages.tree_sitter_util import node_text, walk, with_tree


def _lang_for_suffix(suffix: str) -> str:
    if suffix in {".ts"}:
        return "typescript"
    if suffix in {".tsx"}:
        return "tsx"
    return "javascript"


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {"'", '"', "`"}:
        return s[1:-1]
    return s


def _member_chain(source: bytes, node: Any) -> str | None:
    """Build dotted path for member_expression / identifier chains."""
    typ = node.type
    if typ == "identifier":
        return node_text(source, node)
    if typ == "property_identifier":
        return node_text(source, node)
    if typ in {"member_expression", "member_expression_safe"}:
        obj = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        if obj is None or prop is None:
            return None
        left = _member_chain(source, obj)
        right = node_text(source, prop)
        if left is None:
            return None
        return f"{left}.{right}"
    return None


def _call_callee_node(node: Any) -> Any | None:
    if node.type != "call_expression":
        return None
    return node.child_by_field_name("function")


class JsTsEngine:
    """Rich JS/TS transforms; ``suffix`` selects grammar when parsing."""

    suffixes = frozenset({".js", ".jsx", ".ts", ".tsx"})

    def __init__(self, suffix: str = ".js") -> None:
        self.suffix = suffix if suffix in self.suffixes else ".js"

    def rewrite_import(self, content: str, old: str, new: str) -> tuple[str, int]:
        if not old:
            return content, 0
        language = _lang_for_suffix(self.suffix)

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            for node in walk(root):
                if node.type not in {"string", "string_fragment"}:
                    continue
                # Prefer full string nodes
                if node.type == "string_fragment":
                    continue
                raw = node_text(source, node)
                inner = _strip_quotes(raw)
                if inner != old:
                    continue
                # Only rewrite string literals under import/export/require/import()
                parent = node.parent
                if parent is None:
                    continue
                if not _is_import_string_context(parent, source):
                    continue
                # Preserve quote style
                quote = raw[0] if raw else '"'
                edits.append(
                    SourceEdit(node.start_byte, node.end_byte, f"{quote}{new}{quote}")
                )
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=self.suffix), n

        result = with_tree(content, language=language, fn=via_ts)
        if result is not None:
            return result
        return _fallback_rewrite_imports(content, old, new)

    def rename_attr(self, content: str, old: str, new: str) -> tuple[str, int]:
        return self._rewrite_path(content, old, new)

    def rewrite_call(self, content: str, old: str, new: str) -> tuple[str, int]:
        return self._rewrite_path(content, old, new)

    def _rewrite_path(self, content: str, old: str, new: str) -> tuple[str, int]:
        if not old or old not in content:
            return content, 0
        language = _lang_for_suffix(self.suffix)

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            for node in walk(root):
                if node.type not in {
                    "member_expression",
                    "identifier",
                    "call_expression",
                }:
                    continue
                target = node
                if node.type == "call_expression":
                    callee = _call_callee_node(node)
                    if callee is None:
                        continue
                    target = callee
                chain = _member_chain(source, target)
                if chain != old:
                    continue
                edits.append(SourceEdit(target.start_byte, target.end_byte, new))
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=self.suffix), n

        result = with_tree(content, language=language, fn=via_ts)
        if result is not None:
            return result
        pattern = re.compile(rf"(?<![\w.]){re.escape(old)}(?![\w])")
        updated, count = pattern.subn(new, content)
        return updated, count

    def rename_param(
        self,
        content: str,
        *,
        function_target: str,
        old_param: str,
        new_param: str,
    ) -> tuple[str, int]:
        if not old_param:
            return content, 0
        language = _lang_for_suffix(self.suffix)

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            suffix = function_target.split(".")[-1] if function_target else ""
            for node in walk(root):
                if node.type != "call_expression":
                    continue
                callee = _call_callee_node(node)
                if callee is None:
                    continue
                chain = _member_chain(source, callee) or ""
                if function_target and not (
                    chain == function_target
                    or chain.endswith(function_target)
                    or (suffix and chain.endswith(suffix))
                ):
                    continue
                args = node.child_by_field_name("arguments")
                if args is None:
                    continue
                for child in walk(args):
                    # object property: { old_param: ... } or { old_param, }
                    if child.type == "pair":
                        key = child.child_by_field_name("key")
                        if key is None:
                            continue
                        key_txt = node_text(source, key)
                        if key_txt.strip("\"'") == old_param:
                            edits.append(
                                SourceEdit(key.start_byte, key.end_byte, new_param)
                            )
                    elif child.type == "shorthand_property_identifier":
                        if node_text(source, child) == old_param:
                            edits.append(
                                SourceEdit(
                                    child.start_byte, child.end_byte, new_param
                                )
                            )
                    elif child.type == "assignment_expression":
                        left = child.child_by_field_name("left")
                        if left is not None and node_text(source, left) == old_param:
                            edits.append(
                                SourceEdit(left.start_byte, left.end_byte, new_param)
                            )
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=self.suffix), n

        result = with_tree(content, language=language, fn=via_ts)
        if result is not None:
            return result
        return _fallback_rename_params(
            content,
            function_target=function_target,
            old_param=old_param,
            new_param=new_param,
        )


def _is_import_string_context(parent: Any, source: bytes) -> bool:
    """True if string sits in import/export/require/dynamic import."""
    cur = parent
    depth = 0
    while cur is not None and depth < 8:
        typ = cur.type
        if typ in {
            "import_statement",
            "export_statement",
            "import_clause",
            "named_imports",
            "namespace_import",
        }:
            return True
        if typ == "call_expression":
            fn = cur.child_by_field_name("function")
            if fn is not None:
                name = node_text(source, fn)
                if name in {"require", "import"}:
                    return True
        if typ == "string" and cur.parent is not None:
            cur = cur.parent
            depth += 1
            continue
        cur = cur.parent
        depth += 1
    # also: `from 'x'` — parent of string is often import_statement directly
    text = node_text(source, parent) if parent else ""
    if "from" in text or "require" in text or "import" in text:
        return True
    return False


def _fallback_rewrite_imports(content: str, old: str, new: str) -> tuple[str, int]:
    patterns = [
        (rf"""(from\s+['"]){re.escape(old)}(['"])""", rf"\1{new}\2"),
        (
            rf"""(import\s*\(\s*['"]){re.escape(old)}(['"]\s*\))""",
            rf"\1{new}\2",
        ),
        (
            rf"""(require\s*\(\s*['"]){re.escape(old)}(['"]\s*\))""",
            rf"\1{new}\2",
        ),
    ]
    updated = content
    count = 0
    for pat, repl in patterns:
        updated, n = re.subn(pat, repl, updated)
        count += n
    if count == 0 and old in content:
        updated = content.replace(old, new)
        count = content.count(old)
    return updated, count


def _fallback_rename_params(
    content: str,
    *,
    function_target: str,
    old_param: str,
    new_param: str,
) -> tuple[str, int]:
    pattern = re.compile(rf"(\b){re.escape(old_param)}(\s*[:=])")
    suffix = function_target.split(".")[-1] if function_target else ""
    if suffix and suffix not in content and function_target not in content:
        new_content, count = pattern.subn(rf"\1{new_param}\2", content)
        return new_content, count
    new_content, count = pattern.subn(rf"\1{new_param}\2", content)
    return new_content, count
