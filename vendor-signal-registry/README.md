# Vendor Signal Registry

Central ingestion workers that produce a unified `registry.json` of vendor API
breaking changes, model deprecations, and SDK major bumps.

## Quick start

```bash
cd vendor-signal-registry
pip install -e .
vendor-signals build
```

Artifact paths:

- `dist/registry.json`
- `docs/registry.json` (GitHub Pages)

## Workers

| Worker | Env flags |
|--------|-----------|
| OpenAPIDiffWorker | `OASDIFF_LIVE=1` |
| DeprecationScraperWorker | `SCRAPE_LIVE=1` |
| ModelPollingWorker | `OPENAI_API_KEY`, `UPDATE_MODEL_SNAPSHOT=1` |
| ChangelogParserWorker | `OPENAI_API_KEY` / `CHANGELOG_LLM=1` |
| SDKReleaseWorker | `SDK_RELEASE_LIVE=1`, `GITHUB_TOKEN` |

Offline fixtures under `fixtures/` are used by default so CI works without secrets.
