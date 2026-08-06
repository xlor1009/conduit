"""Build Migration Packets from signals, docs, or LLM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from conduit.detect.models import ChangeSignal
from conduit.packet.cache import save_packet
from conduit.packet.validate import validate_packet


def packet_id_for(package: str, from_version: str, to_version: str) -> str:
    return f"{package}-{from_version}-{to_version}"


def empty_packet(
    *,
    package: str,
    ecosystem: str,
    from_version: str,
    to_version: str,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "packet_id": packet_id_for(package, from_version, to_version),
        "package": package,
        "ecosystem": ecosystem,
        "from_version": from_version,
        "to_version": to_version,
        "sources": [],
        "notes": notes,
        "rules": [],
    }


def packet_from_signals(
    signals: list[ChangeSignal],
    *,
    package: str,
    ecosystem: str = "pypi",
    from_version: str = "0.0.0",
    to_version: str = "1.0.0",
) -> dict[str, Any]:
    """Assemble a packet from ChangeSignal suggested_rules (deterministic)."""
    pkg_signals = [s for s in signals if s.package.lower() == package.lower()]
    if pkg_signals:
        # Prefer lockfile jump versions when present
        for s in pkg_signals:
            if s.from_version and s.to_version:
                from_version = s.from_version
                to_version = s.to_version
                if s.ecosystem:
                    ecosystem = s.ecosystem
                break

    packet = empty_packet(
        package=package,
        ecosystem=ecosystem if ecosystem in {"pypi", "npm", "go", "other"} else "other",
        from_version=from_version,
        to_version=to_version,
        notes="Synthesized from detect signals",
    )
    rules: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    seen_rules: set[str] = set()
    for s in pkg_signals or signals:
        if s.source_url:
            sources.append({"url": s.source_url, "kind": "other"})
        for rule in s.suggested_rules:
            key = json.dumps(rule, sort_keys=True)
            if key in seen_rules:
                continue
            seen_rules.add(key)
            rules.append(rule)
        # Model deprecations without suggested rules still become string replaces
        if (
            s.change_type in {"MODEL_DEPRECATION", "MODEL_REMOVED"}
            and s.affected_pattern
            and s.replacement_pattern
        ):
            rule = {
                "type": "EXACT_STRING_REPLACE",
                "target_files": ["*.py", "*.ts", "*.js", "*.yaml", "*.yml", "*.json", ".env*"],
                "match": s.affected_pattern,
                "replace": s.replacement_pattern,
            }
            key = json.dumps(rule, sort_keys=True)
            if key not in seen_rules:
                seen_rules.add(key)
                rules.append(rule)
    packet["rules"] = rules
    packet["sources"] = sources
    return packet


def synthesize_from_docs(
    *,
    package: str,
    from_version: str,
    to_version: str,
    ecosystem: str = "pypi",
    changelog_text: str = "",
    docs_text: str = "",
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a packet from vendor docs. Uses configured LLM when available;
    otherwise returns base packet or empty rules with sources noted.
    """
    from conduit.llm import get_llm_client

    packet = base or empty_packet(
        package=package,
        ecosystem=ecosystem,
        from_version=from_version,
        to_version=to_version,
        notes="Synthesized from vendor docs",
    )
    if changelog_text:
        packet.setdefault("sources", []).append(
            {"url": "local://changelog", "kind": "changelog"}
        )
    if docs_text:
        packet.setdefault("sources", []).append(
            {"url": "local://docs", "kind": "docs"}
        )

    client = get_llm_client()
    if client is None or not (changelog_text or docs_text):
        return packet

    prompt = {
        "instructions": (
            "Generate a Conduit migration packet JSON with keys: "
            "packet_id, package, ecosystem, from_version, to_version, sources, notes, rules. "
            "Rules may use EXACT_STRING_REPLACE, REGEX_REPLACE, AST_PARAM_RENAME, "
            "DEPENDENCY_BUMP, AST_IMPORT_REWRITE, AST_ATTR_RENAME, AST_CALL_REWRITE. "
            "Reply with JSON only."
        ),
        "package": package,
        "from_version": from_version,
        "to_version": to_version,
        "ecosystem": ecosystem,
        "changelog": changelog_text[:12000],
        "docs": docs_text[:12000],
        "seed": packet,
    }
    try:
        data = client.complete_json(
            system="You author Conduit migration packets. JSON only.",
            user=json.dumps(prompt),
        )
        if data and not validate_packet(data):
            return data
        if data:
            packet["rules"] = data.get("rules") or packet.get("rules") or []
            packet["notes"] = data.get("notes") or packet.get("notes")
    except Exception:
        pass
    return packet


def load_fixture_openai_packet() -> dict[str, Any]:
    """Offline demo packet derived from classic openai deprecation fixtures."""
    return {
        "packet_id": "openai-0.28.1-1.0.0",
        "package": "openai",
        "ecosystem": "pypi",
        "from_version": "0.28.1",
        "to_version": "1.0.0",
        "sources": [
            {
                "url": "https://platform.openai.com/docs/deprecations",
                "kind": "docs",
            }
        ],
        "notes": "Offline fixture packet for demo-consumer (model + param renames).",
        "rules": [
            {
                "type": "EXACT_STRING_REPLACE",
                "target_files": [
                    "*.py",
                    "*.ts",
                    "*.js",
                    "*.yaml",
                    "*.yml",
                    "*.json",
                    ".env*",
                ],
                "match": "gpt-4-0613",
                "replace": "gpt-4o",
            },
            {
                "type": "AST_PARAM_RENAME",
                "target_files": ["*.py", "*.ts", "*.js"],
                "function_target": "chat.completions.create",
                "old_param": "max_tokens",
                "new_param": "max_completion_tokens",
            },
            {
                "type": "DEPENDENCY_BUMP",
                "package": "openai",
                "from_version": "0.28.1",
                "to_version": "1.0.0",
                "ecosystems": ["pip", "pyproject"],
            },
        ],
    }


def ensure_packet(
    root: Path,
    signals: list[ChangeSignal],
    *,
    package: str,
    packet_path: Path | None = None,
    use_fixture_fallback: bool = True,
) -> dict[str, Any]:
    """Load explicit packet, cache, signal-synth, or openai fixture."""
    from conduit.packet.cache import find_cached_packet, cache_path

    if packet_path and packet_path.is_file():
        return json.loads(packet_path.read_text(encoding="utf-8"))

    from_v, to_v = "0.0.0", "1.0.0"
    eco = "pypi"
    for s in signals:
        if s.package.lower() == package.lower() and s.from_version and s.to_version:
            from_v, to_v = s.from_version, s.to_version
            eco = s.ecosystem or eco
            break

    cached = find_cached_packet(root, package, from_v, to_v)
    if cached:
        return cached

    packet = packet_from_signals(
        signals, package=package, ecosystem=eco, from_version=from_v, to_version=to_v
    )
    if not packet.get("rules") and use_fixture_fallback and package.lower() == "openai":
        packet = load_fixture_openai_packet()

    save_packet(cache_path(root, package, packet["from_version"], packet["to_version"]), packet)
    return packet
