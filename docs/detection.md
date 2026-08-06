# Detection

Detection answers: **which packages jumped versions, and what vendor signals exist?**

Command: `conduit detect` (also the first stage of `conduit run`).

## Sources

### 1. Lockfile / manifest git diff

Conduit diffs watched files against `--base-ref` (or `HEAD~1` / merge-base heuristics when omitted):

- `requirements.txt`, `requirements-dev.txt`
- `pyproject.toml`
- `package.json`, `package-lock.json`
- `poetry.lock`, `Pipfile.lock`
- `go.mod`

Only packages whose declared version **changed** become `VersionJump` signals. Unchanged dependencies are ignored (Tier 1 isolation).

By default only **major** bumps are treated as migration candidates (`--majors-only`, on by default). Use `--all-bumps` to include minor/patch.

Ecosystem parsers today:

| File | Quality |
|------|---------|
| `requirements.txt` | Solid (`pkg==ver` / operators) |
| `package.json` | Solid (deps / dev / peer) |
| `go.mod` | Supported |
| `pyproject.toml` | Best-effort regex (not full TOML) |
| `package-lock.json` / `poetry.lock` | Watched; parsing is weaker — prefer comparing manifest side when possible |

Implementation: [`conduit/src/conduit/detect/lockfile_diff.py`](../conduit/src/conduit/detect/lockfile_diff.py).

### 2. Vendor detect modules

Modules implement `DetectModule` and emit `ChangeSignal`s (renames, deprecations, suggested rules). Built-in: **`openai`**.

```bash
conduit detect --path . --module openai
conduit detect --path . --skip-lockfile --module openai   # modules only
conduit detect --path . --skip-modules                    # lockfile only
conduit detect --path . --json                           # machine-readable
```

See [Detect modules](detect-modules.md).

## Signals → package selection

`conduit run` picks a package via:

1. `--package` if set
2. Else prefer `openai` if present in signals
3. Else first package among signals

Those signals seed packet synthesis when no cached/explicit packet exists.

## Dependabot / Renovate intercept

In CI, pass the PR base so the lockfile diff sees the bump:

```bash
conduit run --path . --base-ref origin/main --skip-pr
```

Workflow: [GitHub Actions](github-actions.md).

## Related docs

- [Architecture](architecture.md)
- [Detect modules](detect-modules.md)
- [CLI reference](cli-reference.md)
