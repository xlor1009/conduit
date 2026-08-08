"""Core detect orchestrator: lockfile jumps + vendor modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from conduit.detect.lockfile_diff import detect_lockfile_jumps
from conduit.detect.manifests import read_installed
from conduit.detect.models import ChangeSignal
from conduit.detect.modules.base import DetectContext
from conduit.detect.modules.discovery import load_modules


@dataclass
class DetectResult:
    signals: list[ChangeSignal] = field(default_factory=list)
    installed: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def packages(self) -> set[str]:
        return {s.package for s in self.signals if s.package}


def run_detect(
    root: Path,
    *,
    base_ref: str | None = None,
    majors_only: bool = True,
    module_names: list[str] | None = None,
    skip_modules: bool = False,
    skip_lockfile: bool = False,
    demo: bool = False,
) -> DetectResult:
    root = root.resolve()
    installed = read_installed(root)
    signals: list[ChangeSignal] = []
    warnings: list[str] = []

    if not skip_lockfile:
        for jump in detect_lockfile_jumps(
            root, base_ref=base_ref, majors_only=majors_only
        ):
            signals.append(jump.to_signal())
            installed.setdefault(jump.name, jump.to_version)

    if not skip_modules:
        ctx = DetectContext(
            repo_root=root,
            installed=installed,
            demo=demo,
        )
        for mod in load_modules(names=module_names):
            if (
                module_names is None
                and installed
                and not mod.applies(installed)
            ):
                continue
            try:
                signals.extend(mod.run(ctx))
            except Exception as exc:
                warnings.append(f"detect module {mod.name}: {exc}")
            warnings.extend(list(ctx.extra.get("warnings") or []))
            ctx.extra["warnings"] = []

    return DetectResult(signals=signals, installed=installed, warnings=warnings)
