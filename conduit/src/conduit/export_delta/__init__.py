"""Compare public exports between two package versions to narrow migration scope."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from conduit.export_delta.diff import diff_exports
from conduit.export_delta.extract import extract_exports_from_tree
from conduit.export_delta.resolve import resolve_package_tree


@dataclass
class ExportDelta:
    package: str
    from_version: str
    to_version: str
    ecosystem: str
    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    renamed: dict[str, str] = field(default_factory=dict)
    from_symbols: set[str] = field(default_factory=set)
    to_symbols: set[str] = field(default_factory=set)
    skipped_reason: str | None = None

    @property
    def changed_symbols(self) -> set[str]:
        return (
            set(self.removed)
            | set(self.added)
            | set(self.renamed.keys())
            | set(self.renamed.values())
        )

    def to_dict(self) -> dict:
        return {
            "package": self.package,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "ecosystem": self.ecosystem,
            "added": sorted(self.added),
            "removed": sorted(self.removed),
            "renamed": dict(sorted(self.renamed.items())),
            "skipped_reason": self.skipped_reason,
        }


def compute_export_delta(
    *,
    package: str,
    from_version: str,
    to_version: str,
    ecosystem: str = "pypi",
    cache_root: Path | None = None,
) -> ExportDelta:
    """Fetch both versions (cached) and diff public symbols. Soft-fails on errors."""
    result = ExportDelta(
        package=package,
        from_version=from_version,
        to_version=to_version,
        ecosystem=ecosystem,
    )
    if not package:
        result.skipped_reason = "missing package name"
        return result

    try:
        old_tree = resolve_package_tree(
            package, from_version, ecosystem=ecosystem, cache_root=cache_root
        )
        new_tree = resolve_package_tree(
            package, to_version, ecosystem=ecosystem, cache_root=cache_root
        )
    except Exception as exc:
        result.skipped_reason = f"resolve failed: {exc}"
        return result

    if old_tree is None or new_tree is None:
        result.skipped_reason = "could not resolve one or both package versions"
        return result

    try:
        old_syms = extract_exports_from_tree(old_tree, package=package, ecosystem=ecosystem)
        new_syms = extract_exports_from_tree(new_tree, package=package, ecosystem=ecosystem)
    except Exception as exc:
        result.skipped_reason = f"extract failed: {exc}"
        return result

    result.from_symbols = old_syms
    result.to_symbols = new_syms
    added, removed, renamed = diff_exports(old_syms, new_syms)
    result.added = added
    result.removed = removed
    result.renamed = renamed
    return result


def prune_by_export_symbols(
    files: Iterable[Path],
    delta: ExportDelta,
) -> list[Path]:
    """
    Keep files that mention any changed symbol.
    If delta is unusable or no file mentions a symbol, return the original list.
    """
    file_list = list(files)
    symbols = {s for s in delta.changed_symbols if s and len(s) > 1}
    if delta.skipped_reason or not symbols:
        return file_list

    hits: list[Path] = []
    for path in file_list:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            hits.append(path)
            continue
        if any(sym in text for sym in symbols):
            hits.append(path)
    return hits if hits else file_list
