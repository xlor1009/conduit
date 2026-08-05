"""Scaffold a vendor Migration Packet directory."""

from __future__ import annotations

import json
from pathlib import Path

from conduit.packet.synthesize import empty_packet

PACKET_README = """# Conduit Migration Packet: {packet_id}

Package: `{package}` (`{ecosystem}`)
Version jump: `{from_version}` → `{to_version}`

## Consumer usage

```bash
# Option A: drop into consumer cache
cp conduit-packet.json /path/to/repo/.conduit/packets/

# Option B: explicit path
conduit run --path /path/to/repo --packet ./conduit-packet.json
```

## Authoring

1. Edit `rules` in `conduit-packet.json` (see schema/conduit-packet.schema.json).
2. Validate: `conduit packet validate ./conduit-packet.json`
3. Optional: regenerate from docs:
   `conduit packet synthesize --package {package} --from {from_version} --to {to_version} --changelog CHANGELOG.md --docs MIGRATION.md --out ./conduit-packet.json`
"""


def scaffold_packet(
    *,
    package: str,
    ecosystem: str,
    from_version: str,
    to_version: str,
    out_dir: Path,
) -> Path:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    packet = empty_packet(
        package=package,
        ecosystem=ecosystem,
        from_version=from_version,
        to_version=to_version,
        notes="Vendor-authored migration packet (edit rules).",
    )
    packet_path = out_dir / "conduit-packet.json"
    packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    (out_dir / "README.md").write_text(
        PACKET_README.format(**packet),
        encoding="utf-8",
    )
    examples = out_dir / "examples"
    examples.mkdir(exist_ok=True)
    (examples / ".gitkeep").write_text("", encoding="utf-8")
    return packet_path
