"""Language engine protocol for pluggable AST transforms."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LanguageEngine(Protocol):
    """Per-language AST transform surface shared by packet rule types."""

    suffixes: frozenset[str]

    def rewrite_import(self, content: str, old: str, new: str) -> tuple[str, int]:
        """Rewrite import/module paths. Returns (updated, change_count)."""

    def rename_attr(self, content: str, old: str, new: str) -> tuple[str, int]:
        """Rename attribute / member access paths."""

    def rewrite_call(self, content: str, old: str, new: str) -> tuple[str, int]:
        """Rewrite call / callee paths."""

    def rename_param(
        self,
        content: str,
        *,
        function_target: str,
        old_param: str,
        new_param: str,
    ) -> tuple[str, int]:
        """Rename keyword / named parameters near a call target."""
