# Demo Consumer

Intentionally outdated OpenAI client usage for end-to-end demos of `vendor-patch`.

```bash
pip install -e ../../vendor-patch-cli
pip install pytest openai
vendor-patch run \
  --path . \
  --registry-url ../../vendor-signal-registry/dist/registry.json \
  --skip-pr
```
