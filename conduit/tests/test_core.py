"""Conduit unit tests (offline)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from conduit.detect.lockfile_diff import detect_lockfile_jumps, diff_versions
from conduit.detect.modules.discovery import load_modules
from conduit.export_delta.diff import diff_exports
from conduit.export_delta.extract import _python_file_exports
from conduit.llm.client import resolve_provider
from conduit.detect.models import ChangeSignal
from conduit.packet.synthesize import ensure_packet, load_fixture_openai_packet
from conduit.packet.validate import validate_packet
from conduit.main import _resolve_packet_arg
from conduit.patcher import apply_packet
from conduit.patcher.ast_attr_call import rename_python_attr, rewrite_python_call
from conduit.patcher.ast_import_rewrite import rewrite_python_imports
from conduit.prune.grep_imports import prune_by_imports
from conduit.scaffold.module_new import scaffold_module
from conduit.scaffold.packet_init import scaffold_packet
from conduit.test_gen import ensure_tests

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "examples" / "demo-consumer"
SAMPLE_PACKET = REPO / "examples" / "sample-packet" / "conduit-packet.json"


def test_diff_versions_requirements():
    old = "openai==0.28.1\nrequests==2.0.0\n"
    new = "openai==1.0.0\nrequests==2.0.0\n"
    jumps = diff_versions(old, new, filename="requirements.txt")
    assert len(jumps) == 1
    assert jumps[0].name == "openai"
    assert jumps[0].is_major


def test_detect_lockfile_jumps_missing_root(tmp_path: Path):
    """Invalid cwd must not raise (Windows WinError 267)."""
    missing = tmp_path / "does-not-exist"
    assert detect_lockfile_jumps(missing) == []


def test_detect_lockfile_jumps_non_git_dir(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "requirements.txt").write_text("openai==1.0.0\n", encoding="utf-8")
    assert detect_lockfile_jumps(plain) == []


def test_export_delta_placeholder_version(tmp_path: Path):
    from conduit.export_delta import compute_export_delta

    delta = compute_export_delta(
        package="openai",
        from_version="0.0.0",
        to_version="1.0.0",
        ecosystem="pypi",
        cache_root=tmp_path / "exports",
    )
    assert delta.skipped_reason is not None
    assert "openai==0.0.0" in delta.skipped_reason
    assert delta.diagnostics
    assert "placeholder" in delta.diagnostics[0]


def test_resolve_packet_arg_package_name():
    path, pkg = _resolve_packet_arg("openai")
    assert path is None
    assert pkg == "openai"


def test_resolve_packet_arg_file(tmp_path: Path):
    packet_file = tmp_path / "conduit-packet.json"
    packet_file.write_text("{}", encoding="utf-8")
    path, pkg = _resolve_packet_arg(str(packet_file))
    assert path == packet_file.resolve()
    assert pkg is None


def test_ensure_packet_uses_manifest_from_version(tmp_path: Path):
    signals = [
        ChangeSignal(
            source="module:openai",
            package="openai",
            change_type="API_BREAKING",
            suggested_rules=[
                {
                    "type": "DEPENDENCY_BUMP",
                    "package": "openai",
                    "from_version": "0.28.1",
                    "to_version": "1.40.0",
                    "ecosystems": ["pip"],
                }
            ],
        )
    ]
    result = ensure_packet(
        tmp_path,
        signals,
        package="openai",
        installed={"openai": "0.28.1"},
        use_fixture_fallback=False,
    )
    assert result.packet["from_version"] == "0.28.1"
    assert result.from_source == "manifest"
    assert result.packet["to_version"] == "1.40.0"
    assert result.to_source == "rule"
    assert result.warnings == []


def test_ensure_packet_warns_on_placeholder_versions(tmp_path: Path):
    signals = [
        ChangeSignal(
            source="module:acme",
            package="acme",
            change_type="API_BREAKING",
            suggested_rules=[
                {
                    "type": "EXACT_STRING_REPLACE",
                    "match": "old",
                    "replace": "new",
                    "target_files": ["*.py"],
                }
            ],
        )
    ]
    result = ensure_packet(
        tmp_path,
        signals,
        package="acme",
        installed={},
        use_fixture_fallback=False,
    )
    assert result.from_source == "placeholder"
    assert result.to_source == "placeholder"
    assert any("from_version defaulted" in w for w in result.warnings)
    assert any("to_version defaulted" in w for w in result.warnings)


def test_load_modules_includes_openai():
    names = {m.name for m in load_modules()}
    assert "openai" in names


def test_fixture_packet_valid():
    packet = load_fixture_openai_packet()
    assert validate_packet(packet) == []


def test_sample_packet_valid():
    data = json.loads(SAMPLE_PACKET.read_text(encoding="utf-8"))
    assert validate_packet(data) == []


def test_prune_demo_imports_openai():
    files = prune_by_imports(DEMO, ["openai"])
    rels = {str(p.relative_to(DEMO)).replace("\\", "/") for p in files}
    assert any("ai_client.py" in r for r in rels)


def test_apply_packet_dry_run_demo(tmp_path: Path):
    dest = tmp_path / "demo"
    shutil.copytree(DEMO, dest, ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__"))
    packet = json.loads(SAMPLE_PACKET.read_text(encoding="utf-8"))
    files = prune_by_imports(dest, ["openai"])
    report = apply_packet(dest, packet, dry_run=True, file_allowlist=files or None)
    assert report.changes or report.files_modified is not None
    text = (dest / "src" / "ai_client.py").read_text(encoding="utf-8")
    assert "gpt-4-0613" in text


def test_apply_packet_writes_demo(tmp_path: Path):
    dest = tmp_path / "demo"
    shutil.copytree(DEMO, dest, ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__"))
    packet = json.loads(SAMPLE_PACKET.read_text(encoding="utf-8"))
    files = prune_by_imports(dest, ["openai"])
    report = apply_packet(dest, packet, dry_run=False, file_allowlist=files or None)
    text = (dest / "src" / "ai_client.py").read_text(encoding="utf-8")
    assert "gpt-4o" in text
    assert "max_completion_tokens" in text
    assert report.files_modified


def test_scaffold_packet(tmp_path: Path):
    path = scaffold_packet(
        package="stripe",
        ecosystem="pypi",
        from_version="1.0.0",
        to_version="2.0.0",
        out_dir=tmp_path / "stripe-packet",
    )
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["package"] == "stripe"
    assert validate_packet(data) == []


def test_scaffold_module(tmp_path: Path):
    (tmp_path / "src" / "conduit" / "detect" / "modules").mkdir(parents=True)
    mod_dir = scaffold_module("acme", package="acme", target_root=tmp_path)
    assert (mod_dir / "__init__.py").is_file()


def test_resolve_provider_openai(monkeypatch):
    monkeypatch.delenv("CONDUIT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CONDUIT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert resolve_provider() == "openai"


def test_resolve_provider_anthropic(monkeypatch):
    monkeypatch.delenv("CONDUIT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CONDUIT_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    assert resolve_provider() == "anthropic"


def test_resolve_provider_explicit_ollama(monkeypatch):
    monkeypatch.setenv("CONDUIT_LLM_PROVIDER", "ollama")
    assert resolve_provider() == "ollama"


def test_resolve_provider_explicit_custom(monkeypatch):
    monkeypatch.setenv("CONDUIT_LLM_PROVIDER", "custom")
    assert resolve_provider() == "custom"


def test_resolve_provider_legacy_alias(monkeypatch):
    monkeypatch.setenv("CONDUIT_LLM_PROVIDER", "openai_compatible")
    assert resolve_provider() == "custom"


def test_diff_exports_rename_case():
    added, removed, renamed = diff_exports({"FooBar"}, {"foobar"})
    assert renamed.get("FooBar") == "foobar"
    assert not added
    assert not removed


def test_python_file_exports_all():
    src = '__all__ = ["Client", "util"]\n\ndef helper():\n    pass\n'
    syms = _python_file_exports(src)
    assert "Client" in syms
    assert "util" in syms
    assert "helper" in syms


def test_rewrite_python_imports():
    src = "from openai import OpenAI\n"
    out, n = rewrite_python_imports(src, "openai", "openai_v1")
    assert n >= 1
    assert "openai_v1" in out


def test_rename_python_attr_and_call():
    src = "x = openai.ChatCompletion.create()\n"
    out, n = rename_python_attr(src, "openai.ChatCompletion", "openai.chat.completions")
    assert n >= 1
    assert "chat.completions" in out
    src2 = "openai.ChatCompletion.create()\n"
    out2, n2 = rewrite_python_call(
        src2, "openai.ChatCompletion.create", "openai.chat.completions.create"
    )
    assert n2 >= 1


def test_ensure_tests_creates_stub(tmp_path: Path, monkeypatch):
    packet = {
        "package": "demo",
        "ecosystem": "pypi",
        "from_version": "1.0.0",
        "to_version": "2.0.0",
        "rules": [],
    }
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CONDUIT_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("CONDUIT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("CONDUIT_LLM_BASE_URL", raising=False)
    created = ensure_tests(tmp_path, packet)
    assert created
    assert (tmp_path / created[0]).is_file()


def test_attr_rename_rule_in_packet(tmp_path: Path):
    src = tmp_path / "mod.py"
    src.write_text("import openai\nx = openai.ChatCompletion\n", encoding="utf-8")
    packet = {
        "packet_id": "t",
        "package": "openai",
        "ecosystem": "pypi",
        "from_version": "0",
        "to_version": "1",
        "rules": [
            {
                "type": "AST_ATTR_RENAME",
                "target_files": ["*.py"],
                "old_attr": "openai.ChatCompletion",
                "new_attr": "openai.chat.completions",
            }
        ],
    }
    assert validate_packet(packet) == []
    report = apply_packet(tmp_path, packet, dry_run=False, require_context=False)
    text = src.read_text(encoding="utf-8")
    assert "chat.completions" in text
    assert report.files_modified
