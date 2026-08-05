# Conduit — Vendor Signal Monitoring & Patch Engine

Open-source, automated API maintenance ("Dependabot for API Breaking Changes & Model Deprecations").

## Architecture

**Approach A — Static Community Registry**

1. Central workers in `vendor-signal-registry/` ingest OpenAPI diffs, deprecation pages, model lists, changelogs, and SDK releases.
2. Signals are normalized into `registry.json` (see [`schema.json`](schema.json)).
3. A GitHub Actions cron (`0 */6 * * *`) rebuilds and publishes the file to GitHub Pages:
   `https://your-org.github.io/vendor-signals/registry.json`

**Approach B — Hybrid Enterprise Opt-In**

Consumer CI passes `--custom-endpoint <url>` to bypass the public CDN and query an internal gateway.

Downstream `vendor-patch-cli` scans repos, applies codemods, runs tests (with optional LLM self-correction), and opens PRs.

```text
vendor-signal-registry  --(cron)-->  registry.json (Pages/CDN)
                                           |
                                           v
consumer repo  <-- vendor-patch scan/apply/run (GitHub Action)
```

## Packages

| Path | Role |
|------|------|
| [`vendor-signal-registry/`](vendor-signal-registry/) | 5 ingestion workers + pipeline + Pages artifact |
| [`vendor-patch-cli/`](vendor-patch-cli/) | Scanner, patch engine, test verifier, PR generator |
| [`examples/demo-consumer/`](examples/demo-consumer/) | Tiny Python app still on `gpt-4-0613` for demos |

## Quick start

```bash
# 1. Build the central registry (fixture / offline mode)
pip install -e ./vendor-signal-registry
python -m vendor_signal_registry.pipeline build

# 2. Install the consumer CLI
pip install -e ./vendor-patch-cli
pip install pytest

# 3. Scan the demo consumer against the local registry
vendor-patch scan \
  --path ./examples/demo-consumer \
  --registry-url ./vendor-signal-registry/dist/registry.json

# 4. Full local run (patch + tests + self-correct, no PR)
vendor-patch run \
  --path ./examples/demo-consumer \
  --registry-url ./vendor-signal-registry/dist/registry.json \
  --vendor openai \
  --skip-pr
```

## Workers (registry)

| Worker | Purpose | Live flags |
|--------|---------|------------|
| `OpenAPIDiffWorker` | Diff OpenAPI specs for removed paths / renamed params | `OASDIFF_LIVE=1` |
| `DeprecationScraperWorker` | Scrape deprecation tables | `SCRAPE_LIVE=1` |
| `ModelPollingWorker` | Diff `/v1/models` vs snapshot | `OPENAI_API_KEY`, `UPDATE_MODEL_SNAPSHOT=1` |
| `ChangelogParserWorker` | Parse RSS/changelog for signature renames | `OPENAI_API_KEY` / `CHANGELOG_LLM=1` |
| `SDKReleaseWorker` | Detect SDK major / rc bumps | `SDK_RELEASE_LIVE=1`, `GITHUB_TOKEN` |

Fixtures under `vendor-signal-registry/fixtures/` keep CI deterministic without secrets.

## CLI modes

```bash
# Approach A
vendor-patch run --registry-url https://your-org.github.io/vendor-signals/registry.json

# Approach B
vendor-patch run --custom-endpoint http://internal-gateway/v1/signals
```

## Environment

| Variable | Used by |
|----------|---------|
| `OPENAI_API_KEY` | Model polling, changelog LLM parse, test self-correction |
| `GITHUB_TOKEN` | Live SDK release lookups / `gh pr create` |
| `OASDIFF_LIVE` / `SCRAPE_LIVE` / `SDK_RELEASE_LIVE` | Enable live network paths |

## GitHub Actions

- Registry build + Pages: [`.github/workflows/build-registry.yml`](.github/workflows/build-registry.yml)
- Consumer composite action: [`vendor-patch-cli/action.yml`](vendor-patch-cli/action.yml)

## License

MIT
