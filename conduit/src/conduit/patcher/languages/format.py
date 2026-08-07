"""Best-effort post-edit formatters. Never raise; missing tools are no-ops."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def maybe_format(content: str, *, suffix: str) -> str:
    """Format ``content`` when a known formatter is available for ``suffix``."""
    suffix = suffix.lower()
    if suffix == ".go":
        return _run_formatter(["gofmt"], content, suffix=".go")
    if suffix == ".java":
        if shutil.which("google-java-format"):
            return _run_formatter(
                ["google-java-format", "-"], content, suffix=".java", stdin=True
            )
        return content
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        if shutil.which("prettier"):
            parser = "typescript" if suffix in {".ts", ".tsx"} else "babel"
            return _run_formatter(
                ["prettier", "--parser", parser],
                content,
                suffix=suffix,
                stdin=True,
            )
        return content
    return content


def _run_formatter(
    cmd: list[str],
    content: str,
    *,
    suffix: str,
    stdin: bool = False,
) -> str:
    if not shutil.which(cmd[0]):
        return content
    try:
        if stdin:
            proc = subprocess.run(
                cmd,
                input=content,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
            return content

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"file{suffix}"
            path.write_text(content, encoding="utf-8")
            proc = subprocess.run(
                [*cmd, str(path)],
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0:
                return content
            return path.read_text(encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired):
        return content
