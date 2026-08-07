"""Update dependency pins in manifests (pip/npm/go/maven/gradle)."""

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
            deps[package] = (
                to_version
                if to_version.startswith(("^", "~", ">="))
                else f"^{to_version}"
            )
            changed = True
    if changed and not dry_run:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def bump_go_mod(path: Path, package: str, to_version: str, *, dry_run: bool) -> bool:
    """Bump a ``require`` line in go.mod (module path match)."""
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    ver = to_version if to_version.startswith("v") else f"v{to_version}"
    # Matches both `require pkg v1` and indented `pkg v1` inside a require block
    pattern = re.compile(
        rf"(?m)^((?:require\s+)?\s*{re.escape(package)}\s+)v?[^\s]+"
    )
    updated, n = pattern.subn(rf"\1{ver}", original)
    if n == 0:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def bump_pom_xml(path: Path, package: str, to_version: str, *, dry_run: bool) -> bool:
    """Lightweight Maven pom.xml bump by artifactId + following version tag."""
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    # Match <artifactId>pkg</artifactId> ... <version>x</version> within a dependency
    pattern = re.compile(
        rf"(<artifactId>\s*{re.escape(package)}\s*</artifactId>\s*"
        rf"(?:<(?!version\b)[^>]+>.*?</[^>]+>\s*)*"
        rf"<version>\s*)([^<]+)(</version>)",
        re.DOTALL,
    )
    updated, n = pattern.subn(rf"\g<1>{to_version}\3", original)
    if n == 0:
        # Also try groupId:artifactId style package names (artifact only)
        artifact = package.split(":")[-1]
        if artifact != package:
            pattern = re.compile(
                rf"(<artifactId>\s*{re.escape(artifact)}\s*</artifactId>\s*"
                rf"(?:<(?!version\b)[^>]+>.*?</[^>]+>\s*)*"
                rf"<version>\s*)([^<]+)(</version>)",
                re.DOTALL,
            )
            updated, n = pattern.subn(rf"\g<1>{to_version}\3", original)
    if n == 0:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def bump_gradle(path: Path, package: str, to_version: str, *, dry_run: bool) -> bool:
    """Bump Gradle dependency strings containing the package/coordinate."""
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    # "group:artifact:version" or 'group:artifact:version'
    artifact = package if ":" in package else package
    pattern = re.compile(
        rf'(["\'])({re.escape(artifact)}):([^"\']*)(["\'])'
    )
    updated, n = pattern.subn(rf"\1\2:{to_version}\4", original)
    if n == 0 and ":" not in package:
        # implementation("pkg:name:1.0") where package is name
        pattern = re.compile(
            rf'(["\'])([\w.-]+:{re.escape(package)}):([^"\']*)(["\'])'
        )
        updated, n = pattern.subn(rf"\1\2:{to_version}\4", original)
    if n == 0:
        return False
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def apply_dependency_bump(
    root: Path,
    rule: dict[str, Any],
    *,
    dry_run: bool = False,
) -> list[str]:
    package = rule["package"]
    to_version = rule["to_version"]
    ecosystems = set(
        rule.get("ecosystems")
        or ["pip", "npm", "pyproject", "go", "maven", "gradle"]
    )
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

    if "go" in ecosystems:
        gomod = root / "go.mod"
        if bump_go_mod(gomod, package, to_version, dry_run=dry_run):
            changed.append(str(gomod.relative_to(root)))

    if "maven" in ecosystems:
        pom = root / "pom.xml"
        if bump_pom_xml(pom, package, to_version, dry_run=dry_run):
            changed.append(str(pom.relative_to(root)))

    if "gradle" in ecosystems:
        for name in ("build.gradle", "build.gradle.kts"):
            gradle = root / name
            if bump_gradle(gradle, package, to_version, dry_run=dry_run):
                changed.append(str(gradle.relative_to(root)))

    return changed
