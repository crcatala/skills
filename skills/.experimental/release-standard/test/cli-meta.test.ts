// Tests for templates/node: cli-meta.ts, build-info.mjs and test-package.sh. Node 22.18+ (type stripping).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  buildInfo,
  compareVersions,
  detectInstall,
  formatVersion,
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
  test("private npm installs reinstall from git", () => {
    const steps = updateSteps("npm", meta({ isPrivate: true, repositoryUrl: "git+https://github.com/o/r.git" }));
    assert.deepEqual(steps, [{ cmd: "npm", args: ["install", "-g", "git+https://github.com/o/r.git"] }]);
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

test("gitInstallUrl", () => {
  assert.equal(gitInstallUrl("github:o/r"), "git+https://github.com/o/r.git");
  assert.equal(gitInstallUrl("https://github.com/o/r.git"), "git+https://github.com/o/r.git");
  assert.equal(gitInstallUrl("git+ssh://git@github.com/o/r.git"), "git+ssh://git@github.com/o/r.git");
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
  test("version only outside git", () => {
    const root = mkTemp();
    writeFileSync(join(root, "package.json"), JSON.stringify({ name: "t", version: "0.1.0" }));
    assert.deepEqual(buildInfo(packageMeta(root)), { version: "0.1.0" });
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

test("release.mjs parses and prints usage", () => {
  const root = mkTemp();
  writeFileSync(join(root, "package.json"), JSON.stringify({ name: "t", version: "1.0.0" }));
  const script = join(templates, "node", "release.mjs");
  sh(root, process.execPath, ["--check", script]);
  assert.throws(() => sh(root, process.execPath, [script]), /usage: node scripts\/release\.mjs/);
});
