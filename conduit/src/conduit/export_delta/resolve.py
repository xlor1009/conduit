"""Download / unpack package versions into a local cache for export scanning."""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path


def _cache_dir(cache_root: Path | None, ecosystem: str, package: str, version: str) -> Path:
    root = cache_root or (Path.cwd() / ".conduit" / "exports")
    safe_pkg = package.replace("/", "__").replace("@", "")
    return root / ecosystem / safe_pkg / version


def resolve_package_tree(
    package: str,
    version: str,
    *,
    ecosystem: str = "pypi",
    cache_root: Path | None = None,
) -> tuple[Path | None, str | None]:
    """
    Return (directory with unpacked sources, error).
    Uses `.conduit/exports/` cache. On failure returns (None, reason).
    """
    if not version or version in {"0.0.0", "0", "unknown", "?"}:
        return None, (
            f"{package}=={version or '(empty)'}: placeholder/missing version "
            "(no real package version on the migration packet)"
        )

    dest = _cache_dir(cache_root, ecosystem, package, version)
    marker = dest / ".conduit_ready"
    if marker.is_file() and dest.is_dir():
        return dest, None

    dest.mkdir(parents=True, exist_ok=True)
    try:
        if ecosystem in {"pypi", "pip", "other"}:
            ok, err = _fetch_pypi(package, version, dest)
        elif ecosystem == "npm":
            ok, err = _fetch_npm(package, version, dest)
        else:
            ok, err = _fetch_pypi(package, version, dest)
    except Exception as exc:
        ok, err = False, f"{package}=={version}: {exc}"

    if not ok:
        if dest.exists() and not any(dest.iterdir()):
            dest.rmdir()
        return None, err or f"{package}=={version}: fetch failed"

    marker.write_text("ok", encoding="utf-8")
    return dest, None


def _fetch_pypi(package: str, version: str, dest: Path) -> tuple[bool, str]:
    """pip download --no-deps and unpack sdist/wheel into dest."""
    download_dir = dest / "_download"
    if download_dir.exists():
        shutil.rmtree(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    spec = f"{package}=={version}"
    cmd = [
        "python",
        "-m",
        "pip",
        "download",
        "--no-deps",
        "--no-binary",
        ":none:",
        "-d",
        str(download_dir),
        spec,
    ]
    # Prefer sdist; if that fails, allow wheels
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        cmd = [
            "python",
            "-m",
            "pip",
            "download",
            "--no-deps",
            "-d",
            str(download_dir),
            spec,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            if len(detail) > 500:
                detail = detail[:500] + "…"
            return False, f"pip download {spec} failed" + (f": {detail}" if detail else "")

    archives = list(download_dir.glob("*"))
    if not archives:
        return False, f"pip download {spec} produced no archives"

    archive = archives[0]
    extract_root = dest / "_src"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)

    name = archive.name.lower()
    if name.endswith(".whl") or name.endswith(".zip"):
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(extract_root)
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(extract_root)
    else:
        return False, f"unsupported archive type for {spec}: {archive.name}"

    return True, ""


def _fetch_npm(package: str, version: str, dest: Path) -> tuple[bool, str]:
    """npm pack and unpack into dest."""
    if not shutil.which("npm") and not shutil.which("npm.cmd"):
        return False, "npm not found on PATH"
    npm = "npm.cmd" if shutil.which("npm.cmd") else "npm"
    spec = f"{package}@{version}"
    proc = subprocess.run(
        [npm, "pack", spec, "--pack-destination", str(dest)],
        capture_output=True,
        text=True,
        check=False,
        cwd=dest,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if len(detail) > 500:
            detail = detail[:500] + "…"
        return False, f"npm pack {spec} failed" + (f": {detail}" if detail else "")

    tgzs = list(dest.glob("*.tgz"))
    if not tgzs:
        # npm pack prints filename
        line = (proc.stdout or "").strip().splitlines()
        if line:
            candidate = dest / line[-1].strip()
            if candidate.is_file():
                tgzs = [candidate]
    if not tgzs:
        return False, f"npm pack {spec} produced no tarball"

    extract_root = dest / "_src"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgzs[0], "r:gz") as tf:
        tf.extractall(extract_root)
    return True, ""


def package_scan_root(tree: Path) -> Path:
    """Return the directory that actually holds package source / package.json."""
    src = tree / "_src"
    if not src.is_dir():
        return tree
    # npm pack extracts to package/
    pkg = src / "package"
    if pkg.is_dir():
        return pkg
    children = [p for p in src.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    return src
