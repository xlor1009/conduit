"""Normalize raw worker signals into unified registry events with rules."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from vendor_signal_registry.models import (
    ChangeType,
    RawSignal,
    RegistryDocument,
    RegistryEvent,
    Severity,
)

DEFAULT_CODE_GLOBS = ["*.py", "*.ts", "*.js", "*.yaml", "*.yml", "*.json", ".env*"]
AST_GLOBS = ["*.py", "*.ts", "*.js"]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned[:48] or "item"


def make_event_id(signal: RawSignal) -> str:
    base = (
        f"evt_{_slug(signal.vendor)}_{_slug(signal.change_type.value)}_"
        f"{_slug(signal.affected_pattern)}"
    )
    digest = hashlib.sha1(
        f"{signal.vendor}|{signal.change_type.value}|{signal.affected_pattern}|"
        f"{signal.replacement_pattern}|{signal.deadline}".encode()
    ).hexdigest()[:6]
    return f"{base}_{digest}"


def default_rules_for(signal: RawSignal) -> list[dict[str, Any]]:
    if signal.suggested_rules:
        return list(signal.suggested_rules)

    rules: list[dict[str, Any]] = []

    # Model ID / literal migrations only — never string-replace package names
    if signal.change_type in {
        ChangeType.MODEL_DEPRECATION,
        ChangeType.MODEL_REMOVED,
    }:
        if signal.replacement_pattern and signal.affected_pattern:
            rules.append(
                {
                    "type": "EXACT_STRING_REPLACE",
                    "target_files": list(DEFAULT_CODE_GLOBS),
                    "match": signal.affected_pattern,
                    "replace": signal.replacement_pattern,
                }
            )

    if signal.change_type == ChangeType.PARAM_RENAME:
        old_param = signal.extra.get("old_param") or signal.affected_pattern
        new_param = signal.extra.get("new_param") or signal.replacement_pattern
        function_target = signal.extra.get(
            "function_target", "openai.chat.completions.create"
        )
        if old_param and new_param:
            rules.append(
                {
                    "type": "AST_PARAM_RENAME",
                    "target_files": list(AST_GLOBS),
                    "function_target": function_target,
                    "old_param": old_param,
                    "new_param": new_param,
                }
            )

    if signal.change_type == ChangeType.SDK_MAJOR_BUMP:
        package = signal.extra.get("package", signal.affected_pattern)
        from_version = signal.extra.get("from_version", "0.0.0")
        to_version = signal.extra.get("to_version") or signal.replacement_pattern or "1.0.0"
        rules.append(
            {
                "type": "DEPENDENCY_BUMP",
                "package": package,
                "from_version": from_version,
                "to_version": to_version,
                "ecosystems": signal.extra.get("ecosystems", ["pip", "npm", "pyproject"]),
            }
        )

    if signal.change_type == ChangeType.API_BREAKING:
        # Informational by default; workers may attach suggested_rules for renames
        pass

    return rules


def signal_to_event(signal: RawSignal) -> RegistryEvent:
    return RegistryEvent(
        event_id=make_event_id(signal),
        vendor=signal.vendor,
        change_type=signal.change_type.value,
        severity=signal.severity.value
        if isinstance(signal.severity, Severity)
        else str(signal.severity),
        affected_pattern=signal.affected_pattern,
        replacement_pattern=signal.replacement_pattern,
        deadline=signal.deadline,
        source_url=signal.source_url,
        description=signal.description,
        rules=default_rules_for(signal),
    )


def merge_signals(
    signals: list[RawSignal],
    *,
    generated_at: str,
    version: str = "1.0.0",
) -> RegistryDocument:
    events: list[RegistryEvent] = []
    seen: set[str] = set()
    for signal in signals:
        event = signal_to_event(signal)
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        events.append(event)

    events.sort(key=lambda e: (e.vendor, e.change_type, e.event_id))
    return RegistryDocument(
        generated_at=generated_at,
        version=version,
        events=events,
    )
