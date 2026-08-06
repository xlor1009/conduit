"""LLM self-correction loop after packet apply (tests + production files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conduit.llm import get_llm_client
from conduit.test_runner import TestResult, run_tests


def _paths_from_traceback(root: Path, text: str, limit: int = 12) -> list[Path]:
    import re

    found: list[Path] = []
    for m in re.finditer(r'File "([^"]+)"', text):
        raw = m.group(1)
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        if path.is_file() and str(path.resolve()).startswith(str(root.resolve())):
            if path not in found:
                found.append(path)
        if len(found) >= limit:
            break
    return found


def _collect_context_files(root: Path, test_result: TestResult, limit: int = 12) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in _paths_from_traceback(
        root, (test_result.stdout or "") + "\n" + (test_result.stderr or "")
    ):
        try:
            files[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
        except OSError:
            continue

    candidates = list((root / "tests").rglob("*.py")) if (root / "tests").is_dir() else []
    candidates += list(root.glob("test_*.py"))
    src = root / "src"
    if src.is_dir():
        candidates += list(src.rglob("*.py"))[:20]
    for path in candidates:
        if len(files) >= limit:
            break
        rel = str(path.relative_to(root))
        if rel in files:
            continue
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return files


def _apply_file_updates(root: Path, updates: dict[str, str]) -> list[str]:
    changed: list[str] = []
    root_resolved = root.resolve()
    for rel, content in updates.items():
        path = (root / rel).resolve()
        if not str(path).startswith(str(root_resolved)):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        changed.append(rel)
    return changed


def _heuristic_fix(root: Path, packet: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    replacements: list[tuple[str, str]] = []
    for rule in packet.get("rules") or []:
        if rule.get("type") == "EXACT_STRING_REPLACE":
            replacements.append((rule["match"], rule["replace"]))
        if rule.get("type") == "AST_PARAM_RENAME":
            replacements.append((rule["old_param"], rule["new_param"]))

    targets: list[Path] = []
    if (root / "tests").is_dir():
        targets += list((root / "tests").rglob("*.py"))
    targets += list(root.glob("test_*.py"))
    if (root / "src").is_dir():
        targets += list((root / "src").rglob("*.py"))

    for path in targets:
        try:
            original = path.read_text(encoding="utf-8")
        except OSError:
            continue
        updated = original
        for old, new in replacements:
            if old and old in updated:
                updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(str(path.relative_to(root)))
    return changed


def _llm_suggest_fixes(
    *,
    test_result: TestResult,
    packet: dict[str, Any],
    files: dict[str, str],
) -> dict[str, str]:
    client = get_llm_client()
    if client is None:
        return {}

    prompt = {
        "instructions": (
            "Tests failed after an automatic API migration. "
            "Fix production and/or test files to match the migration packet. "
            'Return JSON: {"files": {"relative/path.py": "full new file contents"}}. '
            "Only include files that need changes."
        ),
        "error_stdout": test_result.stdout[-6000:],
        "error_stderr": test_result.stderr[-6000:],
        "packet": packet,
        "files": files,
    }
    try:
        data = client.complete_json(
            system="You are a careful migration agent. Reply with JSON only.",
            user=json.dumps(prompt),
        )
        files_out = data.get("files") or {}
        return {str(k): str(v) for k, v in files_out.items() if isinstance(v, str)}
    except Exception:
        return {}


def verify_with_self_correct(
    root: Path,
    packet: dict[str, Any],
    *,
    max_retries: int = 5,
) -> tuple[TestResult, list[str]]:
    """Run tests; on failure, LLM/heuristic-fix and retry (default 5)."""
    corrected_files: list[str] = []
    result = run_tests(root)
    if result.passed:
        return result, corrected_files

    for attempt in range(1, max_retries + 1):
        print(f"[self-correct] attempt {attempt}/{max_retries} after test failure")
        context_files = _collect_context_files(root, result)
        updates = _llm_suggest_fixes(
            test_result=result, packet=packet, files=context_files
        )
        if updates:
            corrected_files.extend(_apply_file_updates(root, updates))
        else:
            corrected_files.extend(_heuristic_fix(root, packet))

        result = run_tests(root)
        if result.passed:
            return result, sorted(set(corrected_files))

    return result, sorted(set(corrected_files))
