"""Typer CLI entrypoints for vendor-patch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from vendor_patch_cli.patcher import apply_events
from vendor_patch_cli.pr_generator import open_pull_request
from vendor_patch_cli.registry_client import DEFAULT_REGISTRY_URL, filter_events, load_registry
from vendor_patch_cli.scanner import scan_path
from vendor_patch_cli.self_correct import verify_with_self_correct

app = typer.Typer(
    name="vendor-patch",
    help="Scan, patch, verify, and PR vendor API deprecations from registry.json",
    add_completion=False,
    invoke_without_command=False,
)
console = Console()


def _resolve_root(path: Path) -> Path:
    return path.expanduser().resolve()


def _default_local_registry() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "vendor-signal-registry"
        / "dist"
        / "registry.json"
    )


def _load(
    registry_url: Optional[str],
    custom_endpoint: Optional[str],
) -> dict:
    return load_registry(
        registry_url=registry_url,
        custom_endpoint=custom_endpoint,
        local_fallback=_default_local_registry(),
    )


@app.command("scan")
def scan_cmd(
    path: Path = typer.Option(Path("."), "--path", help="Repository root to scan"),
    registry_url: Optional[str] = typer.Option(
        None, "--registry-url", help="Approach A registry.json URL or local path"
    ),
    custom_endpoint: Optional[str] = typer.Option(
        None,
        "--custom-endpoint",
        help="Approach B: bypass central registry and query this endpoint",
    ),
    vendor: Optional[str] = typer.Option(None, "--vendor"),
    event_id: Optional[str] = typer.Option(None, "--event-id"),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Download registry.json and report matches without modifying files."""
    root = _resolve_root(path)
    registry = _load(registry_url, custom_endpoint)
    events = filter_events(registry, vendor=vendor, event_id=event_id)
    result = scan_path(root, events)

    if json_out:
        payload = [
            {
                "event_id": m.event_id,
                "vendor": m.vendor,
                "path": str(m.path),
                "line": m.line,
                "column": m.column,
                "pattern": m.pattern,
                "rule_type": m.rule_type,
                "snippet": m.snippet,
            }
            for m in result.matches
        ]
        console.print_json(json.dumps(payload))
        raise typer.Exit(0 if result.matches else 1)

    table = Table(title=f"Vendor signal matches in {root}")
    table.add_column("Event")
    table.add_column("File")
    table.add_column("Line")
    table.add_column("Pattern")
    for m in result.matches:
        table.add_row(
            m.event_id,
            str(m.path.relative_to(root)),
            str(m.line),
            m.pattern,
        )
    console.print(table)
    console.print(
        f"[bold]{len(result.matches)}[/bold] match(es) across "
        f"{len(result.files)} file(s); "
        f"{len(result.events_with_hits)} event(s) applicable."
    )
    if not result.matches:
        raise typer.Exit(1)


@app.command("apply")
def apply_cmd(
    path: Path = typer.Option(Path("."), "--path"),
    registry_url: Optional[str] = typer.Option(None, "--registry-url"),
    custom_endpoint: Optional[str] = typer.Option(None, "--custom-endpoint"),
    vendor: Optional[str] = typer.Option(None, "--vendor"),
    event_id: Optional[str] = typer.Option(None, "--event-id"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    all_events: bool = typer.Option(
        False,
        "--all-events",
        help="Apply all matching events (default: only events with scan hits)",
    ),
) -> None:
    """Apply codemods / string replacements for matching registry events."""
    root = _resolve_root(path)
    registry = _load(registry_url, custom_endpoint)
    events = filter_events(registry, vendor=vendor, event_id=event_id)
    scan = scan_path(root, events)
    targets = events if all_events else (scan.events_with_hits or events)
    if not targets:
        console.print("[yellow]No applicable events found.[/yellow]")
        raise typer.Exit(1)

    report = apply_events(root, targets, dry_run=dry_run)
    for change in report.changes:
        prefix = "DRY-RUN " if dry_run else ""
        console.print(f"{prefix}[{change.rule_type}] {change.path}: {change.detail}")
    console.print(
        f"{'Would modify' if dry_run else 'Modified'} "
        f"{len(report.files_modified)} file(s)."
    )


@app.command("run")
def run_cmd(
    path: Path = typer.Option(Path("."), "--path"),
    registry_url: Optional[str] = typer.Option(
        None,
        "--registry-url",
        help=f"Default: {DEFAULT_REGISTRY_URL} (falls back to monorepo dist)",
    ),
    custom_endpoint: Optional[str] = typer.Option(None, "--custom-endpoint"),
    vendor: Optional[str] = typer.Option("openai", "--vendor"),
    event_id: Optional[str] = typer.Option(None, "--event-id"),
    skip_tests: bool = typer.Option(False, "--skip-tests"),
    skip_pr: bool = typer.Option(False, "--skip-pr"),
    no_push: bool = typer.Option(False, "--no-push"),
    include_deps: bool = typer.Option(
        False,
        "--include-deps",
        help="Also apply SDK_MAJOR_BUMP / DEPENDENCY_BUMP rules",
    ),
    max_retries: int = typer.Option(3, "--max-retries"),
) -> None:
    """Full pipeline: scan -> apply -> test (+ self-correct) -> PR."""
    root = _resolve_root(path)
    registry = _load(registry_url, custom_endpoint)
    events = filter_events(registry, vendor=vendor, event_id=event_id)
    scan = scan_path(root, events)
    targets = list(scan.events_with_hits)
    if not include_deps:
        targets = [
            e
            for e in targets
            if e.get("change_type") != "SDK_MAJOR_BUMP"
        ]

    if not targets:
        console.print("[green]No deprecated patterns found. Nothing to do.[/green]")
        raise typer.Exit(0)

    console.print(f"Applying {len(targets)} event(s)...")
    # When include_deps is false, strip DEPENDENCY_BUMP rules from remaining events
    apply_targets = targets
    if not include_deps:
        apply_targets = []
        for event in targets:
            rules = [
                r
                for r in (event.get("rules") or [])
                if r.get("type") != "DEPENDENCY_BUMP"
            ]
            cloned = dict(event)
            cloned["rules"] = rules
            apply_targets.append(cloned)

    report = apply_events(root, apply_targets, dry_run=False)
    for change in report.changes:
        console.print(f"[{change.rule_type}] {change.path}: {change.detail}")

    if skip_tests:
        from vendor_patch_cli.test_runner import TestResult

        test_result = TestResult(
            runner="skipped",
            passed=True,
            returncode=0,
            stdout="skipped",
            stderr="",
            command=[],
        )
        corrected: list[str] = []
    else:
        test_result, corrected = verify_with_self_correct(
            root, targets, max_retries=max_retries
        )
        for rel in corrected:
            console.print(f"[self-correct] updated {rel}")
            if rel not in report.files_modified:
                report.files_modified.append(rel)

    console.print(test_result.summary)
    if not test_result.passed:
        console.print("[red]Tests still failing after self-correction; aborting PR.[/red]")
        if test_result.stdout:
            console.print(test_result.stdout[-2000:])
        if test_result.stderr:
            console.print(test_result.stderr[-2000:])
        raise typer.Exit(2)

    if skip_pr:
        console.print("[green]Patches applied and tests passed (PR skipped).[/green]")
        raise typer.Exit(0)

    pr = open_pull_request(
        root,
        targets,
        report,
        test_result,
        push=not no_push,
        create_pr=True,
    )
    console.print(pr.message)
    raise typer.Exit(0 if pr.created or skip_pr else 3)


if __name__ == "__main__":
    app()
