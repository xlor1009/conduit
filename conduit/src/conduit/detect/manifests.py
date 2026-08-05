"""Parse currently installed package versions from manifests."""

from __future__ import annotations

from pathlib import Path

from conduit.detect.lockfile_diff import (
    _parse_go_mod,
    _parse_package_json_deps,
    _parse_pyproject_deps,
    _parse_requirements_lines,
)


def read_installed(root: Path) -> dict[str, str]:
    """Return package -> version from common manifests at repo root."""
    root = root.resolve()
    installed: dict[str, str] = {}

    req = root / "requirements.txt"
    if req.is_file():
        installed.update(_parse_requirements_lines(req.read_text(encoding="utf-8")))

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        installed.update(_parse_pyproject_deps(pyproject.read_text(encoding="utf-8")))

    pkg = root / "package.json"
    if pkg.is_file():
        installed.update(_parse_package_json_deps(pkg.read_text(encoding="utf-8")))

    gomod = root / "go.mod"
    if gomod.is_file():
        installed.update(_parse_go_mod(gomod.read_text(encoding="utf-8")))

    return installed
