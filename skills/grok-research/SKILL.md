---
name: grok-research
description: Deep research via Grok 4.6 — agentic web + X (Twitter) search. The model autonomously plans searches, browses pages, follows up, and synthesizes comprehensive answers with inline citations. Use for research questions that need synthesized answers, multi-step investigation, real-time info, social sentiment, or travel/comparison planning.
compatibility: "Requires python3, network access, and XAI_API_KEY."
---

# Grok Research

In the commands below, `{baseDir}` is the directory containing this `SKILL.md`.

Deep agentic research powered by Grok 4.6 via the xAI API. Unlike traditional search APIs that return raw links/snippets, Grok acts as an autonomous researcher — it plans a search strategy, browses pages, makes follow-up queries, cross-references sources, and returns a synthesized answer with inline citations.

**Cost**: depends on token volume and agentic tool calls. Use `--model grok-4.3` for a lower-cost alternative.

## Setup

1. Get an API key at https://console.x.ai/
2. Add to your shell profile:
   ```bash
   export XAI_API_KEY="your-api-key-here"
   ```
3. Install or upgrade the SDK (the skill requires `xai-sdk` 1.19.0 or newer):
   ```bash
   pip install --upgrade 'xai-sdk>=1.19.0'
   ```

## Usage

```bash
python3 {baseDir}/search.py "your research query"
```

### Options

| Option | Description |
|--------|-------------|
| `--tools web` | Web search only (no X/Twitter) |
| `--tools x` | X search only (no web) |
| `--tools both` | Both web + X search (default) |
| `--model MODEL` | Model to use (default: `grok-4.6`; use `grok-4.3` for lower cost) |
| `--reasoning-effort low\|medium\|high\|xhigh` | Reasoning effort (default: `high`; `xhigh` requires Grok 4.6 or a newer compatible model) |
| `--no-reasoning` | Deprecated compatibility flag; maps to `--reasoning-effort low` because Grok 4.6 cannot disable reasoning |
| `--max-turns N` | Optional agentic-search cap (fewer turns = faster/cheaper); omit it for the provider default |
| `--profile general\|factual\|comparison\|news\|social\|literature` | Research policy; `general` verifies the premise and is the sensible default for most tasks |
| `--format prose\|claims` | Output normal prose or a strict claims-and-evidence JSON object |
| `--system "prompt"` | Additional system guidance appended to the selected profile |
| `--verbose` | Show tool calls on stderr; reasoning totals remain in the footer |
| `--json` | Output structured JSON (content, citations, usage, tool_calls) |

### Examples

```bash
# Deep research question
python3 {baseDir}/search.py "What are the latest developments in WebAssembly?"

# Web-only (skip X/Twitter)
python3 {baseDir}/search.py "Python 3.13 new features" --tools web

# Social sentiment (X/Twitter focused)
python3 {baseDir}/search.py "What are developers saying about Bun runtime?" --tools x

# Travel planning
python3 {baseDir}/search.py "10-day Japan trip April 2026, cherry blossoms, budget tips" --tools web

# Comparison research
python3 {baseDir}/search.py "Compare Zed vs Cursor vs VS Code for AI coding 2026"

# Current events / news
python3 {baseDir}/search.py "biggest news stories this week"

# Use a comparison policy (the default general policy fits most research tasks)
python3 {baseDir}/search.py "best terminal emulators 2026" --profile comparison --system "Focus on Linux."

# Emit auditable claims with source-by-source supporting evidence
python3 {baseDir}/search.py "Is Deno 3 released?" --profile factual --format claims

# Quick, bounded factual lookup
python3 {baseDir}/search.py "who won the Super Bowl?" --model grok-4.3 --max-turns 2

# Lower reasoning effort for faster/cheaper research
python3 {baseDir}/search.py "summarize latest AI model releases" --reasoning-effort low --max-turns 2

# Structured JSON output (for piping/processing)
python3 {baseDir}/search.py "Anthropic Claude latest updates" --json
```

### Output

The default `general` profile first verifies the premise of the request. It reports unsupported or negative findings with search scope and uncertainty rather than treating missing results as proof of nonexistence.

**Turn guidance:** omit `--max-turns` for normal, comparative, or claims-and-evidence research—the provider can use the depth it needs. Use `2-3` only for a simple, known-answer lookup. For premise verification or `--format claims`, use at least `6` if you need a cap; `8-12` is safer for comparisons or disputed/negative findings.

The default prose format streams a synthesized answer with `[[1]](url)` style inline citations, followed by metadata. `--format claims` returns a JSON object with precise claims, confidence, source-by-source support, and limitations. The CLI rejects malformed claims output, including empty claims arrays, missing evidence, invalid confidence/source types, empty fields, and non-HTTP(S) source URLs.

```
[Synthesized answer with inline citations...]

---
Model: grok-4.6 | Reasoning effort: high | Time: 42.3s
Tokens — prompt: 17000, completion: 1800, reasoning: 1500, cached: 9000
Tools used: {'SERVER_SIDE_TOOL_WEB_SEARCH': 8, 'SERVER_SIDE_TOOL_X_SEARCH': 2}
Citations (45):
  https://example.com/source1
  ...
```

### Pricing

- **Grok 4.6 tokens**: $2.00/1M input, $0.50/1M cached input, $6.00/1M output
- **Grok 4.3 tokens**: $1.25/1M input, $0.20/1M cached input, $2.50/1M output
- **Web Search**: $0.005 per tool call
- **X Search**: $0.005 per tool call

See [xAI's pricing page](https://docs.x.ai/developers/pricing) for current rates.
