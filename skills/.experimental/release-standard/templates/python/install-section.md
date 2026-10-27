## Install

<!-- Template from the release standard. Replace <dist>, <tool> and <repo>.
     For an unpublished tool, delete the first block and keep "From source". -->

```bash
uv tool install <dist>      # or: pipx install <dist>, pip install <dist>
uvx <dist> --help           # run without installing
```

Requires Python <requires-python from pyproject.toml>.

### From source

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
uv tool install --editable .   # puts `<tool>` on your PATH, running this clone's code
<tool> --version               # <tool> X.Y.Z (sha7 YYYY-MM-DD): the commit you are on
```

Code changes take effect on the next run; reinstall (`uv tool install --editable
. --reinstall`) after dependencies change.

### Updating

```bash
<tool> update --check       # exit 0: up to date, 1: update available
<tool> update               # updates the same way it was installed
```
