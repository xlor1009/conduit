"""Java language engine via tree-sitter with regex/string fallbacks."""

from __future__ import annotations

import re
from typing import Any

from conduit.patcher.languages.edits import SourceEdit, apply_edits
from conduit.patcher.languages.format import maybe_format
from conduit.patcher.languages.tree_sitter_util import node_text, walk, with_tree


def _scoped_name(source: bytes, node: Any) -> str | None:
    typ = node.type
    if typ == "identifier":
        return node_text(source, node)
    if typ == "scoped_identifier":
        parts: list[str] = []
        for child in node.children:
            if child.type in {"identifier", "scoped_identifier", "type_identifier"}:
                if child.type == "scoped_identifier":
                    t = _scoped_name(source, child)
                else:
                    t = node_text(source, child)
                if t:
                    parts.append(t)
            elif child.type == ".":
                continue
        return ".".join(parts) if parts else node_text(source, node)
    if typ == "type_identifier":
        return node_text(source, node)
    if typ == "field_access":
        obj = node.child_by_field_name("object")
        field = node.child_by_field_name("field")
        if obj is None or field is None:
            return node_text(source, node)
        left = _scoped_name(source, obj) or node_text(source, obj)
        right = node_text(source, field)
        return f"{left}.{right}"
    if typ == "method_invocation":
        name = node.child_by_field_name("name")
        obj = node.child_by_field_name("object")
        if name is None:
            return None
        right = node_text(source, name)
        if obj is None:
            return right
        left = _scoped_name(source, obj) or node_text(source, obj)
        return f"{left}.{right}"
    return None


class JavaEngine:
    suffixes = frozenset({".java"})

    def rewrite_import(self, content: str, old: str, new: str) -> tuple[str, int]:
        if not old:
            return content, 0

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            for node in walk(root):
                if node.type != "import_declaration":
                    continue
                text = node_text(source, node)
                matched = False
                for child in walk(node):
                    if child.type not in {"scoped_identifier", "identifier"}:
                        continue
                    name = _scoped_name(source, child) or node_text(source, child)
                    if name == old:
                        edits.append(
                            SourceEdit(child.start_byte, child.end_byte, new)
                        )
                        matched = True
                        break
                    if name.startswith(old + "."):
                        suffix = name[len(old) :]
                        edits.append(
                            SourceEdit(
                                child.start_byte, child.end_byte, new + suffix
                            )
                        )
                        matched = True
                        break
                if not matched and old in text:
                    updated_decl = text.replace(old, new, 1)
                    edits.append(
                        SourceEdit(node.start_byte, node.end_byte, updated_decl)
                    )
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=".java"), n

        result = with_tree(content, language="java", fn=via_ts)
        if result is not None:
            return result
        pattern = re.compile(
            rf"(import\s+(?:static\s+)?){re.escape(old)}(\s*;)"
        )
        updated, count = pattern.subn(rf"\1{new}\2", content)
        if count == 0 and old in content:
            updated = content.replace(old, new)
            count = content.count(old)
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
                if node.type not in {"field_access", "method_invocation", "identifier"}:
                    continue
                chain = _scoped_name(source, node)
                if chain != old:
                    continue
                if node.type == "method_invocation":
                    obj = node.child_by_field_name("object")
                    name = node.child_by_field_name("name")
                    if obj is not None and name is not None:
                        edits.append(
                            SourceEdit(obj.start_byte, name.end_byte, new)
                        )
                    elif name is not None:
                        edits.append(
                            SourceEdit(node.start_byte, name.end_byte, new)
                        )
                else:
                    edits.append(SourceEdit(node.start_byte, node.end_byte, new))
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=".java"), n

        result = with_tree(content, language="java", fn=via_ts)
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
        """Builder-style ``.oldParam(...)`` and ``old_param=`` heuristics."""
        if not old_param:
            return content, 0
        _ = function_target  # soft match; used by fallback nearness checks

        def via_ts(root: Any, source: bytes) -> tuple[str, int] | None:
            edits: list[SourceEdit] = []
            for node in walk(root):
                if node.type != "method_invocation":
                    continue
                name_node = node.child_by_field_name("name")
                name = node_text(source, name_node) if name_node else ""
                if name == old_param and name_node is not None:
                    edits.append(
                        SourceEdit(name_node.start_byte, name_node.end_byte, new_param)
                    )
            if not edits:
                return None
            updated, n = apply_edits(source, edits)
            return maybe_format(updated, suffix=".java"), n

        result = with_tree(content, language="java", fn=via_ts)
        if result is not None:
            return result
        pattern = re.compile(rf"(\.){re.escape(old_param)}(\s*\()")
        updated, count = pattern.subn(rf"\1{new_param}\2", content)
        if count == 0:
            pattern2 = re.compile(rf"(\b){re.escape(old_param)}(\s*=)")
            updated, count = pattern2.subn(rf"\1{new_param}\2", content)
        return updated, count
