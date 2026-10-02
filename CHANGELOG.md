# Changelog

All notable changes are recorded here. The repository is versioned as a whole
with git tags (`vMAJOR.MINOR.PATCH`); individual skills are not versioned
separately unless they carry `metadata.version` for their own breaking changes.

## [Unreleased]

### Added
- `terminal-capture`: capture-only workflow for verified terminal output. Produces
  animated plus static SVG by default (scripted PTY recorder to asciicast v2, rendered
  by svgcast built from source at a pinned, hash-checked version), with Charmbracelet
  VHS as the fallback for PNG/GIF/MP4/WebM on request. Includes a secret scan before
  and after recording (built-in rules plus a pinned, source-built Betterleaks engine, run
  with hardened flags) that deletes artifacts and stops on credential-shaped content, a
  scrubbed-environment recorder, and an SVG preview helper.
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
