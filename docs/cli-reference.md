# CLI reference

Entry point: `conduit` (Typer app in [`conduit/src/conduit/main.py`](../conduit/src/conduit/main.py)).

```bash
conduit --help
conduit <command> --help
```

## Global options

| Option | Description |
|--------|-------------|
| `--verbose` / `-v` | Extra diagnostics (packet version sources, export-delta resolve details, etc.) |

Place before or after the subcommand:

```bash
conduit -v run --path . --packet openai
conduit run -v --path . --packet openai
```

---

## `conduit run`

Full pipeline: detect → prune → export delta → packet → apply → test gen → verify → PR.

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `.` | Repo root (must be a directory). On Windows prefer forward slashes or quotes if backslashes get stripped. |
| `--base-ref` | none | Git ref for lockfile diff (e.g. `origin/main`) |
| `--package` | auto | Package to migrate |
| `--module` | auto | Restrict detect modules (if omitted and a package name is known, Conduit uses a matching detect module when one exists) |
| `--packet` | cache/synth | Path to an existing `conduit-packet.json`, **or** a package name (e.g. `openai`, `stripe`) |
| `--skip-tests` | false | Skip test gen + verify |
| `--skip-pr` | false | Do not open a PR |
| `--no-push` | false | Do not push remote |
| `--skip-modules` | false | Lockfile detect only |
| `--skip-lockfile` | false | Modules only |
| `--skip-export-delta` | false | Skip export compare / prune |
| `--max-retries` | `5` | Self-correct attempts |
| `--verbose` / `-v` | false | Same as global verbose |

### `--packet` resolution

1. If the value is an **existing file** → load that packet JSON.
2. Otherwise treat it as a **package name** → same idea as `--package <name>`: detect/synthesize a packet for that package.
3. If both `--packet <file>` and `--package` disagree on the package field, the **packet file** wins (with a warning).
4. If `--packet <name>` and `--package` disagree, **`--package`** wins (with a warning).

### Version defaults and warnings

When synthesizing a packet (not loading a file), Conduit resolves `from_version` / `to_version` from detect signals, then manifests, then `DEPENDENCY_BUMP` rules. Placeholder versions (`0.0.0` / `1.0.0`) or the offline openai fixture trigger a **yellow warning**. Use `-v` to see sources (`manifest`, `signal`, `rule`, `fixture`, `placeholder`).

---

## `conduit detect`

Lockfile diff + vendor modules → print signals (or `--json`).

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `.` | Repo root |
| `--base-ref` | none | Diff base |
| `--module` | all | Single module name |
| `--skip-modules` | false | |
| `--skip-lockfile` | false | |
| `--majors-only` / `--all-bumps` | majors-only | Filter version jumps |
| `--json` | false | Machine-readable signals |

Exit `0` if any signals, else `1`.

---

## `conduit apply`

Apply a packet only.

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `.` | Repo root |
| `--packet` | required | Packet **file** path |
| `--dry-run` | false | Print changes without writing |

---

## `conduit verify`

Run tests + self-correct using a packet for heuristic/LLM context.

| Option | Default | Description |
|--------|---------|-------------|
| `--path` | `.` | Repo root |
| `--packet` | openai fixture if omitted | Packet **file** path |
| `--max-retries` | `5` | |

---

## `conduit module`

### `module list`

List built-in / entry-point modules and whether they apply to installed manifests.

### `module new`

Scaffold a detect module.

| Option | Description |
|--------|-------------|
| `name` | Module name (argument) |
| `--package` | Package name (defaults to name) |
| `--ecosystem` | `pypi` (default) etc. |
| `--path` | Conduit package root or out dir |
| `--out-of-tree` | Standalone package layout |

---

## `conduit packet`

### `packet init`

Scaffold an empty packet directory / file.

| Option | Description |
|--------|-------------|
| `--package` | required |
| `--from` / `--to` | versions |
| `--ecosystem` | `pypi` default |
| `--out` | output directory |

### `packet synthesize`

Build rules from `--changelog` / `--docs` (LLM if configured).

### `packet validate`

JSON Schema validation; exit non-zero on errors.

### `packet show`

Pretty-print packet JSON.

---

## Environment (global)

See [LLM configuration](llm.md) for `CONDUIT_LLM_*` and provider keys.

`GH_TOKEN` / `GITHUB_TOKEN` used by `gh` when opening PRs.
