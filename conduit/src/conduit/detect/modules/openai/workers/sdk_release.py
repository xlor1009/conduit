"""SDKReleaseWorker: major/prerelease SDK bumps vs client's installed version."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from conduit.detect.client_state import PackageClientState
from conduit.detect.modules.openai.models_legacy import ChangeType, RawSignal, Severity
from conduit.detect.modules.openai.workers.base import Worker, fixtures_dir

TAG_RE = re.compile(r"^v?(?P<version>\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)$")

# Info-point registry: which repos to watch (not deprecation content).
DEFAULT_REPOS: dict[str, dict[str, Any]] = {
    "openai/openai-python": {
        "package": "openai",
        "ecosystems": ["pip", "pyproject"],
    },
    "openai/openai-node": {
        "package": "openai",
        "ecosystems": ["npm"],
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


def _ecosystems_match(meta: dict[str, Any], client_ecosystems: list[str]) -> bool:
    wanted = {str(e).lower() for e in (meta.get("ecosystems") or [])}
    if not wanted:
        return True
    # Treat pyproject as pip for matching
    have = {e.lower() for e in client_ecosystems}
    if "pip" in have:
        have.add("pyproject")
    if "pyproject" in have:
        have.add("pip")
    if not have:
        # Unknown ecosystem: allow a single comparison path (prefer pip registry entries)
        return "pip" in wanted or "pyproject" in wanted
    return bool(wanted & have)


class SDKReleaseWorker(Worker):
    name = "SDKReleaseWorker"

    def __init__(self) -> None:
        self.last_skip_reason: str | None = None

    def run(
        self,
        *,
        demo: bool = False,
        client_state: PackageClientState | None = None,
    ) -> list[RawSignal]:
        self.last_skip_reason = None
        installed_raw = (
            (client_state.installed_version if client_state else None) or ""
        ).strip()
        if not installed_raw:
            self.last_skip_reason = "no_installed_version"
            return []

        installed_v = _parse_version(installed_raw)
        if installed_v is None:
            # Allow bare versions like 1.40.0 without v prefix (already handled) or 1.40
            try:
                installed_v = Version(installed_raw.lstrip("v"))
            except InvalidVersion:
                self.last_skip_reason = "unparseable_installed_version"
                return []

        client_ecosystems = list(client_state.ecosystems) if client_state else []
        repos = _load_repo_registry()
        signals: list[RawSignal] = []
        seen_packages: set[str] = set()

        for repo, meta in repos.items():
            if not _ecosystems_match(meta, client_ecosystems):
                continue
            if demo:
                latest_tag = meta.get("latest_tag")
            else:
                latest_tag = _github_latest_tag(repo)
            if not latest_tag:
                continue

            latest_v = _parse_version(str(latest_tag))
            if not latest_v:
                continue

            package = str(meta.get("package") or repo.split("/")[-1])
            pkg_key = package.lower()
            if pkg_key in seen_packages:
                continue
            ecosystems = meta.get("ecosystems", ["pip"])

            major = _is_major_bump(installed_v, latest_v)
            pre = _is_prerelease(str(latest_tag), latest_v)
            if not (major or (pre and latest_v > installed_v)):
                continue

            seen_packages.add(pkg_key)
            severity = Severity.CRITICAL if major else Severity.WARNING
            signals.append(
                RawSignal(
                    vendor="openai",
                    change_type=ChangeType.SDK_MAJOR_BUMP,
                    severity=severity,
                    affected_pattern=package,
                    replacement_pattern=str(latest_v.base_version),
                    source_url=f"https://github.com/{repo}/releases/tag/{latest_tag}",
                    description=(
                        f"SDK {repo} latest {latest_tag} is ahead of client "
                        f"installed {installed_raw}"
                        + (" (prerelease)" if pre else "")
                    ),
                    extra={
                        "package": package,
                        "from_version": str(installed_v.base_version),
                        "to_version": str(latest_v.base_version),
                        "ecosystems": ecosystems,
                        "repo": repo,
                        "latest_tag": latest_tag,
                    },
                )
            )

        if not signals and self.last_skip_reason is None:
            # Healthy: catalog checked, no major/prerelease ahead of client
            self.last_skip_reason = None
        return signals
