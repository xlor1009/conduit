# Conduit documentation

Deep dives for every major part of the system. Start with the [root README](../README.md) for the high-level overview, then use these pages when you need detail.

| Doc | Covers |
|-----|--------|
| [Getting started](getting-started.md) | Install, demo run, first real-repo run |
| [Architecture](architecture.md) | End-to-end pipeline and design principles |
| [Detection](detection.md) | Lockfile diffs, manifests (`read_installed`), version jumps |
| [Pruning & export delta](pruning-and-export-delta.md) | Import filter + package API comparison |
| [Migration packets](migration-packets.md) | Schema, `--packet` name/file, version resolution, cache, synthesis |
| [Codemods](codemods.md) | Rule types and pluggable language engines (Python, JS/TS, Java, Go) |
| [LLM configuration](llm.md) | OpenAI, Anthropic, Ollama, custom local |
| [Testing & self-correction](testing-and-self-correct.md) | Test runners, smoke-test gen, retry loop |
| [Pull requests](pull-requests.md) | Branching, `gh`, PR body |
| [Detect modules](detect-modules.md) | Plugin API, OpenAI module, scaffolding |
| [GitHub Actions](github-actions.md) | CI, Dependabot intercept, nightly, composite action |
| [CLI reference](cli-reference.md) | Every command and flag |
