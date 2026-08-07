# Conduit package

Installable CLI with pluggable language engines (Python, JS/TS, Java, Go).
See the [root README](../README.md) for quick start and docs.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[llm,langs,dev]"
conduit --help
```

Use the `langs` extra for tree-sitter grammars; without it, AST rules still run via regex/string fallbacks.
