# Releasing

<!-- Template from the release standard. Replace <dist>, <tool> and <package>,
     and match the make targets to the repository's Makefile. Delete the PyPI
     parts if the tool is unpublished. -->

Releases are cut by hand from a clean `main`. The tag and GitHub Release come
from `make release`; the PyPI upload is a separate, last step from the tagged
commit, so a failed upload never leaves a half-made tag.

## Prerequisites

- Push access to `main`; `gh auth status` succeeds.
- PyPI and TestPyPI tokens (`uv publish` reads `UV_PUBLISH_TOKEN`; twine reads
  `~/.pypirc`).

## Before releasing

1. `git checkout main && git pull --ff-only`
2. `bash scripts/prep-release.sh`. Paste the output into an
   LLM, review the result, and put it under `## [Unreleased]` in `CHANGELOG.md`.

## Release

```bash
make bump VERSION=X.Y.Z   # version in pyproject.toml (and __init__.py), changelog section,
                          # commit "chore: release vX.Y.Z"; refuses an empty Unreleased
git push                  # the release commit must be on origin/main before tagging
make prepublish           # verify, stamp build info, build, install the wheel in a clean
                          # environment and check `<tool> --version`
make release-dry          # preview the tag and GitHub Release
make release              # tag vX.Y.Z (annotated "Release X.Y.Z"), push, GitHub Release
                          # with the changelog section and the wheel/sdist attached
uv publish --index testpypi dist/*   # optional rehearsal
uv publish dist/*         # last: upload the files built from the tagged commit
```

`make release` refuses to run when the tree is dirty, `HEAD` is not on
`origin/main`, the tag already exists, or `dist/` was built from another commit.

## When a step fails

- **Before `git push`**: nothing is on the remote yet. Fix and repeat;
  `git reset --hard origin/main` drops a local bump commit.
- **After `git push`, before `make release`**: the bump commit is on `main`
  but untagged. Fix the cause and continue from `make prepublish`; do not bump
  again.
- **GitHub Release**: the tag is pushed. Create it with
  `gh release create vX.Y.Z dist/* --title vX.Y.Z --notes-file <section>`.
- **Upload**: run `uv publish dist/*` again; files already on PyPI are skipped
  with `--check-url https://pypi.org/simple/`.

## Verify

```bash
uvx <dist>@latest --version    # <tool> X.Y.Z (sha7 YYYY-MM-DD)
```
