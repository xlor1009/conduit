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

`DetectContext` includes `repo_root`, `installed` versions, and `demo` (offline fixtures vs live sources).

Built-ins register via entry point group:

```toml
[project.entry-points."conduit.detect_modules"]
openai = "conduit.detect.modules.openai:OpenAIModule"
```

Discovery: [`conduit/src/conduit/detect/modules/discovery.py`](../conduit/src/conduit/detect/modules/discovery.py).

## Built-in: OpenAI

`OpenAIModule` runs several workers. **Live by default** (network). Pass `--demo` for offline fixtures (CI / sample packet demos).

| Worker | Live source | Demo fixture |
|--------|-------------|--------------|
| OpenAPI diff | Fixture `previous.yaml` (baseline) vs freshly cloned `openai/openai-openapi` latest | `fixtures/openai/openapi/` (previous vs latest) |
| Deprecation scraper | `https://platform.openai.com/docs/deprecations` | `fixtures/openai/deprecations/` |
| Model polling | `GET /v1/models` (needs `OPENAI_API_KEY`) | `fixtures/openai/models/` |
| Changelog parser | platform changelog page | `fixtures/openai/changelogs/` |
| SDK release | GitHub releases API | `fixtures/openai/sdk_releases/` (also lists repos to watch) |

Normalize emits apply rules **only when grounded**: model A→B when scrape states both; path replace only when both `/v1/...` sides are known; `AST_PARAM_RENAME` only when the signal carries explicit `function_target`(s). No path-fallback maps and no invented ChatCompletion target lists.

Call-shape / successor gaps are filled by **evidence + LLM packet enrichment** (module seed URLs + web search) when an LLM is configured — see [LLM configuration](llm.md).

Clean “0 signals” from OpenAPI/changelog/SDK workers are **verbose-only** (`-v`); missing `OPENAI_API_KEY` for model polling still warns always.

Fixtures and the SDK repo list are **info-point / offline** data. Model replacement strings should come from live deprecation pages, not hardcoded module maps.

```bash
conduit detect --path . --module openai          # live
conduit detect --path . --module openai --demo   # fixtures
conduit run --path . --packet openai -v          # live detect
conduit run --path ./examples/demo-consumer --packet ./examples/sample-packet/conduit-packet.json --demo --skip-pr
```

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
