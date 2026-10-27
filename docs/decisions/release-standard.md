# Decision record: a shared release standard

Status: accepted, October 2026. Implemented as the experimental
[`release-standard`](../../skills/.experimental/release-standard/SKILL.md)
skill.

## Problem

The maintainer keeps many small command-line tools, mostly TypeScript and
published to npm, a few in Python, and some not published anywhere and
installed from a clone. Each repository got its release setup by copying the
previous one and adjusting it, so the setups drifted:

- An investigation of a dozen or so recently active repositories with similar
  tooling found that the release-it configuration itself was nearly identical
  everywhere (tag format, commit message, clean `main`, changelog plugin). The
  drift was in the glue around it: the changelog-drafting script existed in
  about six variants, the "Unreleased must not be empty" check in about six
  variants (and was missing in some repositories), every `RELEASING.md` was
  different, and dry-run and first-release flags varied.
- `--version` printed only the package version almost everywhere. Only one tool
  printed the commit, and only one had a self-update command. On a real
  machine, a linked checkout and a stale global install both printed a bare
  version, so there was no way to tell which build was running or that it was
  out of date.
- Install documentation was inconsistent: some READMEs explained installing
  from source and some did not, with different steps each time.

Fixes made in one repository did not reach the others, and each release felt
slightly different.

## Goals

1. One release flow for every repository: changelog drafted with an LLM from
   the commits, a check that it is not empty, bump, tag, GitHub Release,
   publish.
2. One install story: a registry install when published, and always a
   documented clone, build and link path, which also covers tools in other
   languages and tools not published yet.
3. One way to identify a build: the same `--version` line for registry installs
   and local builds, showing the commit.
4. One `update` command that works however the tool was installed.

## Decisions

### Keep release-it as the engine; standardize the glue

release-it already did the core work well, and its configuration had
converged. Replacing or wrapping it heavily would create one more tool that
needs careful releases of its own, and the edge cases (monorepos, compiled
binaries, non-Node repositories) appear quickly. The standard fixes the parts
that drifted: the scripts, the docs, the version output, and the update
command.

### A skill first, a package later

Two ways to share the glue were considered: a skill (conventions, templates and
an audit) or an npm package (`release-kit`) that repositories depend on. The
drift was mostly in copied scripts, which a package removes for good, and
partly in docs and conventions, which a skill handles. The long-term answer is
both. The skill comes first so the conventions settle while they are applied to
a few repositories, before any package API is fixed. Until then, scripts are
copied byte for byte with a revision header, and the audit reports copies that
differ.

### Python and other languages: same contract, native tools

Options considered:

- Leave non-Node repositories out: no work, but guaranteed drift.
- Use release-it everywhere: one tool, but a Python repository would need a
  `package.json` and Node just to release, and version files outside
  `package.json` need plugins.
- Write a new tool for any language: effectively a new release-it.
- **Same contract, native tools (chosen):** tag format, changelog format and
  prompt, the changelog check, RELEASING.md layout, version line, update
  command and install section are shared; bumping and publishing use the
  language's own tools (uv or twine, make).

The contract is what needs to be consistent, and it does not depend on
language. The two scripts most worth sharing (changelog prompt and changelog
check) are plain bash and are used unchanged.

### Distribution of the future package: public npm

Options considered for `release-kit`: a public npm package, a git dependency,
a global tool installed per machine, or no package at all (copies plus audit).
**Public npm (chosen)**, as a pinned dev dependency: Renovate then opens
upgrade PRs in every repository, so a fix made once reaches all of them; it
installs the same way with npm, pnpm and bun and in CI with no extra
authentication; and it matches how the CLIs themselves are published. A git
dependency is handled less well by Renovate and needs prebuilt output and
possibly auth; a global tool is not pinned per repository, so releases would
depend on the machine. Repositories without Node keep using copies and the
audit.

The runtime part (version line and update) is a separate, dependency-free
package, because it ships inside every installed tool, while the release
scripts matter only to the maintainer.

### Publish last, from the tagged commit

release-it runs its release steps in plugin order npm → git → github, so with
its npm plugin enabled the package is published (and built by `prepack`)
before the release commit and tag exist. A build stamp made then records the
previous commit and a dirty tree. The standard turns release-it's publish off
and publishes afterwards from the tagged commit, with the terminal attached so
2FA prompts work (release-it hooks do not get an interactive terminal). This
pattern already existed in one investigated repository. The order also makes
recovery simple: a failed publish is retried without re-tagging.

### Version line: `name X.Y.Z (sha7 YYYY-MM-DD)`

The format follows rustc and cargo (`rustc 1.80.0 (051478957 2024-07-21)`)
and the GNU convention of putting the program name first. Tools that parse
version output look for the first version-like token on the first line on
stdout with exit code 0, which this keeps. Details:

- The date is the commit date, not the build date, so a commit always prints
  the same line.
- `-dirty` after the short sha marks a build from uncommitted changes, as
  `git describe` does.
- Without any commit information the line is just `name X.Y.Z`; no empty
  parentheses.
- Details (full commit, install method, path) belong in an optional
  `version --json` subcommand, so `--version` stays one line.

The commit is stamped into a build-info file at build time, because a registry
tarball has no `.git`; a run straight from source reads git instead.

### Every tool gets `update`

`update`, `update --check` (exit 0 up to date, 1 update available, 2 unknown)
and `update --force`. The tool detects how it was installed (source checkout,
global npm, pnpm or bun, mise, npx, uv tool, pipx, pip) and updates the same
way, so it never installs a second copy next to the first. It prints each
command before running it, runs it in the foreground, and refuses to update a
checkout that is dirty or not on `main`.

### The skill runs only when asked

The skill is user-invoked (`disable-model-invocation: true`): it edits
repositories and can cut releases, so an agent never picks it up on its own
from a passing mention of releases or versions. The invocation text names the
target repositories and the mode (`audit`, `apply`, `release`), and the skill
still asks before any edit and before any real release.
