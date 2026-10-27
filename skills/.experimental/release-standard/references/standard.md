# The release standard

The contract every CLI repository follows, whatever its language. Language
wiring is in [node.md](node.md) and [python.md](python.md).

## Versions, tags and the changelog

- Versions are plain semver `X.Y.Z`. Tags are `vX.Y.Z`, annotated as
  `Release X.Y.Z`, on a release commit whose message is `chore: release vX.Y.Z`.
- Releases are cut by hand from a maintainer machine, from a clean `main`.
- `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com): an
  `## [Unreleased]` section on top, groups `Added`, `Changed`, `Fixed`,
  `Removed`, `Security`, user-facing changes only. The release moves Unreleased
  into a dated `## [X.Y.Z]` section and adds a fresh empty Unreleased.
- `scripts/prep-release.sh` prints the commits and changed files since the last
  tag with a prompt for drafting the Unreleased entries with an LLM. The
  maintainer reviews the draft and commits it to `main` before releasing.
- `scripts/check-changelog.sh` makes the release refuse to start when
  Unreleased has no entries.
- The GitHub Release for `vX.Y.Z` uses that version's changelog section.

## Order of a release

1. Preflight: clean `main`, the changelog check, the repository's `verify`
   (lint, types, tests), a package smoke test, and, when it publishes, a check
   that the maintainer is logged in to the registry.
2. Bump the version and the changelog, commit, tag, push the commit and tag.
3. Create the GitHub Release.
4. **Publish to the registry last, from the tagged commit.** The published build
   is stamped with the tag's commit and a clean tree. Publishing before the
   commit exists would stamp the parent commit with a dirty tree.
5. If a later step fails, the earlier ones stay done. Each repository's
   `RELEASING.md` names the one command that resumes from the failed step
   (for example, publish again without re-tagging).

Unpublished tools (installed from a clone or a git URL) do steps 1–3 only.

## Version output

`<tool> --version` and `-V` print one line on stdout and exit 0:

```text
<name> <version> (<sha7>[-dirty] <YYYY-MM-DD>)
mytool 1.4.2 (a1b2c3d 2026-10-27)
mytool 1.4.3 (9f8e7d6-dirty 2026-10-28)
```

- `<name>` is the command name, `<sha7>` the first 7 characters of the commit
  the build came from, the date that commit's date (not the build date, so the
  same commit always prints the same line).
- `-dirty` marks a build made from a working tree with uncommitted changes.
- With no commit information at all, print `<name> <version>` with no empty
  parentheses.
- The same line is printed by a registry install and by a local build. Builds
  stamp the commit into a build-info file, which is what installed copies and
  built output report. Code running from source in a checkout reads git
  instead, so a stale build never hides newer commits or edits.

`<tool> version` (a subcommand) is optional and prints the details: version,
full commit, date, dirty state, install method, and install path. With
`--json` it prints them as one JSON object.

## Update command

Every tool has `<tool> update`:

| Invocation | Behavior | Exit code |
|---|---|---|
| `update` | Check, then update with the method the tool was installed with | 0 when updated or already current, non-zero on failure |
| `update --check` | Report only | 0 up to date, 1 update available, 2 unknown |
| `update --force` | Update even when already current | as `update` |

The install method decides both where "latest" comes from and what runs:

| Installed with | Latest is | Update runs |
|---|---|---|
| Source checkout (clone + build + link) | `origin/main`, or the checkout's own commit when the build is older | `git pull --ff-only`, install dependencies, build. Refuses when the tree is dirty or not on `main`. |
| Global npm, pnpm or bun, from the registry | registry `latest` | `npm install -g <pkg>@latest` (or the pnpm/bun equivalent) |
| Global npm, pnpm or bun from a git URL (unpublished) | remote `main` | `npm install -g <git url>` (or `pnpm add -g`, `bun add -g`) |
| mise (`npm:` or `pipx:` backend) | registry `latest` | `mise upgrade --bump <backend>:<pkg>` |
| npx | nothing to update | prints that `npx <pkg>@latest` always runs the latest |
| uv tool, pipx, pip (Python) | PyPI | `uv tool upgrade`, `pipx upgrade`, `pip install -U` |
| Anything else | | prints the manual steps, exit 1 |

The tool prints the command before running it and runs it in the foreground,
so prompts reach the terminal. When a step fails, it says how to finish after
fixing the cause: run `update` again (a build older than the checkout counts as
an update, so a failed build after a successful pull is retried), or
`update --force` where nothing records that the update is unfinished. An unpublished tool never looks its name up on
a registry, where an unrelated package could have it; when its installer
cannot reinstall from the original source, `update` says so and stops.

## Install documentation

The README has an `## Install` section with, in order:

1. The registry install (`npm install -g <pkg>`, `uv tool install <pkg>`), plus
   the no-install form (`npx`, `uvx`) when it applies. Omit when unpublished.
2. **From source**: clone, install dependencies, build, link (`npm link` or
   the language's equivalent), and `<tool> --version` to confirm which commit
   is on `PATH`. Present in every repository, published or not.
3. **Updating**: `<tool> update`.

See the Install section templates in each language's `templates/` folder.

## Files every repository has

| File | Canonical (byte-identical copy) |
|---|---|
| `CHANGELOG.md` | no |
| `RELEASING.md` (from the template, then adjusted) | no |
| `scripts/prep-release.sh` | yes |
| `scripts/check-changelog.sh` | yes |
| Language files (see node.md, python.md) | varies |

Canonical scripts start with a `# release-standard:` header naming the file and
its revision. Do not edit them in place; project-specific additions go in the
hook files the scripts call (for example `scripts/test-package.local.sh`), so
the audit can compare the copies with the templates.
