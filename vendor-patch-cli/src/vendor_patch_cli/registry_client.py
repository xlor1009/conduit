"""Fetch vendor signal registry (Approach A CDN or Approach B custom endpoint)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_REGISTRY_URL = (
    "https://your-org.github.io/vendor-signals/registry.json"
)


def _is_path_like(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"", "file"}:
        return True
    if parsed.scheme == "http" and parsed.hostname in {"internal-gateway", "localhost"}:
        return False
    return False


def load_registry(
    *,
    registry_url: str | None = None,
    custom_endpoint: str | None = None,
    local_fallback: Path | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Approach A: download central registry.json over HTTP.
    Approach B: if custom_endpoint is set, fetch that URL instead.
    Local file paths and file:// URLs are also supported for demos/CI.
    """
    url = custom_endpoint or registry_url or DEFAULT_REGISTRY_URL

    # Local path support
    path_candidate = Path(url)
    if path_candidate.is_file():
        return json.loads(path_candidate.read_text(encoding="utf-8"))

    if url.startswith("file://"):
        local = Path(url[7:])
        return json.loads(local.read_text(encoding="utf-8"))

    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        if local_fallback and local_fallback.is_file():
            return json.loads(local_fallback.read_text(encoding="utf-8"))
        # Try monorepo dist as last resort
        monorepo = (
            Path(__file__).resolve().parents[3]
            / "vendor-signal-registry"
            / "dist"
            / "registry.json"
        )
        if monorepo.is_file():
            return json.loads(monorepo.read_text(encoding="utf-8"))
        raise RuntimeError(
            f"Failed to fetch registry from {url}: {exc}. "
            "Pass --registry-url to a local registry.json for offline use."
        ) from exc


def filter_events(
    registry: dict[str, Any],
    *,
    vendor: str | None = None,
    event_id: str | None = None,
) -> list[dict[str, Any]]:
    events = list(registry.get("events") or [])
    if vendor:
        events = [e for e in events if e.get("vendor") == vendor]
    if event_id:
        events = [e for e in events if e.get("event_id") == event_id]
    return events
