"""Update dependency pins in package.json / requirements.txt / pyproject.toml."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def bump_requirements_txt(path: Path, package: str, to_version: str, *, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(?m)^(\s*{re.escape(package)}\s*)(?:==|>=|~=|<=)?\s*[^\s#]*"
    )
    updated, n = pattern.subn(rf"\1=={to_version}", original)
    if n == 0:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def bump_pyproject(path: Path, package: str, to_version: str, *, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    # Simple string bump for dependencies = [ "openai==x" ] style
    pattern = re.compile(
        rf'(["\']){re.escape(package)}\s*(?:==|>=|~=)?\s*[^"\']*(["\'])'
    )
    updated, n = pattern.subn(rf"\1{package}=={to_version}\2", original)
    if n == 0:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def bump_package_json(path: Path, package: str, to_version: str, *, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section)
        if isinstance(deps, dict) and package in deps:
            deps[package] = to_version if to_version.startswith(("^", "~", ">=")) else f"^{to_version}"
            changed = True
    if changed and not dry_run:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def apply_dependency_bump(
    root: Path,
    rule: dict[str, Any],
    *,
    dry_run: bool = False,
) -> list[str]:
    package = rule["package"]
    to_version = rule["to_version"]
    ecosystems = set(rule.get("ecosystems") or ["pip", "npm", "pyproject"])
    changed: list[str] = []

    if "pip" in ecosystems:
        req = root / "requirements.txt"
        if bump_requirements_txt(req, package, to_version, dry_run=dry_run):
            changed.append(str(req.relative_to(root)))

    if "pyproject" in ecosystems:
        pyproject = root / "pyproject.toml"
        if bump_pyproject(pyproject, package, to_version, dry_run=dry_run):
            changed.append(str(pyproject.relative_to(root)))

    if "npm" in ecosystems:
        pkg = root / "package.json"
        if bump_package_json(pkg, package, to_version, dry_run=dry_run):
            changed.append(str(pkg.relative_to(root)))

    return changed
