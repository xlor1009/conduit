"""Scaffold a new detect module."""

from __future__ import annotations

from pathlib import Path

MODULE_INIT = '''"""Detect module: {name}."""

from __future__ import annotations

from conduit.detect.models import ChangeSignal
from conduit.detect.modules.base import DetectContext, DetectModule


class {class_name}Module(DetectModule):
    name = "{name}"
    packages = {packages!r}

    def run(self, ctx: DetectContext) -> list[ChangeSignal]:
        # TODO: scrape changelogs / OpenAPI / releases and emit ChangeSignals
        _ = ctx
        return []
'''

MODULE_MD = """# {name} detect module

Checklist:

1. Implement `{class_name}Module.run()` to emit `ChangeSignal`s.
2. Add offline fixtures under `fixtures/{name}/`.
3. Register built-in in `conduit.detect.modules.discovery._builtin_modules`, **or**
   for an external package add entry point:

```toml
[project.entry-points."conduit.detect_modules"]
{name} = "your_package.module:{class_name}Module"
```

4. Verify: `conduit module list`
"""

TEST_STUB = '''"""Smoke test for {name} module."""

from conduit.detect.modules.{name} import {class_name}Module


def test_module_name():
    mod = {class_name}Module()
    assert mod.name == "{name}"
'''


def _class_name(name: str) -> str:
    parts = [p for p in name.replace("-", "_").split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def scaffold_module(
    name: str,
    *,
    package: str | None = None,
    ecosystem: str = "pypi",
    target_root: Path,
    out_of_tree: bool = False,
) -> Path:
    """
    Create a new detect module stub.
    Default: under target_root/src/conduit/detect/modules/<name>/
    """
    _ = ecosystem
    class_name = _class_name(name)
    packages = [package or name]
    if out_of_tree:
        mod_dir = target_root / name
    else:
        mod_dir = target_root / "src" / "conduit" / "detect" / "modules" / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "workers").mkdir(exist_ok=True)
    (mod_dir / "workers" / ".gitkeep").write_text("", encoding="utf-8")
    (mod_dir / "__init__.py").write_text(
        MODULE_INIT.format(name=name, class_name=class_name, packages=packages),
        encoding="utf-8",
    )
    (mod_dir / "MODULE.md").write_text(
        MODULE_MD.format(name=name, class_name=class_name),
        encoding="utf-8",
    )
    fixtures = target_root / "fixtures" / name
    if not out_of_tree:
        fixtures.mkdir(parents=True, exist_ok=True)
        (fixtures / ".gitkeep").write_text("", encoding="utf-8")
        tests_dir = target_root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / f"test_module_{name}.py").write_text(
            TEST_STUB.format(name=name, class_name=class_name),
            encoding="utf-8",
        )
    return mod_dir
