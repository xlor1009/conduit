"""SDKReleaseWorker: detect major semver bumps / rc tags on official SDKs."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from vendor_signal_registry.models import ChangeType, RawSignal, Severity
from vendor_signal_registry.workers.base import Worker, env_flag, fixtures_dir

TAG_RE = re.compile(r"^v?(?P<version>\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)$")


def _parse_version(tag: str) -> Version | None:
    match = TAG_RE.match(tag.strip())
    if not match:
        return None
    try:
        return Version(match.group("version"))
    except InvalidVersion:
        return None


def _is_major_bump(previous: Version, latest: Version) -> bool:
    return latest.major > previous.major


def _is_prerelease(tag: str, version: Version) -> bool:
    return bool(version.is_prerelease) or "-rc" in tag.lower() or ".rc" in tag.lower()


def _github_latest_tag(repo: str) -> str | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = httpx.get(url, headers=headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json().get("tag_name")
    except (httpx.HTTPError, json.JSONDecodeError):
        return None


class SDKReleaseWorker(Worker):
    name = "SDKReleaseWorker"

    def run(self) -> list[RawSignal]:
        fixture = fixtures_dir() / "sdk_releases" / "tags.json"
        payload: dict[str, Any] = json.loads(fixture.read_text(encoding="utf-8"))
        repos = payload.get("repos", {})
        signals: list[RawSignal] = []

        for repo, meta in repos.items():
            previous_tag = meta.get("previous_tag", "v0.0.0")
            latest_tag = meta.get("latest_tag")
            if env_flag("SDK_RELEASE_LIVE"):
                live = _github_latest_tag(repo)
                if live:
                    latest_tag = live

            if not latest_tag:
                continue

            prev_v = _parse_version(previous_tag)
            latest_v = _parse_version(latest_tag)
            if not prev_v or not latest_v:
                continue

            package = meta.get("package", repo.split("/")[-1])
            ecosystems = meta.get("ecosystems", ["pip"])

            if _is_major_bump(prev_v, latest_v) or _is_prerelease(latest_tag, latest_v):
                severity = (
                    Severity.CRITICAL if _is_major_bump(prev_v, latest_v) else Severity.WARNING
                )
                signals.append(
                    RawSignal(
                        vendor="openai",
                        change_type=ChangeType.SDK_MAJOR_BUMP,
                        severity=severity,
                        affected_pattern=package,
                        replacement_pattern=str(latest_v.base_version),
                        source_url=f"https://github.com/{repo}/releases/tag/{latest_tag}",
                        description=(
                            f"SDK {repo} bumped {previous_tag} -> {latest_tag}"
                            + (" (prerelease)" if _is_prerelease(latest_tag, latest_v) else "")
                        ),
                        extra={
                            "package": package,
                            "from_version": str(prev_v.base_version),
                            "to_version": str(latest_v.base_version),
                            "ecosystems": ecosystems,
                            "repo": repo,
                            "latest_tag": latest_tag,
                        },
                    )
                )
        return signals
