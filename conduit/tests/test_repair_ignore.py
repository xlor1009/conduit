"""Tests for dynamic repair ignore lists."""

from __future__ import annotations

from pathlib import Path

from conduit.repair_ignore import (
    build_ignore_list,
    exact_replace_respecting_ignore,
    line_is_contract_assignment,
)
from conduit.self_correct import _heuristic_fix


def test_discover_policy_file_ignored(tmp_path: Path):
    src = tmp_path / "src" / "app"
    src.mkdir(parents=True)
    (src / "policy.py").write_text(
        'LEGACY_CHAT_PARAM = "max_tokens"\nFORBIDDEN_ENDPOINTS = {"/v1/engines"}\n',
        encoding="utf-8",
    )
    (src / "chat.py").write_text(
        'def f():\n    return {"max_tokens": 64}\n',
        encoding="utf-8",
    )
    packet = {
        "rules": [
            {
                "type": "EXACT_STRING_REPLACE",
                "match": "max_tokens",
                "replace": "max_completion_tokens",
                "target_files": ["*.py"],
            }
        ]
    }
    ignore = build_ignore_list(tmp_path, packet)
    assert ignore.path_ignored("src/app/policy.py")
    assert not ignore.path_ignored("src/app/chat.py")


def test_heuristic_skips_ignored_policy_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    policy = src / "policy.py"
    policy.write_text('LEGACY_CHAT_PARAM = "max_tokens"\n', encoding="utf-8")
    chat = src / "chat.py"
    chat.write_text('x = "max_tokens"\n', encoding="utf-8")
    packet = {
        "rules": [
            {
                "type": "EXACT_STRING_REPLACE",
                "match": "max_tokens",
                "replace": "max_completion_tokens",
                "target_files": ["*.py"],
            }
        ],
        "ignore": {"paths": ["src/policy.py"]},
    }
    fix = _heuristic_fix(tmp_path, packet, ignore=build_ignore_list(tmp_path, packet))
    assert "src/chat.py" in fix.files or any("chat.py" in f for f in fix.files)
    assert "max_tokens" in policy.read_text(encoding="utf-8")
    assert "max_completion_tokens" in chat.read_text(encoding="utf-8")


def test_contract_line_spared_inside_mixed_file():
    content = (
        'LEGACY_CHAT_PARAM = "max_tokens"\n'
        'payload = {"max_tokens": 64}\n'
    )
    out, n = exact_replace_respecting_ignore(
        content,
        "max_tokens",
        "max_completion_tokens",
        ignored_patterns={"max_tokens"},
    )
    assert n == 1
    assert 'LEGACY_CHAT_PARAM = "max_tokens"' in out
    assert '"max_completion_tokens"' in out
    assert line_is_contract_assignment('LEGACY_CHAT_PARAM = "max_tokens"', "max_tokens")


def test_conduit_ignore_json(tmp_path: Path):
    (tmp_path / ".conduit").mkdir()
    (tmp_path / ".conduit" / "ignore.json").write_text(
        '{"globs": ["**/oracle.py"]}',
        encoding="utf-8",
    )
    (tmp_path / "oracle.py").write_text("x = 1\n", encoding="utf-8")
    ignore = build_ignore_list(tmp_path, {"rules": []})
    assert ignore.path_ignored("oracle.py")
