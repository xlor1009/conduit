"""Fetch external migration context (GitHub releases, URLs)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx


def read_local_text(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def fetch_url(url: str, *, timeout: float = 30.0) -> str:
    headers = {}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def fetch_github_release_notes(owner: str, repo: str, tag: str | None = None) -> str:
    if tag:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    else:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        text = fetch_url(url)
    except Exception:
        return ""
    return text
