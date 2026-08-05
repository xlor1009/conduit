# Demo consumer

Tiny Python app still using legacy OpenAI patterns (`gpt-4-0613`, `max_tokens`, `openai==0.28.1`) so Conduit can migrate it.

```bash
pip install -e "../../conduit[dev]"
pip install pytest

conduit run --path . --packet ../../examples/sample-packet/conduit-packet.json --skip-pr
```
