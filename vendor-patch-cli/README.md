# vendor-patch-cli

Downstream scanner / codemod / test verifier / PR generator that consumes
`registry.json` from the central Vendor Signal Registry.

## Install

```bash
pip install -e ./vendor-patch-cli
```

## Usage

```bash
# Approach A — central CDN (falls back to monorepo dist/registry.json offline)
vendor-patch scan --path .
vendor-patch apply --path . --dry-run
vendor-patch run --path . --vendor openai --skip-pr

# Approach B — enterprise gateway
vendor-patch run --custom-endpoint http://internal-gateway/v1/signals --path .
```

## GitHub Action

```yaml
- uses: your-org/conduit/vendor-patch-cli@main
  with:
    vendor: openai
    registry-url: https://your-org.github.io/vendor-signals/registry.json
```
