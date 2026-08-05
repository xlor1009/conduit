"""LLM self-correction loop for failing tests after patches."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from vendor_patch_cli.test_runner import TestResult, run_tests


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _collect_test_files(root: Path, limit: int = 8) -> dict[str, str]:
    files: dict[str, str] = {}
    candidates = list((root / "tests").rglob("*.py")) if (root / "tests").is_dir() else []
    candidates += list(root.glob("test_*.py"))
    for path in candidates[:limit]:
        try:
            files[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return files


def _apply_file_updates(root: Path, updates: dict[str, str]) -> list[str]:
    changed: list[str] = []
    for rel, content in updates.items():
        path = (root / rel).resolve()
        if not str(path).startswith(str(root.resolve())):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        changed.append(rel)
    return changed


def _heuristic_fix_tests(root: Path, events: list[dict[str, Any]]) -> list[str]:
    """
    Offline fallback: apply simple string replacements from events to test files
    so demos work without an API key when tests assert old model IDs.
    """
    changed: list[str] = []
    replacements: list[tuple[str, str]] = []
    for event in events:
        old = event.get("affected_pattern")
        new = event.get("replacement_pattern")
        if old and new:
            replacements.append((old, new))
        for rule in event.get("rules") or []:
            if rule.get("type") == "EXACT_STRING_REPLACE":
                replacements.append((rule["match"], rule["replace"]))
            if rule.get("type") == "AST_PARAM_RENAME":
                replacements.append((rule["old_param"], rule["new_param"]))

    test_files = list((root / "tests").rglob("*.py")) if (root / "tests").is_dir() else []
    test_files += list(root.glob("test_*.py"))
    for path in test_files:
        original = path.read_text(encoding="utf-8")
        updated = original
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(str(path.relative_to(root)))
    return changed


def _llm_suggest_fixes(
    *,
    test_result: TestResult,
    events: list[dict[str, Any]],
    test_files: dict[str, str],
) -> dict[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {}
    try:
        from openai import OpenAI
    except ImportError:
        return {}

    client = OpenAI(api_key=api_key)
    prompt = {
        "instructions": (
            "Tests failed after an automatic API migration patch. "
            "Update test mocks/fixtures/assertions to match the new API. "
            "Return JSON: {\"files\": {\"relative/path.py\": \"full new file contents\"}}. "
            "Only include files that need changes."
        ),
        "error_stdout": test_result.stdout[-6000:],
        "error_stderr": test_result.stderr[-6000:],
        "migration_events": events,
        "test_files": test_files,
    }
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful test-migration agent. Reply with JSON only.",
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = resp.choices[0].message.content or "{}"
        data = _extract_json_object(content) or {}
        files = data.get("files") or {}
        return {str(k): str(v) for k, v in files.items() if isinstance(v, str)}
    except Exception:
        return {}


def verify_with_self_correct(
    root: Path,
    events: list[dict[str, Any]],
    *,
    max_retries: int = 3,
) -> tuple[TestResult, list[str]]:
    """
    Run tests; on failure, ask an LLM (or heuristic fallback) to fix tests and retry.
    Returns final TestResult and list of files modified during self-correction.
    """
    corrected_files: list[str] = []
    result = run_tests(root)
    if result.passed:
        return result, corrected_files

    for attempt in range(1, max_retries + 1):
        print(f"[self-correct] attempt {attempt}/{max_retries} after test failure")
        test_files = _collect_test_files(root)
        updates = _llm_suggest_fixes(
            test_result=result, events=events, test_files=test_files
        )
        if updates:
            corrected_files.extend(_apply_file_updates(root, updates))
        else:
            # Offline / no-key path
            corrected_files.extend(_heuristic_fix_tests(root, events))

        result = run_tests(root)
        if result.passed:
            return result, sorted(set(corrected_files))

    return result, sorted(set(corrected_files))
