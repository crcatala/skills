---
name: vexor
description: Semantic file discovery via `vexor`. Use whenever locating where something is implemented/loaded/defined in a medium or large repo, or when the file location is unclear. Prefer this over manual browsing.
compatibility: "Requires the vexor CLI (uv tool install vexor)."
---

# Vexor - Semantic File Search

Find files by intent (what they do), not exact text. Uses vector embeddings to understand your query and return the most relevant files.

**Use this for:** Finding where features are implemented, locating config files, understanding code structure, any "where is X?" question.

**Use grep/ripgrep instead for:** Simple exact text matches, regex patterns.

## Command

```bash
vexor "<QUERY>" [--path <ROOT>] [--mode <MODE>] [--ext .py,.md] [--top 5]
```

## Common Flags

| Flag | Description |
|------|-------------|
| `--path/-p` | Root directory (default: current dir) |
| `--mode/-m` | Indexing strategy (see below) |
| `--ext/-e` | Limit file extensions (e.g., `.py,.md`) |
| `--exclude-pattern` | Exclude paths (gitignore-style, repeatable) |
| `--top/-k` | Number of results (default: 5) |
| `--include-hidden` | Include dotfiles |
| `--no-cache` | In-memory only, skip index cache |
| `--format` | `rich` (default), `porcelain` (TSV), `porcelain-z` (NUL) |

## Modes (pick the cheapest that works)

| Mode | Speed | Use Case |
|------|-------|----------|
| `auto` | Varies | Smart routing by file type (default) |
| `name` | ⚡ Fastest | Filename-only matching |
| `head` | Fast | First lines only |
| `code` | Medium | AST-aware chunking for `.py/.js/.ts` |
| `outline` | Medium | Markdown headings/sections |
| `full` | Slowest | Full file content (highest recall) |

## Examples

```bash
# Find where authentication is handled
vexor "user authentication middleware"

# Search Python files for config loading
vexor "config loader" --mode code --ext .py

# Search docs by headings
vexor "deployment process" --path docs --mode outline --ext .md

# Exclude test files
vexor "database connection" --exclude-pattern tests/** --exclude-pattern "**/*_test.py"
```

## Tips

- **First search indexes files** (may take 1-2 minutes). Subsequent searches are fast (<1 sec).
- Use `--mode code` for codebases (understands function/class boundaries).
- Use `--mode outline` for documentation (understands heading hierarchy).
- Results include: similarity score, file path, line numbers, preview snippet.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `vexor` not found | See [references/install-vexor.md](references/install-vexor.md) |
| Config/API issues | Run `vexor doctor` to diagnose |
| Need hidden files | Add `--include-hidden` |
| Need gitignored files | Add `--no-respect-gitignore` |

## When to Use

| Scenario | Tool |
|----------|------|
| "Where is X implemented?" | **vexor** |
| "Find the config for Y" | **vexor** |
| Exact string match | grep/ripgrep |
| Regex pattern | grep/ripgrep |
