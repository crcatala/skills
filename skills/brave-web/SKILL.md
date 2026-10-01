---
name: brave-web
description: Fast web search and safe URL extraction through Brave Search. Use for current facts, documentation, news, targeted domain searches, and reading article/PDF URLs as markdown. Lightweight and browser-free.
compatibility: "Requires bun (or Node.js 22+), network access, and BRAVE_API_KEY (or BRAVE_SEARCH_API_KEY). --context needs a Brave plan that includes LLM Context. Dependencies install on first run."
---

# Brave Web Tools

In the commands below, `{baseDir}` is the directory containing this `SKILL.md`.

Upstream MIT attribution is bundled in
[THIRD_PARTY_NOTICE.md](THIRD_PARTY_NOTICE.md) for standalone installations.

Fast, browser-free web access with Brave Search and readable URL extraction. It is the quick research primitive; use `exa-code` for code-specific research, `grok-research` for multi-source synthesis, and `agent-browser` when a page requires an interactive browser.

## Setup

Requires Node.js 22+ (the local PDF extractor, `unpdf`, requires it) and a Brave Search API key
(`BRAVE_API_KEY`, or `BRAVE_SEARCH_API_KEY` as used by Brave's own tools). `--context` additionally
needs a plan that includes LLM Context (Brave's Search plan); without it the API answers
`OPTION_NOT_IN_PLAN` and the script says so.

```bash
export BRAVE_API_KEY="your-api-key"
cd {baseDir} && bun install  # runs automatically on first invocation as well
```

## Search

```bash
# Basic search (5 results)
bun {baseDir}/search.js "JavaScript async await"

# Recent results for Germany
bun {baseDir}/search.js "AI policy" -n 10 --country DE --freshness pw

# Search only authoritative documentation; domains may be repeated
bun {baseDir}/search.js "React useEffect" --site react.dev --site developer.mozilla.org

# Exclude low-signal sources
bun {baseDir}/search.js "database migration patterns" --exclude-site reddit.com --exclude-site medium.com

# Fetch three pages concurrently, print 5k previews, and cache full text
bun {baseDir}/search.js "OAuth PKCE guide" --site oauth.net --content

# Machine-readable results with 10k page previews; reuse local content for 15 minutes
bun {baseDir}/search.js "OAuth PKCE guide" --content --content-limit 10000 --cache-ttl 900 --json
```

### Query-focused passages (`--context`)

```bash
# Best default for "answer this question / debug this error": relevant passages from ~5 pages in one fast call
bun {baseDir}/search.js "Next.js 15 breaking changes migration guide" --context

# Official docs only, bigger budget, last month
bun {baseDir}/search.js "axum middleware" --context --site docs.rs --max-tokens 8192 --freshness pm
```

`--context` uses Brave's LLM Context endpoint: the server extracts and ranks the passages of each
result that match the query (headings and code blocks preserved) and returns them within a token
budget (about 4 chars per token). It replaces `--content` for research questions: it is faster
(under a second versus several), query-focused instead of "first N characters of the page", and
fetches nothing locally. It cannot read a specific URL or a whole page; use `content.js` for that.
`--context` cannot be combined with `--content`.

| Option | Description |
|---|---|
| `--context` | Return query-focused page passages instead of snippets (needs a plan with LLM Context) |
| `--max-tokens <num>` | With `--context`: approximate passage budget (default 4096; 1024-32768) |
| `--threshold <mode>` | With `--context`: `strict` (default), `balanced`, `lenient`, or `disabled` |

### Options

| Option | Description |
|---|---|
| `-n <num>` | Result count (default 5; max 20, or 50 with `--context`) |
| `--content` | Fetch result pages concurrently (default 3), print a preview, and save full text in the one-hour cache |
| `--content-limit <chars>` | Preview length (default 5k; maximum 100k) |
| `--content-concurrency <num>` | Simultaneous page fetches (default 3; maximum 10) |
| `--content-timeout-ms <ms>` | Per-page timeout (default 15s; maximum 120s) |
| `--cache-ttl <seconds>` | With `--content`, accept matching locally cached content up to this age; `0` forces a live fetch |
| `--json` | Emit structured JSON instead of human-readable result blocks |
| `--country <code>` | Two-letter result country (default `US`) |
| `--freshness <period>` | `pd`, `pw`, `pm`, `py`, or `YYYY-MM-DDtoYYYY-MM-DD` |
| `--site <domain>` | Include only this domain/subdomains (repeatable) |
| `--exclude-site <domain>` | Exclude this domain/subdomains (repeatable) |

Domain constraints are sent to Brave (as `site:` filters, or Goggles with `--context`) **and enforced locally** on returned URLs. This prevents a loosely honored search constraint from leaking an excluded host into the result list. `--freshness` is a Brave API source-age filter; `--cache-ttl` controls only this skill's local extracted-content cache.

## Read a URL

```bash
# Read an article or text-based PDF; first 30k chars are shown
bun {baseDir}/content.js https://example.com/article
bun {baseDir}/content.js https://example.com/report.pdf

# Use an exact textual response rather than readability (API/JSON/text only)
bun {baseDir}/content.js https://api.example.com/openapi.json --raw

# Continue a large cached page
bun {baseDir}/content.js --cache a1b2c3d4e5f67890 --offset 30000 --limit 30000

# Reuse a locally cached URL for up to 15 minutes; use 0 to force a live fetch
bun {baseDir}/content.js https://example.com/article --cache-ttl 900

# Find a passage without loading the full page into context
bun {baseDir}/content.js --cache a1b2c3d4e5f67890 --find "retry timeout"
bun {baseDir}/content.js --cache a1b2c3d4e5f67890 --find "instalation steps" --find-mode fuzzy
```

`content.js` saves full extracted content in `${BRAVE_WEB_CACHE_DIR:-/tmp/brave-web-cache}` for one hour (32 entries, directory/file permissions are restricted on POSIX). Output includes a `Cache-ID`; use it to page content or find passages. This avoids repeatedly fetching long documents and avoids placing a whole long page in the model context.

| Option | Description |
|---|---|
| `--raw` | Return the exact textual HTTP body instead of article extraction |
| `--cache <id>` | Read a cached result instead of fetching a URL |
| `--cache-ttl <seconds>` | For a URL, use content cached up to that age; for a cache ID, require it to be no older than that age. The cache itself retains entries for one hour. |
| `--offset <chars>` / `--limit <chars>` | Select a content slice; default limit 30k, maximum 100k |
| `--find <text>` | Return matching passages with nearby context |
| `--find-mode <mode>` | `exact`, `case-insensitive` (default), or `fuzzy` |

## Safety and routing

- **YouTube transcript requests:** When a YouTube URL or video ID is present and the user wants to understand, summarize, quote, translate, or obtain the spoken text, prefer the `youtube-transcript-api` skill. It retrieves native captions through Supadata and requires `SUPADATA_API_KEY`; it does not download media or request generated transcripts. Use Brave for web research about a YouTube page only when captions are not the goal or the user explicitly asks for web searching.
- Only `http:` and `https:` URLs are accepted. Localhost, internal names, private/link-local/reserved IP ranges, and private DNS answers are blocked. Redirect destinations are followed manually and validated before the next request.
- These checks are DNS **preflight** protections, not DNS-rebinding-proof address pinning: the HTTP client resolves a hostname again when connecting. Run this skill only with network egress policy that independently blocks metadata and private/internal ranges when arbitrary hostile URLs are in scope.
- Responses are bounded to 5MB. PDFs are text-extracted locally with `unpdf`; scanned PDFs with no text require a separate OCR-capable workflow.
- GitHub repository/file/tree URLs are **not scraped as HTML**. The command returns `gh`/shallow-clone guidance (and fetches a root repository overview through `gh` when available). Use `gh` or `git` for actual GitHub content.

## When not to use it

- **GitHub code, issues, PRs:** use `gh` or `git`, as the automatic GitHub route says.
- **Interactive/login/JavaScript-only pages:** use `agent-browser`.
- **Deep, multi-hop research or a cited synthesis:** use `grok-research`.
- **Programming API examples:** prefer `exa-code`.
