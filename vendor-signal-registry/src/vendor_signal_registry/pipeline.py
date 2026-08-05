"""Run all ingestion workers, validate, and write registry.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from vendor_signal_registry.normalize import merge_signals
from vendor_signal_registry.schema_validate import assert_valid
from vendor_signal_registry.workers import ALL_WORKERS
from vendor_signal_registry.workers.base import package_root


def run_pipeline(*, output: Path | None = None, version: str = "1.0.0") -> Path:
    signals = []
    for worker_cls in ALL_WORKERS:
        worker = worker_cls()
        print(f"[pipeline] running {worker.name}...")
        try:
            batch = worker.run()
        except Exception as exc:  # noqa: BLE001 — isolate worker failures
            print(f"[pipeline] {worker.name} failed: {exc}", file=sys.stderr)
            continue
        print(f"[pipeline] {worker.name} emitted {len(batch)} signal(s)")
        signals.extend(batch)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    document = merge_signals(signals, generated_at=generated_at, version=version)
    payload = document.to_dict()
    assert_valid(payload)

    out_path = output or (package_root() / "dist" / "registry.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # Also mirror to docs/ for GitHub Pages static hosting
    docs_path = package_root() / "docs" / "registry.json"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"[pipeline] wrote {out_path} ({len(document.events)} events)")
    print(f"[pipeline] mirrored {docs_path}")
    return out_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="vendor-signals",
        description="Build the unified vendor signal registry.json",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="build",
        choices=["build"],
        help="Pipeline command (default: build)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path for registry.json",
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Registry document version",
    )
    args = parser.parse_args(argv)
    if args.command == "build":
        run_pipeline(output=args.output, version=args.version)


if __name__ == "__main__":
    main()
