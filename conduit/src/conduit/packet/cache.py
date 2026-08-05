"""Migration packet cache under .conduit/packets/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def packets_dir(root: Path) -> Path:
    return root.resolve() / ".conduit" / "packets"


def packet_filename(package: str, from_version: str, to_version: str) -> str:
    safe = lambda s: s.replace("/", "_").replace("\\", "_").replace(" ", "")
    return f"{safe(package)}-{safe(from_version)}-{safe(to_version)}.json"


def cache_path(
    root: Path, package: str, from_version: str, to_version: str
) -> Path:
    return packets_dir(root) / packet_filename(package, from_version, to_version)


def load_packet(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_packet(path: Path, packet: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    return path


def find_cached_packet(
    root: Path, package: str, from_version: str, to_version: str
) -> dict[str, Any] | None:
    path = cache_path(root, package, from_version, to_version)
    if path.is_file():
        return load_packet(path)
    return None
