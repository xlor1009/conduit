"""Registry normalize / validate smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

from vendor_signal_registry.normalize import merge_signals, signal_to_event
from vendor_signal_registry.models import ChangeType, RawSignal, Severity
from vendor_signal_registry.schema_validate import assert_valid
from vendor_signal_registry.workers import ALL_WORKERS

ROOT = Path(__file__).resolve().parents[1]


def test_seeded_registry_validates():
    path = ROOT / "dist" / "registry.json"
    assert_valid(json.loads(path.read_text(encoding="utf-8")))


def test_workers_emit_signals():
    total = 0
    for cls in ALL_WORKERS:
        batch = cls().run()
        assert isinstance(batch, list)
        total += len(batch)
    assert total >= 5


def test_model_deprecation_gets_string_rule():
    signal = RawSignal(
        vendor="openai",
        change_type=ChangeType.MODEL_DEPRECATION,
        severity=Severity.CRITICAL,
        affected_pattern="gpt-4-0613",
        replacement_pattern="gpt-4o",
        deadline="2026-10-23T00:00:00Z",
    )
    event = signal_to_event(signal)
    types = [r["type"] for r in event.rules]
    assert "EXACT_STRING_REPLACE" in types


def test_sdk_bump_does_not_string_replace_package():
    signal = RawSignal(
        vendor="openai",
        change_type=ChangeType.SDK_MAJOR_BUMP,
        severity=Severity.CRITICAL,
        affected_pattern="openai",
        replacement_pattern="1.40.0",
        extra={
            "package": "openai",
            "from_version": "0.28.1",
            "to_version": "1.40.0",
            "ecosystems": ["pip"],
        },
    )
    event = signal_to_event(signal)
    assert all(r["type"] != "EXACT_STRING_REPLACE" for r in event.rules)
    assert any(r["type"] == "DEPENDENCY_BUMP" for r in event.rules)


def test_merge_dedupes():
    signal = RawSignal(
        vendor="openai",
        change_type=ChangeType.MODEL_DEPRECATION,
        severity=Severity.CRITICAL,
        affected_pattern="gpt-4-0613",
        replacement_pattern="gpt-4o",
    )
    doc = merge_signals([signal, signal], generated_at="2026-08-04T12:00:00Z")
    assert len(doc.events) == 1
