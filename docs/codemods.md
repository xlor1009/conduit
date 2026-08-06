# Codemods

The patcher applies packet `rules` to the pruned file set. Implementation: [`conduit/src/conduit/patcher/`](../conduit/src/conduit/patcher/).

## Common fields

Most file-targeting rules include:

```json
"target_files": ["*.py", "src/**/*.ts"]
```

Globs match basename or repo-relative path (`fnmatch`).

## Rule catalog

### `EXACT_STRING_REPLACE`

```json
{
  "type": "EXACT_STRING_REPLACE",
  "target_files": ["*.py", "*.ts", "*.js", "*.yaml", "*.yml", "*.json", ".env*"],
  "match": "gpt-4-0613",
  "replace": "gpt-4o"
}
```

### `REGEX_REPLACE`

```json
{
  "type": "REGEX_REPLACE",
  "target_files": ["*.py"],
  "pattern": "OpenAI\\(\\s*\\)",
  "replace": "OpenAI()"
}
```

### `AST_PARAM_RENAME`

Renames a keyword argument (Python via **libcst**) or object property / `=` style (JS/TS heuristics or tree-sitter helpers).

```json
{
  "type": "AST_PARAM_RENAME",
  "target_files": ["*.py", "*.ts", "*.js"],
  "function_target": "chat.completions.create",
  "old_param": "max_tokens",
  "new_param": "max_completion_tokens"
}
```

`function_target` may be a dotted path; matching is suffix-aware (calls ending in `.create` can match).

### `AST_IMPORT_REWRITE`

Python uses libcst `Import` / `ImportFrom` transforms. JS/TS uses import/require string rewrites (tree-sitter optional).

```json
{
  "type": "AST_IMPORT_REWRITE",
  "target_files": ["*.py"],
  "old_import": "openai",
  "new_import": "openai"
}
```

### `AST_ATTR_RENAME`

```json
{
  "type": "AST_ATTR_RENAME",
  "target_files": ["*.py"],
  "old_attr": "openai.ChatCompletion",
  "new_attr": "openai.chat.completions"
}
```

### `AST_CALL_REWRITE`

```json
{
  "type": "AST_CALL_REWRITE",
  "target_files": ["*.py"],
  "old_callee": "openai.ChatCompletion.create",
  "new_callee": "openai.chat.completions.create"
}
```

### `DEPENDENCY_BUMP`

Updates manifests (`requirements.txt`, `pyproject.toml`, `package.json`). Always considered even if the file was not import-pruned.

```json
{
  "type": "DEPENDENCY_BUMP",
  "package": "openai",
  "from_version": "0.28.1",
  "to_version": "1.0.0",
  "ecosystems": ["pip", "pyproject"]
}
```

## Language engines

| Language | Engine |
|----------|--------|
| Python | libcst for AST rules; string/regex otherwise |
| JS/TS | Prefer tree-sitter when `llm-js` extra installed; regex/string fallbacks always available |
| YAML/JSON/env | String / regex rules only |

## Apply CLI

```bash
conduit apply --path . --packet ./conduit-packet.json
conduit apply --path . --packet ./conduit-packet.json --dry-run
```

`conduit run` calls the same engine after prune + export delta.

## Safety rails

- Hard directory exclusions (see [Pruning](pruning-and-export-delta.md))
- Optional vendor-context check (`file_has_vendor_context`) so rules don’t fire in unrelated files
- Dry-run mode prints planned edits without writing

## Related docs

- [Migration packets](migration-packets.md)
- [Pruning & export delta](pruning-and-export-delta.md)
