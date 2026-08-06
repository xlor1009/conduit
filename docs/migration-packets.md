# Migration packets

A **Migration Packet** is a JSON document (`conduit-packet.json`) that lists deterministic codemod rules for one package version jump.

Schema: [`schema/conduit-packet.schema.json`](../schema/conduit-packet.schema.json)

## Minimal shape

```json
{
  "packet_id": "openai-0.28.1-1.0.0",
  "package": "openai",
  "ecosystem": "pypi",
  "from_version": "0.28.1",
  "to_version": "1.0.0",
  "sources": [{ "url": "https://…", "kind": "docs" }],
  "notes": "Optional human notes",
  "rules": [ /* see Codemods */ ]
}
```

`ecosystem` is one of: `pypi`, `npm`, `go`, `other`.

## Where packets come from (`ensure_packet`)

Resolution order in `conduit run`:

1. **`--packet path`** — explicit file
2. **Cache** — `.conduit/packets/{package}-{from}-{to}.json`
3. **Synthesize from detect signals** — fold `suggested_rules` into a packet
4. **OpenAI fixture fallback** — demo packet when package is `openai` and rules are still empty

Cached after synthesis so the next run is instant.

## Authoring CLI

```bash
# Empty scaffold
conduit packet init \
  --package openai --from 0.28.0 --to 1.0.0 \
  --ecosystem pypi --out ./my-packet

# Fill rules from changelog/docs (uses LLM if configured; otherwise keeps seed/empty rules)
conduit packet synthesize \
  --package openai --from 0.28.0 --to 1.0.0 \
  --changelog ./CHANGELOG.md --docs ./MIGRATION.md \
  --out ./my-packet/conduit-packet.json

conduit packet validate ./my-packet/conduit-packet.json
conduit packet show ./my-packet/conduit-packet.json
```

## Rule types (summary)

| Type | Purpose |
|------|---------|
| `EXACT_STRING_REPLACE` | Literal find/replace |
| `REGEX_REPLACE` | Regex replace |
| `AST_PARAM_RENAME` | Rename kwarg / object key near a call |
| `AST_IMPORT_REWRITE` | Rewrite import module path |
| `AST_ATTR_RENAME` | Rename attribute chain |
| `AST_CALL_REWRITE` | Rewrite call callee path |
| `DEPENDENCY_BUMP` | Bump version in manifests |

Full field docs: [Codemods](codemods.md).

## Example (shipped sample)

See [`examples/sample-packet/conduit-packet.json`](../examples/sample-packet/conduit-packet.json) — model string replace + `max_tokens` → `max_completion_tokens` + dependency bump.

## Vendor vs consumer workflow

| Role | Typical action |
|------|----------------|
| Vendor / maintainer | Publish a packet next to a breaking release (or open a PR to consumer orgs) |
| Consumer | Drop packet in `.conduit/packets/` or pass `--packet`; run `conduit run` |

There is not yet a `conduit packet publish` registry command — share packets via git/HTTP for now.

## Related docs

- [Codemods](codemods.md)
- [LLM configuration](llm.md) (for `packet synthesize`)
- [CLI reference](cli-reference.md)
