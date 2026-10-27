# Node and TypeScript wiring

How a Node CLI meets [the standard](standard.md). Templates are in
`templates/node/` and `templates/shared/`. Use the repository's own package
manager (`npm run`, `pnpm`, `bun run`) wherever the templates say `npm run`;
`npm` itself is still used for `pack`, `publish`, `view` and `whoami`.

## Files

| Copy | To | Canonical |
|---|---|---|
| `shared/prep-release.sh` | `scripts/prep-release.sh` | yes |
| `shared/check-changelog.sh` | `scripts/check-changelog.sh` | yes |
| `node/release.mjs` | `scripts/release.mjs` | yes |
| `node/build-info.mjs` | `scripts/build-info.mjs` | yes |
| `node/test-package.sh` | `scripts/test-package.sh` | yes |
| `node/cli-meta.ts` | `src/cli-meta.ts` (or `.js`, types removed) | no, adapt |
| `node/release-it.json` | `.release-it.json` | no: swap `npm run` for the package manager |
| `node/RELEASING.md` | `RELEASING.md` | no |
| `node/install-section.md` | the README's `## Install` | no |

Make the shell scripts executable (`chmod +x`). Keep project-specific
smoke-test checks in `scripts/test-package.local.sh`; it is sourced with
`$consumer` set to the install prefix, so a check reads
`"$consumer/node_modules/.bin/<tool>" doctor --offline`.

## package.json

```jsonc
{
  "scripts": {
    "build": "<existing build> && node scripts/build-info.mjs",
    "prepack": "npm run build",
    "verify": "<lint> && <typecheck> && <test>",
    "test:package": "bash scripts/test-package.sh",
    "release:prep": "bash scripts/prep-release.sh",
    "release:dry": "node scripts/release.mjs release --dry-run",
    "release": "node scripts/release.mjs release",
    "release:publish": "node scripts/release.mjs publish"
  },
  "files": ["dist", "README.md", "LICENSE"],
  "devDependencies": {
    "release-it": "^21",
    "@release-it/keep-a-changelog": "^8"
  }
}
```

- `build-info.mjs` runs **after** anything that empties `dist/`.
- `files` must ship `dist/build-info.json`. A pattern such as `dist/**/*.js`
  does not; add `"dist/build-info.json"` explicitly. `test-package.sh` fails
  when it is missing.
- `prepack` is what makes `npm pack` (the smoke test) and `npm publish` (the
  release) build from the commit they run on. npm runs `prepublishOnly`
  **before** `prepack`, so a check of the build output (a secret scan of
  `dist/`) placed there would scan the previous build. Put such checks in
  `prepack`, after the build:
  `"prepack": "npm run build && <scan dist>"`. Checks of the source tree can
  stay in `prepublishOnly`.
- `dist/` must be gitignored. Otherwise every build counts as uncommitted
  changes and the stamp always says `-dirty`.
- A scoped package (`@scope/name`) that is public needs
  `"publishConfig": { "access": "public" }`. `release.mjs` passes no
  `--access` flag, so package.json decides and a package meant to stay
  restricted is never published as public by accident.
- Repositories that published before the standard may have `release:first`;
  drop it. A first release from an already-set version is
  `npm run release -- <version> --npm.allowSameVersion`.
- A private (unpublished) package keeps `"private": true` and a `repository`
  field (`github:owner/repo`, `owner/repo`, `git@host:owner/repo.git` or a
  full URL). `release.mjs` then stops after the GitHub Release, and `update`
  compares with the repository's `main` and reinstalls from it with npm, pnpm
  or bun. It never looks the name up on the registry, where an unrelated
  package could have it.

## Why release.mjs exists

release-it runs its `release` steps in plugin order npm → git → github, so with
its npm plugin enabled `npm publish` (and the `prepack` build) runs before the
release commit and tag exist. The build would be stamped with the previous
commit and a dirty tree. The template therefore sets `npm.publish: false` (the
npm plugin still bumps `package.json`) and `release.mjs` publishes after
release-it finishes, with the terminal attached so 2FA prompts work. Do not
move the publish into a release-it hook: hooks do not get an interactive
terminal.

## Version and update in the CLI

With commander:

```ts
import { runUpdate, versionDetails, versionLine } from "./cli-meta.js";

program.version(versionLine("mytool"), "-V, --version", "print the version and commit");
program
  .command("update")
  .description("update mytool the way it was installed")
  .option("--check", "report only: exit 0 up to date, 1 update available, 2 unknown")
  .option("--force", "update even when already up to date")
  .action((opts) => {
    process.exitCode = runUpdate("mytool", opts);
  });
program
  .command("version")
  .option("--json")
  .action((opts) => {
    const d = versionDetails();
    console.log(opts.json ? JSON.stringify(d) : Object.entries(d).map(([k, v]) => `${k}: ${v}`).join("\n"));
  });
```

Other parsers: print `versionLine(...)` for `--version`/`-V` and exit 0.

Notes on `cli-meta.ts`:

- `import.meta.url` appears only in the `HERE` constant near the top. In a
  CommonJS build, change that line to `const HERE = __dirname;` and drop the
  `node:url` import.
- It finds the package root by walking up from its own file to the first
  `package.json`, so it works from `src/` (tsx, bun) and from `dist/`.
- In a checkout, code running from `dist/` reports the stamp (the commit that
  build came from), and code running from `src/` reads git (the current commit
  and `-dirty`). Outside a checkout the stamp is the only source.
- A source checkout is detected by `.git` at the package root. In a monorepo
  where the CLI is one package, detect the checkout from the repository root
  and run the build for that package.
- Single-file binaries (`bun build --compile`) have no `package.json`; define
  the version and commit at compile time instead and keep the same output.
- Several command names (`bin` aliases) share one package; pass the name the
  README uses as primary.

## Checking the result

```bash
npm run verify && npm run test:package   # the smoke test checks the --version format
npm run release:dry
node dist/cli.js --version               # <tool> X.Y.Z (sha7 YYYY-MM-DD), -dirty if built with uncommitted changes
node dist/cli.js update --check          # from a linked checkout: compares with origin/main
```
