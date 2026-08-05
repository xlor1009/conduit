"""DeprecationScraperWorker: extract deprecation metadata from vendor pages."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from conduit.detect.modules.openai.models_legacy import ChangeType, RawSignal, Severity
from conduit.detect.modules.openai.workers.base import Worker, env_flag, fixtures_dir

DEFAULT_URL = "https://platform.openai.com/docs/deprecations"


def _normalize_deadline(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            continue
    return raw if "T" in raw else f"{raw}T00:00:00Z"


def _parse_severity(raw: str | None) -> Severity:
    value = (raw or "WARNING").strip().upper()
    if value in Severity.__members__:
        return Severity[value]
    if value in {"HIGH", "ERROR", "FATAL"}:
        return Severity.CRITICAL
    return Severity.WARNING


def parse_deprecation_html(html: str, source_url: str) -> list[RawSignal]:
    soup = BeautifulSoup(html, "html.parser")
    signals: list[RawSignal] = []

    for row in soup.select("tr[data-legacy]"):
        legacy = row.get("data-legacy") or ""
        replacement = row.get("data-replacement")
        shutdown = row.get("data-shutdown")
        severity = _parse_severity(row.get("data-severity"))
        if not legacy:
            continue
        signals.append(
            RawSignal(
                vendor="openai",
                change_type=ChangeType.MODEL_DEPRECATION,
                severity=severity,
                affected_pattern=legacy,
                replacement_pattern=replacement,
                deadline=_normalize_deadline(shutdown),
                source_url=source_url,
                description=f"Model {legacy} deprecated; replace with {replacement}",
            )
        )

    if signals:
        return signals

    # Fallback: table rows with 4 cells
    for row in soup.select("table#deprecations tbody tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        legacy, replacement, shutdown = cells[0], cells[1], cells[2]
        severity = _parse_severity(cells[3] if len(cells) > 3 else "WARNING")
        signals.append(
            RawSignal(
                vendor="openai",
                change_type=ChangeType.MODEL_DEPRECATION,
                severity=severity,
                affected_pattern=legacy,
                replacement_pattern=replacement,
                deadline=_normalize_deadline(shutdown),
                source_url=source_url,
                description=f"Model {legacy} deprecated; replace with {replacement}",
            )
        )
    return signals


class DeprecationScraperWorker(Worker):
    name = "DeprecationScraperWorker"

    def run(self) -> list[RawSignal]:
        fixture = fixtures_dir() / "deprecations" / "openai_deprecations.html"
        if env_flag("SCRAPE_LIVE"):
            try:
                resp = httpx.get(DEFAULT_URL, timeout=30.0, follow_redirects=True)
                resp.raise_for_status()
                live = parse_deprecation_html(resp.text, DEFAULT_URL)
                if live:
                    return live
            except httpx.HTTPError:
                pass
        html = fixture.read_text(encoding="utf-8")
        return parse_deprecation_html(html, DEFAULT_URL)
