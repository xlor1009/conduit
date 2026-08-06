# Detect modules

Detect modules are **vendor-specific plugins** that emit `ChangeSignal`s (API renames, deprecations, suggested packet rules) beyond raw lockfile diffs.

## Interface

```python
class DetectModule(ABC):
    name: str = "module"
    packages: list[str] = []          # e.g. ["openai"]

    def applies(self, installed: dict[str, str]) -> bool:
        ...

    def run(self, ctx: DetectContext) -> list[ChangeSignal]:
        ...
```

`DetectContext` includes `repo_root`, `installed` versions, and `fixture_mode`.

Built-ins register via entry point group:

```toml
[project.entry-points."conduit.detect_modules"]
openai = "conduit.detect.modules.openai:OpenAIModule"
```

Discovery: [`conduit/src/conduit/detect/modules/discovery.py`](../conduit/src/conduit/detect/modules/discovery.py).

## Built-in: OpenAI

`OpenAIModule` runs several workers (fixtures by default for demos/CI):

| Worker | Signal source |
|--------|----------------|
| OpenAPI diff | Spec deltas → param renames |
| Deprecation scraper | Deprecation docs HTML |
| Model polling | Model id removals |
| Changelog parser | RSS / text (optional LLM extract) |
| SDK release | GitHub release tags |

Live network mode is gated by worker env flags / keys; default fixture paths live under [`conduit/fixtures/openai/`](../conduit/fixtures/openai/).

Normalize step turns raw events into `ChangeSignal` + `suggested_rules` that packet synthesis can fold in.

## Scaffold a new module

```bash
conduit module list
conduit module new stripe --package stripe --ecosystem pypi --path ./conduit
```

This creates a module package under `src/conduit/detect/modules/<name>/` (and optional fixtures dir). Wire it into entry points in `pyproject.toml` if you want it auto-loaded.

Out-of-tree modules:

```bash
conduit module new acme --package acme --out-of-tree --path ./my-acme-module
```

Then install that package so its `conduit.detect_modules` entry point is visible.

## Filtering at runtime

```bash
conduit detect --module openai
conduit run --module openai
conduit run --skip-modules          # lockfile only
```

## Related docs

- [Detection](detection.md)
- [Migration packets](migration-packets.md)
- [CLI reference](cli-reference.md)
