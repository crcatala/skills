// Tests for templates/node/release.mjs: the publish step, run against a fake `npm` on PATH.
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, test } from "node:test";
import { fileURLToPath } from "node:url";

const templates = fileURLToPath(new URL("../templates/", import.meta.url));
const temp: string[] = [];
after(() => temp.forEach((d) => rmSync(d, { recursive: true, force: true })));

const gitEnv = {
  ...process.env,
  GIT_AUTHOR_NAME: "t",
  GIT_AUTHOR_EMAIL: "t@example.com",
  GIT_COMMITTER_NAME: "t",
  GIT_COMMITTER_EMAIL: "t@example.com",
  GIT_CONFIG_GLOBAL: "/dev/null",
};

// A repository at `version`, tagged v<version>, and a fake npm that is logged in, finds nothing on
// the registry and records the arguments of `npm publish`.
function fixture(version: string) {
  const dir = mkdtempSync(join(tmpdir(), "release-standard-"));
  temp.push(dir);
  const root = join(dir, "repo");
  const bin = join(dir, "bin");
  mkdirSync(join(root, "scripts"), { recursive: true });
  mkdirSync(bin);
  copyFileSync(join(templates, "node", "release.mjs"), join(root, "scripts", "release.mjs"));
  writeFileSync(join(root, "package.json"), JSON.stringify({ name: "fixture", version }));
  const sh = (cmd: string, args: string[]) => execFileSync(cmd, args, { cwd: root, env: gitEnv, stdio: "ignore" });
  sh("git", ["init", "-q", "-b", "main"]);
  sh("git", ["add", "-A"]);
  sh("git", ["commit", "-q", "-m", `chore: release v${version}`]);
  sh("git", ["tag", "-a", `v${version}`, "-m", `Release ${version}`]);
  const log = join(dir, "publish.log");
  writeFileSync(
    join(bin, "npm"),
    `#!/usr/bin/env bash
case "$1" in
  whoami) echo tester ;;
  view) echo "npm error code E404" >&2; exit 1 ;;
  publish) echo "$*" > "${log}" ;;
esac
`,
  );
  chmodSync(join(bin, "npm"), 0o755);
  const publish = (...args: string[]) => {
    const r = spawnSync("node", ["scripts/release.mjs", "publish", ...args], {
      cwd: root,
      env: { ...gitEnv, PATH: `${bin}:${process.env.PATH}` },
      encoding: "utf8",
    });
    let published: string | undefined;
    try {
      published = readFileSync(log, "utf8").trim();
    } catch {}
    return { status: r.status, stderr: r.stderr, published };
  };
  return { publish };
}

describe("release.mjs publish", () => {
  test("a release publishes without a dist-tag (latest)", () => {
    const r = fixture("1.2.0").publish();
    assert.equal(r.status, 0, r.stderr);
    assert.equal(r.published, "publish");
  });
  test("a prerelease publishes under its identifier", () => {
    const r = fixture("1.3.0-beta.1").publish();
    assert.equal(r.status, 0, r.stderr);
    assert.equal(r.published, "publish --tag beta");
  });
  test("a numeric prerelease publishes under next", () => {
    assert.equal(fixture("1.3.0-0").publish().published, "publish --tag next");
  });
  test("--tag overrides, in both forms", () => {
    assert.equal(fixture("1.3.0-beta.1").publish("--tag", "rc").published, "publish --tag rc");
    assert.equal(fixture("1.2.0").publish("--tag=legacy").published, "publish --tag legacy");
  });
  test("--tag without a value refuses to publish", () => {
    const r = fixture("1.2.0").publish("--tag");
    assert.equal(r.status, 1);
    assert.match(r.stderr, /--tag needs a value/);
    assert.equal(r.published, undefined);
  });
  test("--dry-run keeps the dist-tag", () => {
    assert.equal(fixture("2.0.0-alpha.0").publish("--dry-run").published, "publish --tag alpha --dry-run");
  });
});
