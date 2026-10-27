// Tests for templates/node: cli-meta.ts, build-info.mjs and test-package.sh. Node 22.18+ (type stripping).
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  buildInfo,
  checkForUpdate,
  compareVersions,
  detectInstall,
  formatVersion,
  gitCloneUrl,
  gitInstallUrl,
  packageMeta,
  updateSteps,
} from "../templates/node/cli-meta.ts";

const templates = fileURLToPath(new URL("../templates/", import.meta.url));
const temp: string[] = [];
const mkTemp = () => {
  const dir = mkdtempSync(join(tmpdir(), "release-standard-"));
  temp.push(dir);
  return dir;
};
after(() => temp.forEach((d) => rmSync(d, { recursive: true, force: true })));

const gitEnv = {
  ...process.env,
  GIT_AUTHOR_NAME: "t",
  GIT_AUTHOR_EMAIL: "t@example.com",
  GIT_COMMITTER_NAME: "t",
  GIT_COMMITTER_EMAIL: "t@example.com",
  GIT_CONFIG_GLOBAL: "/dev/null",
};
const sh = (cwd: string, cmd: string, args: string[]) =>
  execFileSync(cmd, args, { cwd, env: gitEnv, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();

const meta = (over: Partial<ReturnType<typeof packageMeta>> = {}) => ({
  root: "/x",
  name: "@scope/tool",
  version: "1.0.0",
  isPrivate: false,
  ...over,
});

describe("formatVersion", () => {
  test("version, short commit and date", () => {
    assert.equal(formatVersion("mytool", { version: "1.4.2", commit: "a1b2c3d4e5f6", date: "2026-10-27" }), "mytool 1.4.2 (a1b2c3d 2026-10-27)");
  });
  test("dirty builds", () => {
    assert.equal(formatVersion("mytool", { version: "1.4.2", commit: "a1b2c3d4e5f6", date: "2026-10-27", dirty: true }), "mytool 1.4.2 (a1b2c3d-dirty 2026-10-27)");
  });
  test("no commit: no empty parentheses", () => {
    assert.equal(formatVersion("mytool", { version: "1.4.2" }), "mytool 1.4.2");
  });
});

describe("detectInstall", () => {
  test("checkout wins", () => assert.equal(detectInstall("/Users/u/src/tool", true), "checkout"));
  test("npx", () => assert.equal(detectInstall("/Users/u/.npm/_npx/abc/node_modules/tool", false), "npx"));
  test("mise", () => assert.equal(detectInstall("/Users/u/.local/share/mise/installs/npm-tool/1.0.0/lib/node_modules/tool", false), "mise"));
  test("bun", () => assert.equal(detectInstall("/Users/u/.bun/install/global/node_modules/tool", false), "bun"));
  test("pnpm", () => assert.equal(detectInstall("/Users/u/.local/share/pnpm/global/5/node_modules/tool", false), "pnpm"));
  test("npm global", () => assert.equal(detectInstall("/usr/lib/node_modules/tool", false, "/usr/lib/node_modules"), "npm"));
  test("project dependency is unknown", () => assert.equal(detectInstall("/proj/node_modules/tool", false, "/usr/lib/node_modules"), "unknown"));
});

describe("updateSteps", () => {
  test("registry installs use @latest", () => {
    assert.deepEqual(updateSteps("npm", meta()), [{ cmd: "npm", args: ["install", "-g", "@scope/tool@latest"] }]);
    assert.deepEqual(updateSteps("mise", meta()), [{ cmd: "mise", args: ["upgrade", "--bump", "npm:@scope/tool"] }]);
  });
  test("private packages reinstall from git, never from the registry", () => {
    const priv = meta({ isPrivate: true, repositoryUrl: "github:o/r" });
    const url = "git+https://github.com/o/r.git";
    assert.deepEqual(updateSteps("npm", priv), [{ cmd: "npm", args: ["install", "-g", url] }]);
    assert.deepEqual(updateSteps("pnpm", priv), [{ cmd: "pnpm", args: ["add", "-g", url] }]);
    assert.deepEqual(updateSteps("bun", priv), [{ cmd: "bun", args: ["add", "-g", url] }]);
    assert.equal(updateSteps("mise", priv), null);
    assert.equal(updateSteps("npm", meta({ isPrivate: true })), null);
  });
  test("checkout pulls, installs and builds with its package manager", () => {
    assert.deepEqual(updateSteps("checkout", meta(), "pnpm").map((s) => [s.cmd, ...s.args].join(" ")), [
      "git pull --ff-only",
      "pnpm install",
      "pnpm run build",
    ]);
  });
  test("unknown and npx have no steps", () => {
    assert.equal(updateSteps("unknown", meta()), null);
    assert.equal(updateSteps("npx", meta()), null);
  });
});

test("repository URLs normalize once for git and for installers", () => {
  for (const [input, clone] of [
    ["github:o/r", "https://github.com/o/r.git"],
    ["o/r", "https://github.com/o/r.git"],
    ["o/r.git", "https://github.com/o/r.git"],
    ["git@github.com:o/r.git", "ssh://git@github.com/o/r.git"],
    ["https://github.com/o/r.git", "https://github.com/o/r.git"],
    ["git+https://github.com/o/r.git", "https://github.com/o/r.git"],
    ["git+ssh://git@github.com/o/r.git", "ssh://git@github.com/o/r.git"],
  ]) {
    assert.equal(gitCloneUrl(input), clone, input);
    assert.equal(gitInstallUrl(input), `git+${clone}`, input);
  }
});

test("compareVersions", () => {
  assert.ok(compareVersions("1.2.3", "1.10.0") < 0);
  assert.ok(compareVersions("2.0.0", "1.99.99") > 0);
  assert.equal(compareVersions("v1.0.0", "1.0.0"), 0);
  assert.ok(compareVersions("1.0.0-alpha", "1.0.0") < 0);
});

describe("packageMeta and buildInfo", () => {
  test("walks up to package.json and prefers the stamp", () => {
    const root = mkTemp();
    mkdirSync(join(root, "dist", "cli"), { recursive: true });
    writeFileSync(join(root, "package.json"), JSON.stringify({ name: "t", version: "2.0.0", private: true, repository: { url: "github:o/r" } }));
    writeFileSync(join(root, "dist", "build-info.json"), JSON.stringify({ version: "2.0.0", commit: "f".repeat(40), date: "2026-01-02", dirty: false }));
    const m = packageMeta(join(root, "dist", "cli"));
    assert.equal(m.name, "t");
    assert.equal(m.isPrivate, true);
    assert.equal(m.repositoryUrl, "github:o/r");
    assert.equal(formatVersion("t", buildInfo(m)), "t 2.0.0 (fffffff 2026-01-02)");
  });
  test("falls back to git in a checkout without a build", () => {
    const root = mkTemp();
    writeFileSync(join(root, "package.json"), JSON.stringify({ name: "t", version: "0.1.0" }));
    sh(root, "git", ["init", "-q", "-b", "main"]);
    sh(root, "git", ["add", "-A"]);
    sh(root, "git", ["commit", "-q", "-m", "init"]);
    const info = buildInfo(packageMeta(root));
    assert.equal(info.commit, sh(root, "git", ["rev-parse", "HEAD"]));
    assert.equal(info.dirty, false);
  });
  test("in a checkout, dist/ reports the stamp and src/ reads git", () => {
    const root = mkTemp();
    mkdirSync(join(root, "src"));
    mkdirSync(join(root, "dist"));
    writeFileSync(join(root, "package.json"), JSON.stringify({ name: "t", version: "0.1.0" }));
    writeFileSync(join(root, ".gitignore"), "dist/\n");
    writeFileSync(join(root, "dist", "build-info.json"), JSON.stringify({ version: "0.1.0", commit: "e".repeat(40), date: "2026-01-01", dirty: false }));
    sh(root, "git", ["init", "-q", "-b", "main"]);
    sh(root, "git", ["add", "-A"]);
    sh(root, "git", ["commit", "-q", "-m", "init"]);
    writeFileSync(join(root, "src", "edited.ts"), "x");
    const m = packageMeta(root);
    assert.equal(buildInfo(m, join(root, "dist")).commit, "e".repeat(40));
    const fromSource = buildInfo(m, join(root, "src"));
    assert.equal(fromSource.commit, sh(root, "git", ["rev-parse", "HEAD"]));
    assert.equal(fromSource.dirty, true);
  });
  test("version only outside git", () => {
    const root = mkTemp();
    writeFileSync(join(root, "package.json"), JSON.stringify({ name: "t", version: "0.1.0" }));
    assert.deepEqual(buildInfo(packageMeta(root)), { version: "0.1.0" });
  });
});

describe("checkForUpdate in a checkout", () => {
  // A clone of a one-commit origin, with dist/ stamped at `stampAt` (a commit id or "head").
  const clone = (stampAt: "head" | string) => {
    const origin = mkTemp();
    writeFileSync(join(origin, "package.json"), JSON.stringify({ name: "t", version: "0.1.0" }));
    writeFileSync(join(origin, ".gitignore"), "dist/\n");
    sh(origin, "git", ["init", "-q", "-b", "main"]);
    sh(origin, "git", ["add", "-A"]);
    sh(origin, "git", ["commit", "-q", "-m", "init"]);
    const root = join(mkTemp(), "clone");
    sh(origin, "git", ["clone", "-q", origin, root]);
    const head = sh(root, "git", ["rev-parse", "HEAD"]);
    mkdirSync(join(root, "dist"));
    const commit = stampAt === "head" ? head : stampAt;
    writeFileSync(join(root, "dist", "build-info.json"), JSON.stringify({ version: "0.1.0", commit, date: "2026-01-01", dirty: false }));
    const m = packageMeta(root);
    return { m, head, status: () => checkForUpdate("checkout", m, buildInfo(m, join(root, "dist"))) };
  };
  test("current build: up to date", () => {
    const { status } = clone("head");
    assert.equal(status().available, false);
  });
  test("build older than the checkout (pull done, build failed): update available", () => {
    const { status, head } = clone("a".repeat(40));
    const s = status();
    assert.equal(s.available, true);
    assert.equal(s.current, "aaaaaaa");
    assert.equal(s.latest, head.slice(0, 7));
    assert.match(s.note ?? "", /build is older/);
  });
});

// End to end: a tiny CLI using the real cli-meta (types stripped to JS), packed and smoke-tested by
// the canonical test-package.sh, which runs prepack → build-info.mjs and checks the --version line.
test("test-package.sh accepts a stamped build and rejects a missing stamp", () => {
  const root = mkTemp();
  mkdirSync(join(root, "scripts"));
  mkdirSync(join(root, "lib"));
  copyFileSync(join(templates, "node", "build-info.mjs"), join(root, "scripts", "build-info.mjs"));
  copyFileSync(join(templates, "node", "test-package.sh"), join(root, "scripts", "test-package.sh"));
  const source = readFileSync(join(templates, "node", "cli-meta.ts"), "utf8");
  writeFileSync(join(root, "lib", "cli-meta.js"), stripTypeScriptTypes(source));
  writeFileSync(
    join(root, "lib", "cli.js"),
    `#!/usr/bin/env node
import { versionLine } from "./cli-meta.js";
if (process.argv.includes("--version")) console.log(versionLine("fixture"));
else console.log("usage: fixture");
`,
  );
  const pkg = {
    name: "release-standard-fixture",
    version: "1.2.3",
    type: "module",
    bin: { fixture: "lib/cli.js", fx: "lib/cli.js" },
    files: ["lib", "dist"],
    scripts: { build: "node scripts/build-info.mjs", prepack: "npm run build" },
  };
  writeFileSync(join(root, "package.json"), JSON.stringify(pkg, null, 2));
  writeFileSync(join(root, ".gitignore"), "dist/\n");
  sh(root, "git", ["init", "-q", "-b", "main"]);
  sh(root, "git", ["add", "-A"]);
  sh(root, "git", ["commit", "-q", "-m", "init"]);

  const out = sh(root, "bash", ["scripts/test-package.sh"]);
  assert.match(out, /Package smoke test passed/);

  writeFileSync(join(root, "package.json"), JSON.stringify({ ...pkg, files: ["lib"] }, null, 2));
  assert.throws(() => sh(root, "bash", ["scripts/test-package.sh"]), /expected '<name> X\.Y\.Z/);
});

// release.mjs with stub `npm` and `release-it` executables: the preflight gates the publish, and the
// publish happens only after release-it has tagged the release commit.
describe("release.mjs", () => {
  const script = join(templates, "node", "release.mjs");
  const setup = (pkg: Record<string, unknown> = { name: "t", version: "1.0.0" }) => {
    const root = mkTemp();
    const bin = join(root, "stub-bin");
    const log = join(root, "calls.log");
    mkdirSync(bin);
    mkdirSync(join(root, "node_modules", ".bin"), { recursive: true });
    // npm: logged in, version not on the registry yet, publish recorded.
    writeFileSync(join(bin, "npm"), `#!/usr/bin/env bash
echo "npm $*" >> "${log}"
case "$1" in
  whoami) echo tester ;;
  view) echo "npm error code E404" >&2; exit 1 ;;
esac
`);
    // release-it: bump to 1.0.1, commit and tag, as the real one does (dry runs change nothing).
    writeFileSync(join(root, "node_modules", ".bin", "release-it"), `#!/usr/bin/env bash
echo "release-it $*" >> "${log}"
for a in "$@"; do [[ "$a" == --dry-run ]] && exit 0; done
node -e 'const f="package.json",p=JSON.parse(require("fs").readFileSync(f));p.version="1.0.1";require("fs").writeFileSync(f,JSON.stringify(p))'
git commit -qam "chore: release v1.0.1" && git tag -a v1.0.1 -m "Release 1.0.1"
`);
    chmodSync(join(bin, "npm"), 0o755);
    chmodSync(join(root, "node_modules", ".bin", "release-it"), 0o755);
    writeFileSync(join(root, "package.json"), JSON.stringify(pkg));
    writeFileSync(join(root, ".gitignore"), "node_modules/\nstub-bin/\ncalls.log\n");
    sh(root, "git", ["init", "-q", "-b", "main"]);
    sh(root, "git", ["add", "-A"]);
    sh(root, "git", ["commit", "-q", "-m", "init"]);
    const runIt = (...args: string[]) =>
      spawnSync(process.execPath, [script, ...args], {
        cwd: root,
        encoding: "utf8",
        env: { ...gitEnv, PATH: `${bin}:${process.env.PATH}` },
      });
    const calls = () => (existsSync(log) ? readFileSync(log, "utf8") : "");
    return { root, runIt, calls };
  };

  test("prints usage without a command", () => {
    const { runIt } = setup();
    const r = runIt();
    assert.equal(r.status, 1);
    assert.match(r.stderr, /usage: node scripts\/release\.mjs/);
  });

  test("publish refuses an untagged HEAD", () => {
    const { runIt, calls } = setup();
    const r = runIt("publish");
    assert.equal(r.status, 1);
    assert.match(r.stderr, /HEAD is not tagged v1\.0\.0/);
    assert.doesNotMatch(calls(), /npm publish/);
  });

  test("a dry run never publishes", () => {
    const { runIt, calls } = setup();
    assert.equal(runIt("release", "--dry-run").status, 0);
    assert.match(calls(), /release-it --dry-run/);
    assert.doesNotMatch(calls(), /npm publish/);
  });

  test("release publishes after release-it tags, without --access", () => {
    const { runIt, calls } = setup();
    const r = runIt("release", "patch");
    assert.equal(r.status, 0, r.stderr);
    const log = calls();
    assert.ok(log.indexOf("release-it patch") < log.indexOf("npm publish"), log);
    assert.match(log, /^npm publish$/m);
  });

  test("refuses to release when HEAD is already the release", () => {
    const { root, runIt, calls } = setup();
    sh(root, "git", ["tag", "-a", "v1.0.0", "-m", "Release 1.0.0"]);
    const r = runIt("release");
    assert.equal(r.status, 1);
    assert.match(r.stderr, /already the v1\.0\.0 release/);
    assert.doesNotMatch(calls(), /release-it/);
  });

  test("a private package is released but never published", () => {
    const { runIt, calls } = setup({ name: "t", version: "1.0.0", private: true });
    assert.equal(runIt("release", "patch").status, 0);
    assert.doesNotMatch(calls(), /npm (publish|whoami)/);
  });
});
