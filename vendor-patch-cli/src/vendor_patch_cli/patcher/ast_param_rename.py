"""AST parameter rename via libcst (Python) and regex fallback (TS/JS)."""

from __future__ import annotations

import re
from pathlib import Path

import libcst as cst


class _ParamRenameTransformer(cst.CSTTransformer):
    def __init__(self, function_target: str, old_param: str, new_param: str) -> None:
        self.function_target = function_target
        self.old_param = old_param
        self.new_param = new_param
        self.changes = 0
        # Match trailing segment of function_target, e.g. chat.completions.create
        self._suffix = function_target.split(".")[-1]

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if not self._call_matches(original_node):
            return updated_node
        new_args: list[cst.BaseArgument] = []
        changed = False
        for arg in updated_node.args:
            if (
                isinstance(arg, cst.Arg)
                and arg.keyword is not None
                and arg.keyword.value == self.old_param
            ):
                new_args.append(arg.with_changes(keyword=cst.Name(self.new_param)))
                changed = True
                self.changes += 1
            else:
                new_args.append(arg)
        if changed:
            return updated_node.with_changes(args=new_args)
        return updated_node

    def _call_matches(self, node: cst.Call) -> bool:
        func = node.func
        # Attribute chain ending with create / target suffix
        name = _attr_chain(func)
        if not name:
            return False
        if name == self.function_target or name.endswith(self.function_target):
            return True
        # Soft match: ends with same final segment (create)
        return name.endswith(self._suffix)


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


def rename_python_params(
    content: str,
    *,
    function_target: str,
    old_param: str,
    new_param: str,
) -> tuple[str, int]:
    try:
        module = cst.parse_module(content)
    except Exception:
        # Fall back to regex if parse fails
        return rename_js_params(
            content, function_target=function_target, old_param=old_param, new_param=new_param
        )
    transformer = _ParamRenameTransformer(function_target, old_param, new_param)
    updated = module.visit(transformer)
    return updated.code, transformer.changes


def rename_js_params(
    content: str,
    *,
    function_target: str,
    old_param: str,
    new_param: str,
) -> tuple[str, int]:
    """Heuristic rename of object-literal keys / kwargs near function_target calls."""
    # Replace `old_param:` and `old_param=` that appear as property/kwarg names
    pattern = re.compile(rf"(\b){re.escape(old_param)}(\s*[:=])")
    # Prefer applying near function_target suffix occurrences
    suffix = function_target.split(".")[-1]
    if suffix not in content and function_target not in content:
        # Still rename keyword-style usages as a soft fallback
        new_content, count = pattern.subn(rf"\1{new_param}\2", content)
        return new_content, count

    new_content, count = pattern.subn(rf"\1{new_param}\2", content)
    return new_content, count


def apply_param_rename(
    path: Path,
    content: str,
    *,
    function_target: str,
    old_param: str,
    new_param: str,
) -> tuple[str, int]:
    if path.suffix == ".py":
        return rename_python_params(
            content,
            function_target=function_target,
            old_param=old_param,
            new_param=new_param,
        )
    if path.suffix in {".ts", ".js", ".tsx", ".jsx"}:
        return rename_js_params(
            content,
            function_target=function_target,
            old_param=old_param,
            new_param=new_param,
        )
    return content, 0
