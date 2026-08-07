# Testing & self-correction

After apply, Conduit verifies the consumer repo still works.

## Test runner detection

[`test_runner.py`](../conduit/src/conduit/test_runner.py) looks for:

| Signal | Command |
|--------|---------|
| `pytest.ini`, `conftest.py`, `[tool.pytest`, or `tests/test_*.py` | `pytest -q` (or `python -m pytest -q`) |
| `package.json` scripts.test | `npm test --silent` |
| `go.mod` | `go test ./...` |

If nothing is detected, the runner currently treats the suite as a soft pass — unless test generation creates files first (see below).

## Generating tests when missing

[`test_gen.ensure_tests`](../conduit/src/conduit/test_gen.py) runs before verify when you use `conduit run` (unless `--skip-tests`):

1. If a runner **and** test files already exist → no-op  
2. Else if an LLM is configured → ask it for a minimal smoke test JSON (`files` map)  
3. Else write a **deterministic stub**:
   - Python: `tests/test_conduit_migration.py` (import package + marker assert)
   - npm ecosystem: `conduit_migration.test.js`

Runners already cover pytest, `npm test`, and `go test ./...`. Java/Maven suites are not auto-detected yet — pass existing tests in-repo or generate via LLM.

Generated paths are included in the patch report / PR body.

## Self-correction loop

[`self_correct.verify_with_self_correct`](../conduit/src/conduit/self_correct.py):

1. Run tests  
2. On failure, up to `--max-retries` (default **5**):
   - Collect traceback file paths + nearby source/tests  
   - If LLM configured → request `{"files": {relpath: new_contents}}` and write them  
   - Else apply heuristic replaces derived from packet `EXACT_STRING_REPLACE` / `AST_PARAM_RENAME`  
3. Re-run tests  
4. If still failing after retries → `conduit run` aborts PR creation (exit code 2)

## Commands

```bash
conduit verify --path . --packet ./conduit-packet.json --max-retries 5
conduit run ... --max-retries 3
conduit run ... --skip-tests    # apply only; not recommended for real migrations
```

## Tips

- Prefer real unit tests in the consumer repo; generated smoke tests only prove importability.
- For local iteration without burning API quota, leave LLM unset and rely on packet quality + heuristics.
- CI should pass `CONDUIT_LLM_*` secrets only when you want the repair loop online.

## Related docs

- [LLM configuration](llm.md)
- [Pull requests](pull-requests.md)
- [Getting started](getting-started.md)
