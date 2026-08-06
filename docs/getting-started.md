# Getting started

## Requirements

- Python 3.10+
- Git
- Optional: [`gh`](https://cli.github.com/) (only if you want Conduit to open PRs)
- Optional: an LLM (only for packet synthesis, self-correct, and smoke-test generation)

## Install

From a clone of this repo:

```bash
git clone https://github.com/xlor1009/conduit.git
cd conduit
pip install -e "./conduit[llm,dev]"
conduit --help
```

Extras:

| Extra | Installs |
|-------|----------|
| `llm` | OpenAI Python SDK (also used to talk to Ollama / custom servers) |
| `llm-anthropic` | Anthropic SDK |
| `llm-js` | tree-sitter + JS grammar for richer JS/TS transforms |
| `llm-all` | All of the above |
| `dev` | pytest |

## Demo migration (recommended first run)

The repo ships a tiny consumer app that still uses legacy OpenAI patterns, plus a sample Migration Packet.

```bash
conduit run \
  --path ./examples/demo-consumer \
  --packet ./examples/sample-packet/conduit-packet.json \
  --skip-pr
```

What you should see:

1. A packet is loaded (`openai-0.28.1-1.0.0`)
2. Files importing `openai` are pruned (typically `src/ai_client.py`)
3. Codemods rewrite model id / param names
4. Demo tests run under pytest
5. PR creation is skipped so you can inspect the working tree

```bash
git -C examples/demo-consumer diff
# or restore:
git -C examples/demo-consumer checkout -- .
```

`--skip-pr` does **not** mean dry-run. Files are actually modified and tests actually run. It only skips `git push` / `gh pr create`.

### Optional: dry-run apply only

If you want to preview transforms without writing:

```bash
conduit apply \
  --path ./examples/demo-consumer \
  --packet ./examples/sample-packet/conduit-packet.json \
  --dry-run
```

## Run on your own repository

```bash
# Typical: Dependabot already bumped the lockfile on this branch
conduit run --path /path/to/your/repo --base-ref origin/main --package openai

# Or supply a packet explicitly
conduit run --path /path/to/your/repo --packet ./packets/openai-1.0.0.json

# Apply + test locally, no PR
conduit run --path /path/to/your/repo --packet ./packets/openai-1.0.0.json --skip-pr
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--skip-pr` | Do not open a PR |
| `--no-push` | Commit locally but do not push |
| `--skip-tests` | Skip test gen + verify (not recommended) |
| `--skip-export-delta` | Skip downloading old/new package versions for export compare |
| `--max-retries N` | Self-correct attempts after test failure (default 5) |

See [CLI reference](cli-reference.md) for the full list.

## Configure an LLM (optional)

Primary edits do **not** need an LLM. Configure one if you want synthesis / self-correct / auto smoke tests.

```bash
# Local Ollama — no API key
export CONDUIT_LLM_PROVIDER=ollama
export CONDUIT_LLM_MODEL=llama3.2
```

Details: [LLM configuration](llm.md).

## Next steps

- Understand the pipeline: [Architecture](architecture.md)
- Author rules: [Migration packets](migration-packets.md)
- Wire CI: [GitHub Actions](github-actions.md)
