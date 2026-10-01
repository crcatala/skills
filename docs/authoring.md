# Authoring skills

How skills in this repository are written, moved, and retired. Skills must work
in Claude Code and pi (and any other spec-compliant harness) without
modification. Run `scripts/validate.sh` and `scripts/test.sh` after any change;
the validator enforces the layout, README listing, naming, frontmatter, and
portability rules below, and its messages say what to fix.

## Layout

```
skills/<name>/SKILL.md          stable skill (flat; no category folders)
skills/.experimental/<name>/    in progress
```

- The directory name equals the `name` field. The validator rejects any other
  nesting under `skills/`.
- Installers (the `skills` CLI) discover everything under `skills/` and key on
  the skill `name`, not its path. Do not add `archive/`, `deprecated/`,
  `in-progress/` or similar folders under `skills/`: they are discovered and
  installed by wildcard like any other skill.
- Stable skills are listed in `README.md` (the validator enforces this).
  Experimental skills are not listed.

## Lifecycle

**Experimental → stable.** Build in `skills/.experimental/<name>/`. When it is
ready, `git mv` it to `skills/<name>/` (same `name`, so existing installs keep
working), add it to the README catalog, and note it under `[Unreleased]` in the
CHANGELOG. Experimental skills may change or disappear without a release note.

**Changing a stable skill.** Keep the `name` stable. If the behavior changes
incompatibly, create a new name instead of silently changing the old one.

**Retiring a stable skill.**
1. Delete the directory. Do not move it to an archive folder: a same-named copy
   anywhere in the repo can still be found by `skills update`, so deleting is
   the only clear "removed" signal to consumers.
2. Record it under `### Removed` in the CHANGELOG, naming the replacement if any.
3. Tag the last release that contained it (see Releases), so it can be
   recovered with `git show <tag>:skills/<name>/SKILL.md`.
4. Remove it from the README catalog.

**Renaming.** Treat it as retire plus add: consumers pin by `name`. Mention the
old and new names in the CHANGELOG.

**Moving between folders** (promoting from experimental) is safe. Update any
hardcoded paths: README links, `/tree/main/skills/<name>` install URLs, and any
plugin manifest if one is ever added.

## Frontmatter

Use only core spec fields: `name`, `description`, `license`, `compatibility`,
`metadata`, `allowed-tools`. Two harness extensions are allowed and understood
by both Claude Code and pi: `disable-model-invocation` and `argument-hint`.

- `description`: what it does and when to use it, specific keywords, under 1024 chars.
- `compatibility`: one line naming required binaries, env vars, and network
  access. Omit if the skill needs nothing.
- Per-skill version, only if needed: `metadata.version: "1.2.0"`. Never a top-level `version:`.
- Do not use Claude-only features in shared skills (`context: fork`, `` !`cmd` ``
  injection, `$ARGUMENTS` substitution, `${CLAUDE_*}` variables).

## Two kinds of skill

- **Model-invoked** (default): tools and knowledge the agent can pick up by description.
- **User-invoked**: a workflow you trigger by hand. Set `disable-model-invocation: true`.
  This keeps the description out of the model's context entirely. End the body
  with the standard note that text supplied at invocation is extra instructions
  (see any existing user-invoked skill). Do not rely on `$ARGUMENTS`: pi delivers
  invocation text appended to the instructions, Claude Code appends an
  `ARGUMENTS:` line when the body has no placeholder.

## Self-contained skills

A skill directory must work when installed alone: no imports or links outside
its own directory. Refer to bundled files by relative path from the skill root,
one level deep. In command examples, `{baseDir}` means the directory containing
`SKILL.md`; say so once near the top of the skill.

## Requirements and dependencies

- Declare them in `compatibility`, then add a short "Requirements" or
  "Installation check" section with a one-line check command and a one-line
  install hint. Put longer install steps in `references/install.md`.
- If a requirement is missing, the skill reports it and stops. It never
  installs system packages on its own.
- Scripts should self-bootstrap (inline script deps, auto `bun install` on first
  run) rather than depend on a manual setup step.
- No environment-specific paths, hostnames, or container details. Those belong
  in the consuming environment's own instructions.

## Size

Keep `SKILL.md` under 500 lines and the always-loaded text small. Move detail
into `references/`. Do not commit research notes, generated files,
`node_modules/`, or `__pycache__/` inside a skill.

## Releases

Tag the repository `vMAJOR.MINOR.PATCH` and note changes under `[Unreleased]`
in `CHANGELOG.md`. Consumers pin by tag or commit. Tag before deleting a skill
so the last version stays recoverable (see Lifecycle).
