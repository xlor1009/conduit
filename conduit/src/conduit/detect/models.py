"""Unified change signals produced by lockfile diff and vendor modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ChangeSignal:
    """Normalized signal that feeds packet synthesis and apply."""

    source: str  # e.g. "lockfile", "module:openai"
    package: str
    change_type: str
    severity: str = "WARNING"
    from_version: str | None = None
    to_version: str | None = None
    ecosystem: str | None = None
    affected_pattern: str | None = None
    replacement_pattern: str | None = None
    description: str | None = None
    source_url: str | None = None
    deadline: str | None = None
    hints: dict[str, Any] = field(default_factory=dict)
    suggested_rules: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None and v != {} and v != []}


@dataclass
class VersionJump:
    name: str
    from_version: str
    to_version: str
    ecosystem: str  # pypi | npm | go
    manifest: str

    @property
    def is_major(self) -> bool:
        def major(v: str) -> int:
            try:
                return int(v.lstrip("v^~>=< ").split(".")[0] or "0")
            except ValueError:
                return 0

        return major(self.from_version) != major(self.to_version)

    def to_signal(self) -> ChangeSignal:
        return ChangeSignal(
            source="lockfile",
            package=self.name,
            change_type="SDK_MAJOR_BUMP" if self.is_major else "DEPENDENCY_BUMP",
            severity="CRITICAL" if self.is_major else "INFO",
            from_version=self.from_version,
            to_version=self.to_version,
            ecosystem=self.ecosystem,
            description=(
                f"{self.name} {self.from_version} -> {self.to_version} "
                f"({self.manifest})"
            ),
            suggested_rules=[
                {
                    "type": "DEPENDENCY_BUMP",
                    "package": self.name,
                    "from_version": self.from_version,
                    "to_version": self.to_version,
                    "ecosystems": (
                        ["pip", "pyproject"]
                        if self.ecosystem == "pypi"
                        else ["npm"]
                        if self.ecosystem == "npm"
                        else []
                    ),
                }
            ],
        )
