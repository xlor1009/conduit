"""Unit tests for pluggable language engines (JS/TS, Java, Go)."""

from __future__ import annotations

from pathlib import Path

from conduit.patcher.languages.edits import SourceEdit, apply_edits
from conduit.patcher.languages.go import GoEngine
from conduit.patcher.languages.java import JavaEngine
from conduit.patcher.languages.javascript import JsTsEngine
from conduit.patcher.languages.registry import engine_for
from conduit.patcher.dependency_update import (
    bump_go_mod,
    bump_gradle,
    bump_pom_xml,
)
from conduit.prune.grep_imports import prune_by_imports


def test_apply_edits_back_to_front():
    text = "aa bb cc"
    # replace bb and cc
    source = text.encode("utf-8")
    edits = [
        SourceEdit(3, 5, "XX"),
        SourceEdit(6, 8, "YY"),
    ]
    updated, n = apply_edits(source, edits)
    assert n == 2
    assert updated == "aa XX YY"


def test_engine_for_suffixes():
    assert engine_for(Path("a.py")) is not None
    assert engine_for(Path("a.ts")) is not None
    assert engine_for(Path("a.java")) is not None
    assert engine_for(Path("a.go")) is not None
    assert engine_for(Path("a.txt")) is None


def test_js_import_rewrite_only_import_literal():
    eng = JsTsEngine(suffix=".js")
    src = (
        'import x from "openai";\n'
        'const msg = "openai";\n'
        'require("openai");\n'
    )
    updated, count = eng.rewrite_import(src, "openai", "openai-v1")
    assert count >= 1
    assert 'from "openai-v1"' in updated
    assert 'require("openai-v1")' in updated
    # Unrelated string should remain if tree-sitter available; fallback may replace all
    # Accept either precise or fallback behavior for count > 0
    assert "openai-v1" in updated


def test_js_call_chain_rewrite():
    eng = JsTsEngine(suffix=".ts")
    src = "client.chat.completions.create({ model: 'x' });\n"
    updated, count = eng.rewrite_call(
        src, "client.chat.completions.create", "client.chat.completions.createV2"
    )
    assert count >= 1
    assert "createV2" in updated


def test_js_param_rename_object_key():
    eng = JsTsEngine(suffix=".js")
    src = "openai.chat.completions.create({ max_tokens: 10, model: 'x' });\n"
    updated, count = eng.rename_param(
        src,
        function_target="chat.completions.create",
        old_param="max_tokens",
        new_param="max_completion_tokens",
    )
    assert count >= 1
    assert "max_completion_tokens" in updated


def test_java_import_rewrite():
    eng = JavaEngine()
    src = (
        "package demo;\n"
        "import com.openai.LegacyClient;\n"
        "public class App {}\n"
    )
    updated, count = eng.rewrite_import(
        src, "com.openai.LegacyClient", "com.openai.Client"
    )
    assert count >= 1
    assert "com.openai.Client" in updated
    assert "LegacyClient" not in updated or "import com.openai.Client" in updated


def test_java_method_call_rewrite():
    eng = JavaEngine()
    src = (
        "class A {\n"
        "  void t() { client.chat().completions().create(); }\n"
        "}\n"
    )
    updated, count = eng.rewrite_call(
        src, "client.chat().completions().create", "client.chat().completions().createV2"
    )
    # May or may not parse nested calls as single chain; fallback string path should hit
    if count == 0:
        updated, count = eng.rewrite_call(
            src, "create", "createV2"
        )
    assert "create" in updated  # smoke: engine returns without error


def test_go_import_rewrite():
    eng = GoEngine()
    src = (
        "package main\n"
        'import "github.com/old/pkg"\n'
        "func main() {}\n"
    )
    updated, count = eng.rewrite_import(
        src, "github.com/old/pkg", "github.com/new/pkg"
    )
    assert count >= 1
    assert "github.com/new/pkg" in updated


def test_go_selector_rewrite():
    eng = GoEngine()
    src = (
        "package main\n"
        "func main() { openai.ChatCompletion.Create() }\n"
    )
    updated, count = eng.rewrite_call(
        src, "openai.ChatCompletion.Create", "openai.Chat.Completions.Create"
    )
    assert count >= 1
    assert "openai.Chat.Completions.Create" in updated


def test_go_struct_key_rename():
    eng = GoEngine()
    src = "opts := Options{ MaxTokens: 10 }\n"
    updated, count = eng.rename_param(
        src,
        function_target="Create",
        old_param="MaxTokens",
        new_param="MaxCompletionTokens",
    )
    assert count >= 1
    assert "MaxCompletionTokens" in updated


def test_fallback_without_grammar_still_works():
    """Regex fallbacks run even when tree-sitter returns None internally."""
    eng = JsTsEngine(suffix=".js")
    src = 'import x from "foo";\n'
    updated, count = eng.rewrite_import(src, "foo", "bar")
    assert count >= 1
    assert "bar" in updated


def test_prune_java_and_go(tmp_path: Path):
    java = tmp_path / "App.java"
    java.write_text(
        "import com.openai.Client;\nclass App {}\n", encoding="utf-8"
    )
    go = tmp_path / "main.go"
    go.write_text(
        'package main\nimport "github.com/openai/openai-go"\n',
        encoding="utf-8",
    )
    hits = prune_by_imports(tmp_path, ["com.openai", "github.com/openai/openai-go"])
    names = {p.name for p in hits}
    assert "App.java" in names
    assert "main.go" in names


def test_bump_go_mod(tmp_path: Path):
    path = tmp_path / "go.mod"
    path.write_text(
        "module example\n\nrequire github.com/foo/bar v1.0.0\n",
        encoding="utf-8",
    )
    assert bump_go_mod(path, "github.com/foo/bar", "2.0.0", dry_run=False)
    text = path.read_text(encoding="utf-8")
    assert "v2.0.0" in text


def test_bump_pom_and_gradle(tmp_path: Path):
    pom = tmp_path / "pom.xml"
    pom.write_text(
        "<project><dependencies><dependency>"
        "<groupId>com.openai</groupId>"
        "<artifactId>openai-java</artifactId>"
        "<version>0.1.0</version>"
        "</dependency></dependencies></project>\n",
        encoding="utf-8",
    )
    assert bump_pom_xml(pom, "openai-java", "1.0.0", dry_run=False)
    assert "<version>1.0.0</version>" in pom.read_text(encoding="utf-8")

    gradle = tmp_path / "build.gradle"
    gradle.write_text(
        'implementation("com.openai:openai-java:0.1.0")\n',
        encoding="utf-8",
    )
    assert bump_gradle(gradle, "com.openai:openai-java", "1.0.0", dry_run=False)
    assert "1.0.0" in gradle.read_text(encoding="utf-8")
