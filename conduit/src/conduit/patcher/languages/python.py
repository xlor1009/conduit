"""Python language engine (libcst)."""

from __future__ import annotations

from conduit.patcher.ast_attr_call import rename_python_attr, rewrite_python_call
from conduit.patcher.ast_import_rewrite import rewrite_python_imports
from conduit.patcher.ast_param_rename import rename_python_params


class PythonEngine:
    suffixes = frozenset({".py"})

    def rewrite_import(self, content: str, old: str, new: str) -> tuple[str, int]:
        return rewrite_python_imports(content, old, new)

    def rename_attr(self, content: str, old: str, new: str) -> tuple[str, int]:
        return rename_python_attr(content, old, new)

    def rewrite_call(self, content: str, old: str, new: str) -> tuple[str, int]:
        return rewrite_python_call(content, old, new)

    def rename_param(
        self,
        content: str,
        *,
        function_target: str,
        old_param: str,
        new_param: str,
    ) -> tuple[str, int]:
        return rename_python_params(
            content,
            function_target=function_target,
            old_param=old_param,
            new_param=new_param,
        )
