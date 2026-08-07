"""Suffix → language engine registry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conduit.patcher.languages.base import LanguageEngine


def engine_for(path: Path | str) -> LanguageEngine | None:
    """Return a language engine for ``path``'s suffix, or ``None``."""
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        from conduit.patcher.languages.python import PythonEngine

        return PythonEngine()
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        from conduit.patcher.languages.javascript import JsTsEngine

        return JsTsEngine(suffix=suffix)
    if suffix == ".java":
        from conduit.patcher.languages.java import JavaEngine

        return JavaEngine()
    if suffix == ".go":
        from conduit.patcher.languages.go import GoEngine

        return GoEngine()
    return None


def apply_rewrite_import(path: Path, content: str, old: str, new: str) -> tuple[str, int]:
    eng = engine_for(path)
    if eng is None:
        if not old:
            return content, 0
        updated = content.replace(old, new)
        return updated, content.count(old) if updated != content else 0
    return eng.rewrite_import(content, old, new)


def apply_rename_attr(path: Path, content: str, old: str, new: str) -> tuple[str, int]:
    eng = engine_for(path)
    if eng is None:
        return content, 0
    return eng.rename_attr(content, old, new)


def apply_rewrite_call(path: Path, content: str, old: str, new: str) -> tuple[str, int]:
    eng = engine_for(path)
    if eng is None:
        return content, 0
    return eng.rewrite_call(content, old, new)


def apply_rename_param(
    path: Path,
    content: str,
    *,
    function_target: str,
    old_param: str,
    new_param: str,
) -> tuple[str, int]:
    eng = engine_for(path)
    if eng is None:
        return content, 0
    return eng.rename_param(
        content,
        function_target=function_target,
        old_param=old_param,
        new_param=new_param,
    )
