---
name: release-standard
description: "Audit, set up, or cut a release in a CLI repository with the shared release standard: release-it (Node) or native tools (Python), Keep a Changelog with an LLM-drafted section, vX.Y.Z tags, publish last from the tag, a `name X.Y.Z (sha7 YYYY-MM-DD)` --version line, an `update` command, and a from-source install section."
compatibility: "Requires git, bash and python3 (audit). Node repositories need Node 22.18+ and release-it 21 (GitHub Releases through a GITHUB_TOKEN or the browser); Python repositories need uv or twine, and gh for GitHub Releases."
disable-model-invocation: true
argument-hint: "[audit | apply | release] [repo path or name, ...] [notes]"
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

## Invocation

The text after the skill name picks the target and the mode. Nothing given
means: the repository in the current directory, full workflow.

- **Target.** A path (`~/src/mytool`, `../other`) is used as is. A bare
  repository name or `owner/repo` is looked for among the current directory,
  its parent's other directories, and the user's own instructions; if no local
  clone is found, ask where it is or whether to clone it, and where. Several
  targets are handled one at a time: audit all of them first and show one
  combined summary, then apply to each only after its own go-ahead.
- **Mode.**
  - `audit` (or "check", "report"): step 1 only, then a short summary of the
    gaps per repository. No edits.
  - `apply` (the default): the full workflow below.
  - `release`: cut a release of a repository that already follows the
    standard (see "Releasing a repository that follows the standard").
- **Notes.** Anything else (for example "skip the update command for now",
  "Python only") narrows the plan in step 2.

Work inside the target repository: run its commands from its root and edit
only its files.

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
   editing any repository, including the current one.

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

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it as described in Invocation.
