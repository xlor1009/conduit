"""JS/TS AST helpers — thin re-export of the pluggable JsTsEngine."""

from __future__ import annotations

from conduit.patcher.languages.javascript import JsTsEngine

_engine = JsTsEngine()


def rewrite_imports_js(content: str, old_import: str, new_import: str) -> tuple[str, int]:
    return _engine.rewrite_import(content, old_import, new_import)


def rewrite_attr_js(content: str, old_attr: str, new_attr: str) -> tuple[str, int]:
    return _engine.rename_attr(content, old_attr, new_attr)
