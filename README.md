# skills

Personal [Agent Skills](https://agentskills.io/specification) for coding agents
(Claude Code, pi, and any other harness that implements the spec).

## Install

Install with the [`skills` CLI](https://github.com/vercel-labs/skills), choosing
only what you want:

```bash
# pick skills by name, for Claude Code and the shared ~/.agents/skills location (pi, others)
npx skills add crcatala/skills --skill brave-web --skill create-pr -g -y -a claude-code -a universal
```

Always name the skills you want. Avoid `--skill '*'`: the CLI installs every
skill it finds, including anything in `skills/.experimental/`.

Or copy a skill directory into `~/.claude/skills/` (Claude Code) or
`~/.agents/skills/` (pi and other spec-compliant harnesses) yourself. Each
skill is self-contained.

## Two kinds of skill

| Kind | Frontmatter | Loaded | Invoked by |
|---|---|---|---|
| **Model-invoked** (tools and knowledge) | name + description | description always in context; body when relevant | the agent, or you |
| **User-invoked** (workflow prompts) | `disable-model-invocation: true` | nothing until you run it | you only |

User-invoked skills replace prompt templates / slash commands. Run them with
`/<name>` in Claude Code and `/skill:<name>` in pi. Anything you type after the
name is passed to the agent as extra instructions, in both harnesses:

```text
/review-branch focus on error handling
/skill:review-branch focus on error handling
```

## Catalog

### Model-invoked

| Skill | What it does | Needs |
|---|---|---|
| [`agent-browser`](skills/agent-browser/SKILL.md) | Browser QA policy: task sessions, UI verification, screenshot evidence; syntax from installed CLI guides | `agent-browser`, Chrome |
| [`brave-web`](skills/brave-web/SKILL.md) | Browser-free web search and URL-to-markdown extraction | bun, `BRAVE_API_KEY` |
| [`exa-code`](skills/exa-code/SKILL.md) | Code docs and API examples via Exa | bun, `EXA_API_KEY` |
| [`github-pr-screenshots`](skills/github-pr-screenshots/SKILL.md) | Upload screenshots to a PR and embed them | `gh`, `gh-attach` |
| [`grok-research`](skills/grok-research/SKILL.md) | Deep agentic web + X research via Grok | python3, `XAI_API_KEY` |
| [`image-gen`](skills/image-gen/SKILL.md) | Generate or edit images (OpenAI GPT Image, xAI Grok Imagine) | python3, `OPENAI_API_KEY` and/or `XAI_API_KEY` |
| [`ralph`](skills/ralph/SKILL.md) | Autonomous, ticket-native campaign delivery | `ralph`, `tk`, `gh`, node 22+ |
| [`sentry`](skills/sentry/SKILL.md) | Read-only triage policy: access boundaries, evidence, privacy; syntax from CLI help/docs | `sentry` CLI |
| [`ticket`](skills/ticket/SKILL.md) | The `tk` git-backed markdown issue tracker | `tk` |
| [`terminal-capture`](skills/terminal-capture/SKILL.md) | Verified PNG/GIF/video captures of CLI and TUI output via Charmbracelet VHS | `vhs`, `ttyd`, `ffmpeg` |
| [`vexor`](skills/vexor/SKILL.md) | Semantic file discovery by intent | `vexor` |
| [`youtube-transcript-api`](skills/youtube-transcript-api/SKILL.md) | Public YouTube captions via Supadata | python3, `SUPADATA_API_KEY` |

`agent-browser` and `sentry` keep this repository's operating policies, not
copies of upstream command catalogs. They consult the installed tools' guides
and help for current syntax. Keep one `agent-browser` entry point rather than
installing a competing same-named official discovery skill; fetched references
do not override the policy boundaries. No separate upstream skill installation
is needed for either policy skill.

For OpenTUI, use the
[official OpenTUI skill](https://github.com/anomalyco/opentui/blob/main/packages/web/src/content/SKILL.md)
when needed: `npx skills add anomalyco/opentui --skill opentui`.

### User-invoked

| Skill | What it does |
|---|---|
| [`review-branch`](skills/review-branch/SKILL.md) | Review the current branch against main; print only |
| [`review-branch-github`](skills/review-branch-github/SKILL.md) | Review the current branch and post it as a PR comment |
| [`review-pr-good-bad-ugly`](skills/review-pr-good-bad-ugly/SKILL.md) | Full PR read, structured Good/Bad/Ugly review |
| [`triage-review-findings`](skills/triage-review-findings/SKILL.md) | Which Bad/Ugly findings are worth fixing (recommend only) |
| [`assess-review-feedback`](skills/assess-review-feedback/SKILL.md) | Judge another agent's review feedback (pass it as the argument) |
| [`review-and-fix-pr`](skills/review-and-fix-pr/SKILL.md) | Review, comment, fix worthwhile issues, push |
| [`review-pr-overengineering`](skills/review-pr-overengineering/SKILL.md) | Assess over-engineering, comment, simplify, push |
| [`create-pr`](skills/create-pr/SKILL.md) | Open a PR with summary and technical details |
| [`update-pr-description`](skills/update-pr-description/SKILL.md) | Rewrite the PR description concisely, with an example |
| [`implement-and-pr`](skills/implement-and-pr/SKILL.md) | Implement the agreed plan on a new branch, then open a PR |
| [`merge-when-ci-green`](skills/merge-when-ci-green/SKILL.md) | Fix CI until green, then merge |
| [`verify-pr-with-proof`](skills/verify-pr-with-proof/SKILL.md) | Plan, comment, and run verification steps for a PR |
| [`suggest-manual-verification`](skills/suggest-manual-verification/SKILL.md) | Manual steps a human can run to verify the work |
| [`layman-summary`](skills/layman-summary/SKILL.md) | Concise layman's summary of the work, the why, the impact |
| [`evaluate-competing-prs`](skills/evaluate-competing-prs/SKILL.md) | Compare PRs from different agents, with scoring |
| [`qa-verify-pr`](skills/qa-verify-pr/SKILL.md) | QA a PR against the running app with `agent-browser` |
| [`security-audit-api`](skills/security-audit-api/SKILL.md) | Audit public API endpoints against a local server |

## Experimental skills

Skills in [`skills/.experimental/`](skills/.experimental) are public on purpose
but unfinished. They are not listed in the catalog above and can change or be
removed without notice. Install one by name:

```bash
npx skills add crcatala/skills --skill <name> -g -y -a claude-code -a universal
```

## Layout and conventions

```
skills/<name>/SKILL.md     stable skills (flat)
skills/.experimental/      in progress: installable by name, not in the catalog, may change or vanish
scripts/validate.sh        spec + convention checks (also run in CI)
scripts/test.sh            repo checks and the tests bundled with skills
```

See [docs/authoring.md](docs/authoring.md) for authoring conventions, and
[CHANGELOG.md](CHANGELOG.md) for history. Versions are git tags on the whole
repository. Third-party attributions are in [NOTICE.md](NOTICE.md).

Skills run with your agent's permissions and some call paid or networked APIs.
Review a skill before installing it.

## License

Repository-authored material is [MIT](LICENSE). Third-party material retains
its applicable upstream terms; see [NOTICE.md](NOTICE.md) and the notices
bundled inside individual skills. In particular, the `agent-browser` guide
retains Apache-2.0 attribution and a bundled upstream license. External CLI
software and documentation are separately licensed by their publishers.
