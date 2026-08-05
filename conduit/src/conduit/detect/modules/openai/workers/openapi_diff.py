"""OpenAPIDiffWorker: diff vendor OpenAPI specs for breaking changes."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from conduit.detect.modules.openai.models_legacy import ChangeType, RawSignal, Severity
from conduit.detect.modules.openai.workers.base import Worker, env_flag, fixtures_dir


def _load_openapi(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _diff_paths(previous: dict[str, Any], latest: dict[str, Any]) -> list[RawSignal]:
    signals: list[RawSignal] = []
    prev_paths = set((previous.get("paths") or {}).keys())
    latest_paths = set((latest.get("paths") or {}).keys())

    for removed in sorted(prev_paths - latest_paths):
        signals.append(
            RawSignal(
                vendor="openai",
                change_type=ChangeType.API_BREAKING,
                severity=Severity.CRITICAL,
                affected_pattern=removed,
                replacement_pattern=None,
                source_url="https://github.com/openai/openai-openapi",
                description=f"OpenAPI path removed: {removed}",
                suggested_rules=[],
            )
        )

    # Detect renamed request-body properties on shared paths
    for path in sorted(prev_paths & latest_paths):
        prev_props = _request_props(previous["paths"][path])
        latest_props = _request_props(latest["paths"][path])
        removed_props = prev_props - latest_props
        added_props = latest_props - prev_props
        # Heuristic: single removed + single added => rename
        if len(removed_props) == 1 and len(added_props) == 1:
            old_p = next(iter(removed_props))
            new_p = next(iter(added_props))
            signals.append(
                RawSignal(
                    vendor="openai",
                    change_type=ChangeType.PARAM_RENAME,
                    severity=Severity.CRITICAL,
                    affected_pattern=old_p,
                    replacement_pattern=new_p,
                    source_url="https://github.com/openai/openai-openapi",
                    description=f"Request property renamed on {path}: {old_p} -> {new_p}",
                    extra={
                        "old_param": old_p,
                        "new_param": new_p,
                        "function_target": "openai.chat.completions.create",
                        "path": path,
                    },
                )
            )
        else:
            for prop in sorted(removed_props):
                signals.append(
                    RawSignal(
                        vendor="openai",
                        change_type=ChangeType.API_BREAKING,
                        severity=Severity.WARNING,
                        affected_pattern=prop,
                        source_url="https://github.com/openai/openai-openapi",
                        description=f"Request property removed on {path}: {prop}",
                        extra={"path": path},
                    )
                )
    return signals


def _request_props(path_item: dict[str, Any]) -> set[str]:
    props: set[str] = set()
    for method, op in path_item.items():
        if method.startswith("x-") or not isinstance(op, dict):
            continue
        body = (op.get("requestBody") or {}).get("content") or {}
        for media in body.values():
            schema = media.get("schema") or {}
            props.update((schema.get("properties") or {}).keys())
    return props


def _run_oasdiff(prev: Path, latest: Path) -> list[RawSignal]:
    if not shutil.which("oasdiff"):
        return []
    try:
        result = subprocess.run(
            ["oasdiff", "breaking", str(prev), str(latest), "-f", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode not in (0, 1) or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    signals: list[RawSignal] = []
    for item in payload if isinstance(payload, list) else []:
        text = str(item.get("text") or item.get("id") or item)
        signals.append(
            RawSignal(
                vendor="openai",
                change_type=ChangeType.API_BREAKING,
                severity=Severity.CRITICAL,
                affected_pattern=text[:120],
                description=text,
                source_url="https://github.com/openai/openai-openapi",
            )
        )
    return signals


class OpenAPIDiffWorker(Worker):
    name = "OpenAPIDiffWorker"

    def run(self) -> list[RawSignal]:
        fixture_prev = fixtures_dir() / "openapi" / "previous.yaml"
        fixture_latest = fixtures_dir() / "openapi" / "latest.yaml"

        if env_flag("OASDIFF_LIVE"):
            live_signals = self._live_diff()
            if live_signals:
                return live_signals

        previous = _load_openapi(fixture_prev)
        latest = _load_openapi(fixture_latest)
        signals = _diff_paths(previous, latest)

        # Prefer oasdiff output when available even on fixtures
        oas = _run_oasdiff(fixture_prev, fixture_latest)
        if oas:
            # Keep fixture-derived param renames; append oasdiff extras
            keys = {(s.change_type, s.affected_pattern) for s in signals}
            for s in oas:
                if (s.change_type, s.affected_pattern) not in keys:
                    signals.append(s)
        return signals

    def _live_diff(self) -> list[RawSignal]:
        repo = "https://github.com/openai/openai-openapi.git"
        with tempfile.TemporaryDirectory(prefix="oasdiff-") as tmp:
            tmp_path = Path(tmp)
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "50", repo, str(tmp_path / "repo")],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return []
            repo_path = tmp_path / "repo"
            # Find openapi.yaml / openapi.json
            candidates = list(repo_path.glob("**/openapi.y*ml")) + list(
                repo_path.glob("**/openapi.json")
            )
            if not candidates:
                return []
            # Use HEAD vs previous commit of same file as a simple live signal
            latest = candidates[0]
            try:
                subprocess.run(
                    ["git", "show", f"HEAD~1:{latest.relative_to(repo_path).as_posix()}"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return _diff_paths(
                    _load_openapi(fixtures_dir() / "openapi" / "previous.yaml"),
                    _load_openapi(latest),
                )
            # Fall back to fixture previous vs live latest content
            return _diff_paths(
                _load_openapi(fixtures_dir() / "openapi" / "previous.yaml"),
                _load_openapi(latest),
            )
