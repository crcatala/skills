---
name: release-standard
description: "Set up, audit, or bring in line a CLI repository's release process with one shared standard: release-it (Node/TypeScript) or native tools (Python) for version bump, Keep a Changelog with an LLM-drafted Unreleased section, vX.Y.Z tags, GitHub Release, publish last from the tag; a `--version` line of the form `name X.Y.Z (sha7 YYYY-MM-DD)` for both registry installs and local builds; an `update` command that follows the install method; and a README Install section with a from-source path. Use when adding or fixing release scripts, RELEASING.md, version output, self-update, or install docs."
compatibility: "Requires git, bash and python3 (audit). Node repositories need Node 22.18+ and release-it 21; Python repositories need uv or twine. gh is used for GitHub Releases."
---

# Release standard

One release process, version line, update command and install section for
every CLI repository, in any language. In the commands below, `{baseDir}` is
the directory containing this `SKILL.md`.

Read [references/standard.md](references/standard.md) first: it is the
contract. Then the wiring for the repository's language:
[references/node.md](references/node.md) or
[references/python.md](references/python.md). Other languages follow the
contract with their own tools, as the Python wiring does.

## In short

- Hand-cut releases from a clean `main`: changelog check and `verify`, bump,
  commit `chore: release vX.Y.Z`, tag `vX.Y.Z`, push, GitHub Release, and
  **publish last, from the tagged commit**.
- `CHANGELOG.md` in Keep a Changelog form; `scripts/prep-release.sh` prints a
  drafting prompt plus the commits since the last tag.
- `<tool> --version` prints `<name> X.Y.Z (sha7 YYYY-MM-DD)`, `-dirty` for
  uncommitted builds, the same for registry installs and local builds.
- `<tool> update [--check] [--force]` updates the way the tool was installed.
- README `## Install`: registry install, **From source** (clone, build,
  link), **Updating**.

## Requirements

Check: `git --version && python3 --version` (and `node --version` for a Node
repository). Report anything missing and stop; do not install system packages.

## Workflow

1. **Audit.** From the repository root:

   ```bash
   python3 {baseDir}/scripts/audit.py .
   ```

   It is read-only. Also read the current `package.json` or `pyproject.toml`,
   `.release-it.json`, `RELEASING.md`, the README's install text, and how the
   CLI handles `--version`, so you know what the repository does that the audit
   cannot see (extra smoke-test checks, secret scans, monorepo layout, a
   compiled binary).

2. **Plan and confirm.** List the changes: files to copy, scripts to change,
   CLI code to add, README and RELEASING.md edits, and anything you will keep
   that differs from the standard and why. Wait for the user's go-ahead before
   editing a repository other than the current one.

3. **Apply,** on a branch, following the language reference:
   - Copy canonical files byte for byte from `{baseDir}/templates/`. Never edit
     a canonical copy; project-specific checks go in the hook files the scripts
     call (`scripts/test-package.local.sh`).
   - Adapt the non-canonical templates: package manager in `.release-it.json`
     and RELEASING.md, names and URLs in the Install section, CLI wiring for
     `cli-meta`.
   - Keep the repository's own `verify` checks, package manager and extra
     publish safeguards. Do not change the version number.

4. **Verify** without releasing:
   - the repository's `verify`, then the package smoke test (`test:package` or
     `make prepublish`), which checks the `--version` format;
   - the release dry run (`release:dry` or `make release-dry`);
   - from a local build: `--version` shows this commit, and `update --check`
     exits 0 or 1;
   - the audit again: no failures left.

5. **Report** what changed, what was kept and why, and the verification output.
   Commit and open a PR only when asked.

## Releasing a repository that follows the standard

Follow its `RELEASING.md`. Run `release:prep`, draft the Unreleased entries,
and show them to the user before committing. **Never run the real release,
push a tag, or publish without the user's explicit go-ahead for that release**;
the dry run is always fine. When a step fails, use the recovery in
RELEASING.md rather than re-running the whole release.

## Status

Experimental. The canonical scripts are copied into each repository for now.
Once they stop changing, the release scripts are planned to move into a shared
npm dev dependency and `cli-meta` into a small runtime package, at which point
this skill will install those instead of copying files.
