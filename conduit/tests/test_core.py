"""Conduit unit tests (offline)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from conduit.detect.lockfile_diff import diff_versions
from conduit.detect.modules.discovery import load_modules
from conduit.packet.synthesize import load_fixture_openai_packet
from conduit.packet.validate import validate_packet
from conduit.patcher import apply_packet
from conduit.prune.grep_imports import prune_by_imports
from conduit.scaffold.module_new import scaffold_module
from conduit.scaffold.packet_init import scaffold_packet

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
    # dry-run should not rewrite files
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
    # minimal package layout
    (tmp_path / "src" / "conduit" / "detect" / "modules").mkdir(parents=True)
    mod_dir = scaffold_module("acme", package="acme", target_root=tmp_path)
    assert (mod_dir / "__init__.py").is_file()
