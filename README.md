# Conduit

Open-source, self-hosted CLI that performs breaking API updates in consumer repositories.

When you run `conduit run`:

1. **Detect** — lockfile/manifest git diffs plus pluggable vendor **detect modules** (e.g. `openai`)
2. **Prune** — ripgrep-style import filter so only relevant files are touched
3. **Packet** — load or synthesize a Migration Packet (`conduit-packet.json`)
4. **Apply** — deterministic AST/string codemods
5. **Verify** — native tests (`pytest` / `npm test` / `go test`) with LLM self-correction (up to 5 retries)
6. **PR** — branch `conduit/upgrade-{package}-{version}` and open a pull request

```text
Lockfile diff + vendor modules  →  ChangeSignals
        ↓
Import prune  →  Migration Packet (cache or synth)
        ↓
AST apply  →  tests / self-correct  →  PR
```

## Quick start

```bash
pip install -e "./conduit[llm,dev]"

# Detect signals (modules use offline fixtures by default)
conduit detect --path ./examples/demo-consumer --module openai

# Apply the sample vendor packet (dry-run)
conduit apply --path ./examples/demo-consumer \
  --packet ./examples/sample-packet/conduit-packet.json --dry-run

# Full local run without opening a PR
conduit run --path ./examples/demo-consumer \
  --packet ./examples/sample-packet/conduit-packet.json --skip-pr
```

## Author a detect module

```bash
conduit module new stripe --package stripe --path ./conduit
conduit module list
```

External packages can register via entry point group `conduit.detect_modules`.

## Author a Migration Packet (vendors)

```bash
conduit packet init --package openai --from 0.28.0 --to 1.0.0 --out ./my-packet
conduit packet synthesize --package openai --from 0.28.0 --to 1.0.0 \
  --changelog ./CHANGELOG.md --docs ./MIGRATION.md --out ./my-packet/conduit-packet.json
conduit packet validate ./my-packet/conduit-packet.json
```

Schema: [`schema/conduit-packet.schema.json`](schema/conduit-packet.schema.json)

Consumers load packets with `--packet` or by dropping them into `.conduit/packets/`.

## GitHub Actions

| Workflow | Purpose |
|----------|---------|
| [`ci.yml`](.github/workflows/ci.yml) | Unit tests + dry-run apply |
| [`conduit-dependabot.yml`](.github/workflows/conduit-dependabot.yml) | Intercept Dependabot/Renovate lockfile PRs |
| [`conduit-nightly.yml`](.github/workflows/conduit-nightly.yml) | Nightly lag / module scan |
| Composite action | [`conduit/action.yml`](conduit/action.yml) |

Secrets: `OPENAI_API_KEY` (optional self-correct / synth), `GITHUB_TOKEN`.

## Layout

| Path | Role |
|------|------|
| [`conduit/`](conduit/) | Installable CLI package |
| [`conduit/src/conduit/detect/`](conduit/src/conduit/detect/) | Orchestrator, lockfile diff, modules |
| [`conduit/src/conduit/detect/modules/openai/`](conduit/src/conduit/detect/modules/openai/) | OpenAI signal workers |
| [`schema/`](schema/) | Public packet JSON Schema |
| [`examples/demo-consumer/`](examples/demo-consumer/) | Demo app on legacy openai patterns |
| [`examples/sample-packet/`](examples/sample-packet/) | Example vendor packet |

## Post-MVP backlog

1. Package export delta (`.d.ts` / `__all__`)
2. Multi-provider LLM (Anthropic / Ollama)
3. Richer AST DSL + real JS/TS AST
4. Go / multi-ecosystem polish
5. Generate tests when missing
6. More built-in vendor modules
7. `conduit packet publish` / fetch from release URLs

## License

MIT
