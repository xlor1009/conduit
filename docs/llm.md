# LLM configuration

Conduit’s **apply** step does not need an LLM. Configure a model only if you want:

1. `conduit packet synthesize` from changelogs/docs  
2. Self-correction when tests fail after apply  
3. Auto-generated smoke tests when the repo has no suite  

Client code: [`conduit/src/conduit/llm/`](../conduit/src/conduit/llm/).

## Providers

| `CONDUIT_LLM_PROVIDER` | Needs API key? | Notes |
|------------------------|----------------|-------|
| `openai` | **Yes** | Cloud OpenAI |
| `anthropic` | **Yes** | Cloud Anthropic |
| `ollama` | **No** | Defaults to `http://127.0.0.1:11434/v1` |
| `custom` | **No*** | Any OpenAI-compatible HTTP server (`CONDUIT_LLM_BASE_URL` required) |

\*Unless *your* local server is configured to require a bearer token — then set `CONDUIT_LLM_API_KEY`.

Legacy alias: `openai_compatible` → treated as `custom`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `CONDUIT_LLM_PROVIDER` | `openai` \| `anthropic` \| `ollama` \| `custom` |
| `CONDUIT_LLM_MODEL` | Model id (defaults: `gpt-4o-mini`, `claude-3-5-haiku-latest`, `llama3.2`) |
| `CONDUIT_LLM_API_KEY` | Generic key (used for any provider if set) |
| `CONDUIT_LLM_BASE_URL` | Base URL for Ollama override or `custom` |
| `OPENAI_API_KEY` | Fallback when provider is `openai` |
| `ANTHROPIC_API_KEY` | Fallback when provider is `anthropic` |

### Auto-detect (when `CONDUIT_LLM_PROVIDER` unset)

1. `ANTHROPIC_API_KEY` → `anthropic`  
2. Else `OPENAI_API_KEY` → `openai`  
3. Else `CONDUIT_LLM_BASE_URL` → `custom`  
4. Else → no LLM (heuristics / skip synth enrichment)

## Examples

Install extras inside the project venv (see [Getting started](getting-started.md)):

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e "./conduit[llm,langs]"    # or [llm-anthropic] / [llm-all]
```

### Ollama (no key)

```bash
export CONDUIT_LLM_PROVIDER=ollama
export CONDUIT_LLM_MODEL=llama3.2
# optional: export CONDUIT_LLM_BASE_URL=http://127.0.0.1:11434/v1
```

### Custom local server (vLLM, LM Studio, llama.cpp server, …)

```bash
export CONDUIT_LLM_PROVIDER=custom
export CONDUIT_LLM_BASE_URL=http://127.0.0.1:1234/v1
export CONDUIT_LLM_MODEL=my-local-model
# optional if the server checks auth:
# export CONDUIT_LLM_API_KEY=local-secret
```

### OpenAI / Anthropic

```bash
export CONDUIT_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# or
export CONDUIT_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

## What happens with no LLM

| Feature | Behavior |
|---------|----------|
| Packet apply | Works fully |
| Packet synthesize | Returns seed packet / sources only (no LLM rule generation) |
| Self-correct | Heuristic string replacements from packet rules |
| Test generation | Writes a minimal deterministic smoke stub |

## Note on the OpenAI *detect module*

The **openai vendor module** (watching the `openai` SDK) is unrelated to which chat LLM you configure. `model_polling` may still use `OPENAI_API_KEY` to call OpenAI’s Models API when live mode is enabled — that is package telemetry, not Conduit’s migration LLM.

## Related docs

- [Testing & self-correction](testing-and-self-correct.md)
- [Migration packets](migration-packets.md)
