"""Detect module plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from conduit.detect.models import ChangeSignal


@dataclass
class DetectContext:
    """Context passed to vendor detect modules."""

    repo_root: Path
    installed: dict[str, str] = field(default_factory=dict)  # package -> version
    fixture_mode: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


class DetectModule(ABC):
    """Vendor-specific signal source plugged into core detect."""

    name: str = "module"
    packages: list[str] = []

    def applies(self, installed: dict[str, str]) -> bool:
        if not self.packages:
            return True
        wanted = {p.lower() for p in self.packages}
        return any(name.lower() in wanted for name in installed)

    @abstractmethod
    def run(self, ctx: DetectContext) -> list[ChangeSignal]:
        raise NotImplementedError
