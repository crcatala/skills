# Install Vexor

Use this when the `vexor` command is missing.

## Steps

1. Verify if already installed:
   ```bash
   vexor --help
   ```

2. Install with uv (recommended):
   ```bash
   uv tool install vexor && mise reshim
   ```

3. Verify the install:
   ```bash
   vexor --help
   ```

## Alternative install methods

```bash
# Using uvx (one-off execution without install)
uvx vexor --help

# Using pip (if uv unavailable)
pip install -U vexor

# Using pipx (isolated environment)
pipx install vexor
```

## If the command is still missing

- Ensure PATH includes uv's bin directory: `~/.local/share/uv/bin`
- Try running `mise reshim` to refresh shims
- Check `uv tool list` to verify installation

## After install: configure a provider

Vexor needs an embedding provider before semantic search works.

### Option 1: OpenAI (recommended, cheapest)
```bash
vexor config --set-provider openai
vexor config --set-api-key "$OPENAI_API_KEY"
# Uses text-embedding-3-small by default ($0.02/1M tokens)
```

### Option 2: Google Gemini (has free tier)
```bash
vexor config --set-provider gemini
vexor config --set-api-key "$GOOGLE_GENAI_API_KEY"
```

### Option 3: Local/Offline (free, slower)
```bash
uv tool install "vexor[local]"
vexor local --setup --model intfloat/multilingual-e5-small
```

### Verify configuration
```bash
vexor doctor    # Checks API connectivity
vexor config --show  # Shows current settings
```

## Enable BM25 Reranking (recommended)

Improves search accuracy with minimal overhead:
```bash
vexor config --rerank bm25
```

If you cannot configure credentials, ask the user to assist.
