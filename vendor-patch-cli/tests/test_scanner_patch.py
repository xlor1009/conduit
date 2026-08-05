"""CLI unit tests (offline against monorepo registry artifact)."""

from __future__ import annotations

from pathlib import Path

from vendor_patch_cli.patcher import apply_events
from vendor_patch_cli.registry_client import filter_events, load_registry
from vendor_patch_cli.scanner import scan_path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "vendor-signal-registry" / "dist" / "registry.json"
DEMO = ROOT / "examples" / "demo-consumer"


def test_load_local_registry():
    registry = load_registry(registry_url=str(REGISTRY))
    assert "events" in registry
    assert len(registry["events"]) >= 1


def test_scan_demo_consumer():
    registry = load_registry(registry_url=str(REGISTRY))
    events = filter_events(registry, vendor="openai")
    result = scan_path(DEMO, events)
    patterns = {m.pattern for m in result.matches}
    assert "gpt-4-0613" in patterns or any("gpt-4-0613" in p for p in patterns)


def test_apply_dry_run_demo(tmp_path: Path):
    # Copy demo sources into temp dir
    src = DEMO / "src" / "ai_client.py"
    target = tmp_path / "src"
    target.mkdir()
    dest = target / "ai_client.py"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    registry = load_registry(registry_url=str(REGISTRY))
    events = [
        e
        for e in filter_events(registry, vendor="openai")
        if e.get("affected_pattern") == "gpt-4-0613"
        or any(
            r.get("type") == "AST_PARAM_RENAME" and r.get("old_param") == "max_tokens"
            for r in e.get("rules") or []
        )
    ]
    # Prefer deprecation + param rename events
    report = apply_events(tmp_path, events, dry_run=False, require_context=True)
    text = dest.read_text(encoding="utf-8")
    assert "gpt-4o" in text or "max_completion_tokens" in text or report.files_modified
