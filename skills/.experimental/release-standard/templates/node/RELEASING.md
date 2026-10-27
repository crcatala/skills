# Releasing

<!-- Template from the release standard. Replace <pkg> and <tool>, use the
     repository's package manager in place of `npm run`, and delete the npm
     parts if the package is private (unpublished). -->

Releases are cut by hand from a clean `main` with
[release-it](https://github.com/release-it/release-it), wrapped by
`scripts/release.mjs`. One command bumps the version, moves the changelog's
Unreleased section into the new version, commits, tags `vX.Y.Z`, pushes,
creates the GitHub Release, and then publishes `<pkg>` to npm from the tagged
commit.

## Prerequisites

- Push access to `main`, and a GitHub token for the release (`GITHUB_TOKEN`,
  or release-it opens the GitHub release form in the browser instead).
- An npm login with publish rights to `<pkg>`: `npm whoami`, else `npm login`.

## Before releasing

1. Start from an up-to-date `main`:

   ```bash
   git checkout main
   git pull --ff-only
   ```

2. Draft the changelog:

   ```bash
   npm run release:prep
   ```

   Paste the output into an LLM, review the result, and put it under
   `## [Unreleased]` in `CHANGELOG.md` (Added, Changed, Fixed, Removed,
   Security; user-facing changes only). Commit it to `main` and push.

## Release

```bash
npm run release:dry       # preview; changes nothing and skips the hooks
npm run release           # asks for the version; or: npm run release -- patch|minor|major
```

In order, `npm run release`:

1. refuses to start when not logged in to npm or when `HEAD` is already a release;
2. checks that Unreleased has entries and runs `npm run verify`;
3. bumps the version and the changelog, then runs `npm run test:package` (packs
   the tarball, installs it, checks `--help` and `--version` for every command);
4. commits `chore: release vX.Y.Z`, tags `vX.Y.Z`, pushes both;
5. creates the GitHub Release;
6. publishes to npm from the tagged commit (npm may ask for a one-time password).

## When a step fails

- **Before the commit** (steps 1–3): nothing was changed on the remote. Fix the
  cause and run `npm run release` again; `git checkout -- .` discards a
  half-made bump.
- **GitHub Release** (step 5): the tag is pushed. Create the release from the
  tag with that version's CHANGELOG section as notes
  (`gh release create vX.Y.Z --title vX.Y.Z --notes-file <section>`), then run
  `npm run release:publish`.
- **npm publish** (step 6): the tag is pushed; only the publish is left. Run
  `npm run release:publish` from the tagged commit.

## Verify

```bash
npm view <pkg> version
npx <pkg>@latest --version     # <tool> X.Y.Z (sha7 YYYY-MM-DD)
```
