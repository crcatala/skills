---
name: exa-code
description: Search for code documentation, examples, and API references using Exa AI. Use for programming questions, library usage, framework patterns, or best practices. Returns curated code snippets from GitHub repos and documentation sites.
compatibility: "Requires bun, network access, and EXA_API_KEY."
---

# Exa Code

In the commands below, `{baseDir}` is the directory containing this `SKILL.md`.

Search for code documentation, examples, and API references using Exa AI. Optimized for programming queries with high-quality, up-to-date results from GitHub repos and documentation sites.

**Use this for:** Programming questions, API docs, code examples, library usage, framework patterns, best practices.

**Not for:** General web searches, news, non-programming research. Use a general web search tool for those.

## Setup

1. Get an API key at https://exa.ai
2. Add to your shell profile (`~/.profile` or `~/.zprofile` for zsh):
   ```bash
   export EXA_API_KEY="your-api-key-here"
   ```

## Usage

```bash
bun {baseDir}/code.js "query"                                # Default (5000 tokens)
bun {baseDir}/code.js "query" --tokens 10000                 # More comprehensive
bun {baseDir}/code.js "query" --json                         # Output raw JSON
```

### Options

- `--tokens <num>` - Token budget (default: 5000, range: 1000-50000)
- `--json` - Output raw JSON response

### Token Guidelines

| Use Case | Tokens |
|----------|--------|
| Quick focused answer | 1000-2000 |
| Standard documentation lookup | 3000-5000 |
| Comprehensive examples | 8000-15000 |
| Deep dive / multiple concepts | 20000-50000 |

## Examples

```bash
# Framework patterns
bun {baseDir}/code.js "React useState hook examples"
bun {baseDir}/code.js "Next.js app router server components"

# Language features
bun {baseDir}/code.js "TypeScript generic constraints"
bun {baseDir}/code.js "Go error handling best practices"

# Library usage
bun {baseDir}/code.js "Python pandas dataframe filtering" --tokens 8000
bun {baseDir}/code.js "Express.js middleware authentication"

# API documentation
bun {baseDir}/code.js "OpenAI API function calling" --tokens 10000
bun {baseDir}/code.js "Stripe checkout session creation"
```

## Output Format

```
# Code Context: React useState hook examples

Sources: 15 results
Search time: 1.23s

---

## BlogPage Component in Next.js with Server and Client Components

https://raw.githubusercontent.com/...

[Code examples and documentation...]
```

The output includes:
- Actual code snippets from GitHub repos
- Documentation excerpts
- Best practices and patterns
- Common pitfalls and solutions
