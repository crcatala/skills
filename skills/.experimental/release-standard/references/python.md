# Python wiring

How a Python CLI meets [the standard](standard.md) while keeping Python's own
tools (uv or twine for publishing, make for the steps). Templates are in
`templates/python/` and `templates/shared/`.

## Files

| Copy | To | Canonical |
|---|---|---|
| `shared/prep-release.sh` | `scripts/prep-release.sh` | yes |
| `shared/check-changelog.sh` | `scripts/check-changelog.sh` | yes |
| `python/build_info.py` | `scripts/build_info.py` | yes |
| `python/cli_meta.py` | `src/<package>/cli_meta.py` | no, adapt |
| `python/RELEASING.md` | `RELEASING.md` | no |
| `python/install-section.md` | the README's `## Install` | no |

The release script itself (`scripts/release.sh` or make targets) stays
project-owned. It must do, in order:

1. Refuse a dirty tree, a branch other than `main`, `HEAD` not equal to
   `origin/main`, an existing tag, or an empty Unreleased
   (`bash scripts/check-changelog.sh`).
2. **Bump** (`make bump VERSION=X.Y.Z`): set the version in every place it is
   declared, move Unreleased into `## [X.Y.Z] - YYYY-MM-DD` with a fresh empty
   Unreleased, and commit `chore: release vX.Y.Z`. The maintainer then pushes
   it, so the later steps can require `HEAD` to equal `origin/main`.
3. **Build** from that commit: `python3 scripts/build_info.py
   src/<package>/_build_info.json`, then `uv build`. Install the wheel in a
   throwaway environment and check that `<tool> --version` matches
   `<name> X.Y.Z (sha7 YYYY-MM-DD)` without `-dirty`.
4. **Tag and GitHub Release** (`make release`): annotated tag `vX.Y.Z`
   (`Release X.Y.Z`), push, `gh release create` with the changelog section as
   notes and `dist/*` attached. Refuse when `_build_info.json`'s commit is not
   `HEAD`.
5. **Publish last** (`uv publish` or twine), from the same `dist/`.

## Packaging the stamp

`_build_info.json` is generated, so add it to `.gitignore`, and make sure the
build backend still includes it:

- hatchling: `[tool.hatch.build] artifacts = ["src/<package>/_build_info.json"]`
- other backends: confirm with `unzip -l dist/*.whl | grep _build_info`.

To rehearse on TestPyPI with `uv publish --index testpypi`, declare the index
in `pyproject.toml` (`[[tool.uv.index]]` with `name = "testpypi"`,
`url = "https://test.pypi.org/simple/"`,
`publish-url = "https://test.pypi.org/legacy/"`).

## Version and update in the CLI

`cli_meta.py` reads the version from installed metadata
(`importlib.metadata.version("<dist>")`); keep a `__version__` only if the
project already exports one, and keep it in step with `pyproject.toml`.

- `--version`: print `cli_meta.version_line("<tool>", "<dist>")` and exit 0.
- `update [--check] [--force]`: `raise typer.Exit(cli_meta.run_update(...))`.
  For a tool that is not on PyPI pass `published=False`: it then never looks
  the name up on PyPI (an unrelated package could have it), and updates only
  through installers that remember the original source (`uv tool`, `pipx`) or
  from the checkout.

Install detection keys on where the package lives: a source checkout outside
`site-packages` (editable install), `uv tool`, `pipx`, mise's `pipx:` backend,
or a plain `pip` environment. A checkout update pulls, then reinstalls the
editable install with the installer that owns its environment
(`uv tool install --editable . --reinstall`, `pipx install --editable . --force`
or `pip install --editable .`), so new dependencies and the installed version
follow. Installs from a git URL update with `uv tool upgrade <dist>` or
`pipx upgrade <dist>`, which reinstall from the recorded source.

In a checkout, `--version` reads git (the current commit and `-dirty`); the
`_build_info.json` stamp is used only by installed wheels.

## Checking the result

```bash
make verify
make prepublish                   # build + smoke install, checks the --version format
<tool> --version
<tool> update --check
```
