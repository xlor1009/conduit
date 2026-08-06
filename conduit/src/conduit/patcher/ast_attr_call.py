"""AST attribute / call path rewrites (Python libcst + JS helpers)."""

from __future__ import annotations

from pathlib import Path

import libcst as cst


def _attr_chain(node: cst.BaseExpression) -> str | None:
    parts: list[str] = []
    cur: cst.BaseExpression | None = node
    while isinstance(cur, cst.Attribute):
        parts.append(cur.attr.value)
        cur = cur.value
    if isinstance(cur, cst.Name):
        parts.append(cur.value)
        return ".".join(reversed(parts))
    return None


def _make_attr(dotted: str) -> cst.BaseExpression:
    parts = dotted.split(".")
    node: cst.BaseExpression = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


class _AttrRenameTransformer(cst.CSTTransformer):
    def __init__(self, old_attr: str, new_attr: str) -> None:
        self.old_attr = old_attr
        self.new_attr = new_attr
        self.changes = 0

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        chain = _attr_chain(original_node)
        if chain == self.old_attr:
            self.changes += 1
            return _make_attr(self.new_attr)
        # Segment rename: replace trailing segment match in longer chains
        if chain and chain.endswith("." + self.old_attr.split(".")[-1]):
            # only when old_attr is a single segment and matches attr name
            if "." not in self.old_attr and updated_node.attr.value == self.old_attr:
                self.changes += 1
                return updated_node.with_changes(attr=cst.Name(self.new_attr))
        return updated_node


class _CallRewriteTransformer(cst.CSTTransformer):
    def __init__(self, old_callee: str, new_callee: str) -> None:
        self.old_callee = old_callee
        self.new_callee = new_callee
        self.changes = 0

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        chain = _attr_chain(original_node.func)
        if isinstance(original_node.func, cst.Name):
            chain = original_node.func.value
        if chain == self.old_callee:
            self.changes += 1
            return updated_node.with_changes(func=_make_attr(self.new_callee))
        return updated_node


def rename_python_attr(content: str, old_attr: str, new_attr: str) -> tuple[str, int]:
    if not old_attr or old_attr not in content:
        return content, 0
    try:
        module = cst.parse_module(content)
    except Exception:
        updated = content.replace(old_attr, new_attr)
        return updated, content.count(old_attr) if updated != content else 0
    transformer = _AttrRenameTransformer(old_attr, new_attr)
    updated = module.visit(transformer)
    if transformer.changes:
        return updated.code, transformer.changes
    updated = content.replace(old_attr, new_attr)
    return updated, content.count(old_attr) if updated != content else 0


def rewrite_python_call(content: str, old_callee: str, new_callee: str) -> tuple[str, int]:
    if not old_callee or old_callee not in content:
        return content, 0
    try:
        module = cst.parse_module(content)
    except Exception:
        updated = content.replace(old_callee, new_callee)
        return updated, content.count(old_callee) if updated != content else 0
    transformer = _CallRewriteTransformer(old_callee, new_callee)
    updated = module.visit(transformer)
    if transformer.changes:
        return updated.code, transformer.changes
    updated = content.replace(old_callee, new_callee)
    return updated, content.count(old_callee) if updated != content else 0


def apply_attr_rename(
    path: Path, content: str, *, old_attr: str, new_attr: str
) -> tuple[str, int]:
    if path.suffix == ".py":
        return rename_python_attr(content, old_attr, new_attr)
    if path.suffix in {".ts", ".js", ".tsx", ".jsx"}:
        from conduit.patcher.js_ast import rewrite_attr_js

        return rewrite_attr_js(content, old_attr, new_attr)
    updated = content.replace(old_attr, new_attr) if old_attr else content
    return updated, content.count(old_attr) if old_attr and updated != content else 0


def apply_call_rewrite(
    path: Path, content: str, *, old_callee: str, new_callee: str
) -> tuple[str, int]:
    if path.suffix == ".py":
        return rewrite_python_call(content, old_callee, new_callee)
    if path.suffix in {".ts", ".js", ".tsx", ".jsx"}:
        from conduit.patcher.js_ast import rewrite_attr_js

        return rewrite_attr_js(content, old_callee, new_callee)
    updated = content.replace(old_callee, new_callee) if old_callee else content
    return updated, content.count(old_callee) if old_callee and updated != content else 0
