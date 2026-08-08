# Demo consumer

Tiny Python app still using legacy OpenAI patterns (`gpt-4-0613`, `max_tokens`, `openai==0.28.1`) so Conduit can migrate it.

From the repo root (with the Conduit venv activated):

```bash
# repo root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e "./conduit[langs,dev]"

conduit run --path ./examples/demo-consumer \
  --packet ./examples/sample-packet/conduit-packet.json \
  --demo \
  --skip-pr
```
