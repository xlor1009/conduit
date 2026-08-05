"""Base worker interface for signal ingestion."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from vendor_signal_registry.models import RawSignal


def package_root() -> Path:
    """vendor-signal-registry/ package root (contains fixtures/, data/, dist/)."""
    return Path(__file__).resolve().parents[3]


def fixtures_dir() -> Path:
    return package_root() / "fixtures"


def data_dir() -> Path:
    return package_root() / "data"


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Worker(ABC):
    """Ingestion worker that emits zero or more RawSignal objects."""

    name: str = "worker"

    @abstractmethod
    def run(self) -> list[RawSignal]:
        raise NotImplementedError
