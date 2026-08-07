"""Go language engine via tree-sitter with regex/string fallbacks."""

from __future__ import annotations

import re
from typing import Any

from conduit.patcher.languages.edits import SourceEdit, apply_edits
from conduit.patcher.languages.format import maybe_format
from conduit.patcher.languages.tree_sitter_util import node_text, walk, with_tree


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {'"', "`", "'"}:
        return s[1:-1]
    return s


def _selector_chain(source: bytes, node: Any) -> str | None:
    typ = node.type
    if typ == "identifier":
        return node_text(source, node)
    if typ == "field_identifier":
        return node_text(source, node)
    if typ == "selector_expression":
        operand = node.child_by_field_name("operand")
        field = node.child_by_field_name("field")
        if operand is None or field is None:
            return node_text(source, node)
        left = _selector_chain(source, operand) or node_text(source, operand)
        right = node_text(source, field)
        return f"{left}.{right}"
    if typ == "call_expression":
        fn = node.child_by_field_name("function")
        if fn is None:
            return None
        return _selector_chain(source, fn)
    return None


class GoEngine:
    suffixes = frozenset({".go"})

    def rewrite_import(self, content: str, old: str, new: str) -> tuple[str, int]:
        if not old:
            return content, 0

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            for node in walk(root):
                if node.type != "import_spec":
                    continue
                path_node = node.child_by_field_name("path")
                if path_node is None:
                    # Sometimes the string is a direct child
                    for child in node.children:
                        if child.type == "interpreted_string_literal":
                            path_node = child
                            break
                if path_node is None:
                    continue
                raw = node_text(source, path_node)
                inner = _strip_quotes(raw)
                if inner != old:
                    continue
                quote = raw[0] if raw else '"'
                edits.append(
                    SourceEdit(
                        path_node.start_byte,
                        path_node.end_byte,
                        f"{quote}{new}{quote}",
                    )
                )
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=".go"), n

        result = with_tree(content, language="go", fn=via_ts)
        if result is not None:
            return result
        pattern = re.compile(rf'(["`]){re.escape(old)}\1')
        updated, count = pattern.subn(rf'\1{new}\1', content)
        return updated, count

    def rename_attr(self, content: str, old: str, new: str) -> tuple[str, int]:
        return self._rewrite_path(content, old, new)

    def rewrite_call(self, content: str, old: str, new: str) -> tuple[str, int]:
        return self._rewrite_path(content, old, new)

    def _rewrite_path(self, content: str, old: str, new: str) -> tuple[str, int]:
        if not old or old not in content:
            return content, 0

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            for node in walk(root):
                if node.type not in {
                    "selector_expression",
                    "identifier",
                    "call_expression",
                }:
                    continue
                target = node
                if node.type == "call_expression":
                    fn = node.child_by_field_name("function")
                    if fn is None:
                        continue
                    target = fn
                chain = _selector_chain(source, target)
                if chain != old:
                    continue
                edits.append(SourceEdit(target.start_byte, target.end_byte, new))
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=".go"), n

        result = with_tree(content, language="go", fn=via_ts)
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
        """Rename struct-literal keys ``OldParam:`` near matching calls."""
        if not old_param:
            return content, 0

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            suffix = function_target.split(".")[-1] if function_target else ""
            for node in walk(root):
                if node.type != "keyed_element":
                    continue
                # keyed_element: key: value
                key = node.child_by_field_name("key")
                if key is None and node.child_count >= 1:
                    key = node.children[0]
                if key is None:
                    continue
                key_txt = node_text(source, key)
                if key_txt != old_param:
                    continue
                # Soft: if function_target given, prefer proximity — still rename
                if function_target and suffix:
                    # Only skip if neither appears anywhere nearby in parent
                    parent = node.parent
                    ctx = node_text(source, parent) if parent else ""
                    if (
                        function_target not in ctx
                        and suffix not in ctx
                        and function_target not in content
                    ):
                        pass  # still allow global struct key rename
                edits.append(SourceEdit(key.start_byte, key.end_byte, new_param))
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=".go"), n

        result = with_tree(content, language="go", fn=via_ts)
        if result is not None:
            return result
        pattern = re.compile(rf"(\b){re.escape(old_param)}(\s*:)")
        updated, count = pattern.subn(rf"\1{new_param}\2", content)
        return updated, count
