## Install

<!-- Template from the release standard. Replace <pkg>, <tool> and <repo>.
     For an unpublished package, delete the first block and keep "From source". -->

```bash
npm install -g <pkg>        # or: pnpm add -g <pkg>, bun add -g <pkg>
npx <pkg> --help            # run without installing
```

Requires Node.js <range from package.json "engines">.

### From source

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
npm install
npm run build
npm link                    # puts `<tool>` on your PATH, pointing at this clone
<tool> --version            # <tool> X.Y.Z (sha7 YYYY-MM-DD): the commit you built
```

Rebuild after pulling (`npm run build`); the link keeps pointing at the clone.
If `<tool>` is also installed globally, remove that copy so the linked build is
the one on `PATH` (`command -v <tool>` should resolve inside the clone).

### Updating

```bash
<tool> update --check       # exit 0: up to date, 1: update available
<tool> update               # updates the same way it was installed
```
