# Changelog

All notable changes are recorded here. The repository is versioned as a whole
with git tags (`vMAJOR.MINOR.PATCH`); individual skills are not versioned
separately unless they carry `metadata.version` for their own breaking changes.

## [Unreleased]

### Changed
- `independent-pr-review`: new `antigravity` harness that runs Google's Antigravity CLI in print mode
  (`--model`, `--effort`, two turns in one conversation), and a built-in `antigravity-neon` preset
  (`gemini-4-neon`, medium). The CLI is found through `ANTIGRAVITY_CLI`, `agy` or `antigravity` on `PATH`,
  or the copy T3 Code manages under `<T3 home>/tools/antigravity-acp/`. Before a run, the script checks the
  CLI is found and signed in, and otherwise fails that reviewer at once with what to do, including that a
  T3 Code sign-in does not carry over to the CLI. `--list` shows the CLI's path and whether it is ready.
- `github-pr-screenshots`: uploads with the GitHub CLI's built-in `--attach` flag (gh 2.99.0+) instead of the
  `gh-attach` extension, which is no longer installed or used. Files go to GitHub's user-attachments storage, where
  the web editor's uploads go, instead of commits on `refs/uploads/issues/<n>` refs in the repository. The body file
  references files by relative path and `gh` rewrites them to upload URLs. Video renders as a player. Adds when to
  pick a GIF or a video, and `references/gif.md` for making a GIF with ffmpeg from a video or frames (replacing
  gh-attach's `--gif`) and fitting it under the 10 MB image limit.
- `image-gen`: the default OpenAI model is now `gpt-image-2.6-flare`. New options for GPT Image 2.6:
  `--complexity`, SVG output (`--format svg`, `--svg-model`), animated GIF output (`--format gif`,
  `--frames`, `--frame-duration`), and markup-guided edits (`--markup`, also on 2.5). Documents
  that 2.6 uses 3–4x more output tokens than 2.5 at low and medium quality.

### Added
- `anatomy`: user-invoked skill that builds interactive isometric SVG figures
  explaining an idea as a physical machine, derived from wheresryan22/anatomy at
  `1482e84`. Gallery publishing and session-log reading are removed; built
  example pages and PDFs are not shipped.
- `independent-pr-review`: user-invoked. Runs one or more reviewers (codex, claude or pi,
  each with a configured model and effort) without a UI and in parallel; each reviews the
  branch's PR (Good/Bad/Ugly) and triages its own findings in the same session. The
  invoking agent then assesses the triaged findings as the author. Reviewers come from
  `~/.config/independent-pr-review/config.json` (one default; `all`, named or ad-hoc
  `harness:model:effort` on request). Without a config file, built-in presets `codex-sol`
  (`gpt-6.2-sol`, the default), `codex-astra` (`gpt-6.2-astra`) and `claude-fable`
  (`claude-fable-5-2`), all at medium effort, are available; results are saved under the git common dir (or
  `INDEPENDENT_PR_REVIEW_OUTPUT_DIR`), keeping the newest `keep_runs` runs per branch.
- `terminal-capture`: capture-only workflow for verified terminal output. Produces
  animated plus static SVG by default (scripted PTY recorder to asciicast v2, rendered
  by svgcast built from source at a pinned, hash-checked version), with Charmbracelet
  VHS as the fallback for PNG/GIF/MP4/WebM on request. Includes a secret scan before
  and after recording (built-in rules plus a pinned, source-built Betterleaks engine, run
  with hardened flags) that deletes artifacts and stops on credential-shaped content, a
  scrubbed-environment recorder, and an SVG preview helper.
- `terminal-capture`, `github-pr-screenshots`: the SVG deliverables stay SVG through upload.
  `preview.py` PNGs are documented as inspection-only, format changes need an explicit user
  request, and SVG is documented as uploadable as-is with `gh attach`. Added animated-vs-still
  guidance and a private-repo embed check.
- `terminal-capture`: the recorder sends each `key` step as one write, so arrow keys, Home/End and
  Page keys arrive as a single escape sequence instead of being read as a bare Esc; `preview.py`
  sizes its window to the SVG; documented fixture seeding and the no-overwrite rule.
- `brave-web`: `search.js --context` returns query-focused page passages through
  Brave's LLM Context endpoint (`--max-tokens`, `--threshold`); `BRAVE_SEARCH_API_KEY`
  is accepted as an alternative to `BRAVE_API_KEY`. Plain search snippets no longer
  contain `<strong>` tags or HTML entities.
- Skills no longer point at each other by name (`brave-web`, `exa-code`,
  `github-pr-screenshots`), so each works when installed alone.
- Initial collection of 11 model-invoked skills: `agent-browser`, `brave-web`,
  `exa-code`, `github-pr-screenshots`, `grok-research`, `image-gen`, `ralph`,
  `sentry`, `ticket`, `vexor`, and `youtube-transcript-api`.
- 17 user-invoked workflow skills for code review, pull requests, verification,
  summaries, and API security audits.
- Policy-focused browser QA and read-only Sentry triage, with current command
  syntax delegated to installed CLI guides/help and official documentation.
- Repository authoring/lifecycle conventions, skill validation, bundled tests,
  and CI checks.
- Third-party attribution and portable notices for individually installed skills.
