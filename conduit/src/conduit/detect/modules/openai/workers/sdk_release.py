"""SDKReleaseWorker: detect major semver bumps / rc tags on official SDKs."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from conduit.detect.modules.openai.models_legacy import ChangeType, RawSignal, Severity
from conduit.detect.modules.openai.workers.base import Worker, data_dir, fixtures_dir

TAG_RE = re.compile(r"^v?(?P<version>\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)$")

# Info-point registry: which repos to watch (not deprecation content).
DEFAULT_REPOS: dict[str, dict[str, Any]] = {
    "openai/openai-python": {
        "package": "openai",
        "ecosystems": ["pip", "pyproject"],
        "previous_tag": "v0.28.1",
    },
    "openai/openai-node": {
        "package": "openai",
        "ecosystems": ["npm"],
        "previous_tag": "v3.3.0",
    },
}


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


def _load_repo_registry() -> dict[str, dict[str, Any]]:
    """Repos of SDK repos to poll (info points). Fixture file or built-in defaults."""
    fixture = fixtures_dir() / "sdk_releases" / "tags.json"
    if fixture.is_file():
        try:
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            repos = payload.get("repos") or {}
            if isinstance(repos, dict) and repos:
                return repos
        except (OSError, json.JSONDecodeError):
            pass
    return dict(DEFAULT_REPOS)


class SDKReleaseWorker(Worker):
    name = "SDKReleaseWorker"

    def run(self, *, demo: bool = False) -> list[RawSignal]:
        repos = _load_repo_registry()
        snapshot_path = data_dir() / ".sdk-tags-snapshot.json"
        prior: dict[str, str] = {}
        if snapshot_path.is_file():
            try:
                prior = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                prior = {}

        signals: list[RawSignal] = []
        next_snapshot: dict[str, str] = dict(prior)

        for repo, meta in repos.items():
            previous_tag = prior.get(repo) or meta.get("previous_tag", "v0.0.0")
            if demo:
                latest_tag = meta.get("latest_tag")
            else:
                latest_tag = _github_latest_tag(repo)
            if not latest_tag:
                continue

            prev_v = _parse_version(str(previous_tag))
            latest_v = _parse_version(str(latest_tag))
            if not prev_v or not latest_v:
                continue

            package = meta.get("package", repo.split("/")[-1])
            ecosystems = meta.get("ecosystems", ["pip"])
            next_snapshot[repo] = str(latest_tag)

            if _is_major_bump(prev_v, latest_v) or _is_prerelease(str(latest_tag), latest_v):
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
                            + (" (prerelease)" if _is_prerelease(str(latest_tag), latest_v) else "")
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

        if not demo:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(next_snapshot, indent=2) + "\n", encoding="utf-8")

        return signals
