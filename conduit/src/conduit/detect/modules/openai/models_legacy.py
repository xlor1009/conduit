"""Typed models for raw worker signals and normalized registry events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ChangeType(str, Enum):
    MODEL_DEPRECATION = "MODEL_DEPRECATION"
    MODEL_REMOVED = "MODEL_REMOVED"
    API_BREAKING = "API_BREAKING"
    PARAM_RENAME = "PARAM_RENAME"
    SDK_MAJOR_BUMP = "SDK_MAJOR_BUMP"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class RawSignal:
    """Intermediate signal emitted by an ingestion worker."""

    vendor: str
    change_type: ChangeType
    severity: Severity
    affected_pattern: str
    replacement_pattern: str | None = None
    deadline: str | None = None
    source_url: str | None = None
    description: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    suggested_rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RegistryEvent:
    event_id: str
    vendor: str
    change_type: str
    severity: str
    affected_pattern: str
    rules: list[dict[str, Any]]
    replacement_pattern: str | None = None
    deadline: str | None = None
    source_url: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class RegistryDocument:
    generated_at: str
    version: str
    events: list[RegistryEvent]
    schema_url: str = (
        "https://raw.githubusercontent.com/your-org/vendor-signals/main/schema.json"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": self.schema_url,
            "generated_at": self.generated_at,
            "version": self.version,
            "events": [e.to_dict() for e in self.events],
        }
