#!/usr/bin/env node
// release-standard: scripts/release.mjs r1 (do not edit; see RELEASING.md)
//
//   node scripts/release.mjs release [release-it args]   preflight, release-it (bump, changelog, tag, push,
//                                                         GitHub Release), then publish from the tag
//   node scripts/release.mjs publish [--dry-run]         publish the tagged HEAD to npm (resume a release)
//
// release-it publishes to npm before it commits and tags, so its npm step is turned off in
// .release-it.json and this script publishes afterwards: the published build is stamped with the
// release commit and a clean tree. A package with "private": true is never published.
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const pkg = () => JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const fail = (msg) => {
  console.error(msg);
  process.exit(1);
};

function out(cmd, args) {
  try {
    return execFileSync(cmd, args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  } catch {
    return null;
  }
}

// true: on npm, false: not on npm (E404), null: could not tell (network, auth).
function publishedOnNpm(name, version) {
  const r = spawnSync('npm', ['view', `${name}@${version}`, 'version'], { cwd: root, encoding: 'utf8' });
  if (r.status === 0) return r.stdout.trim() === version;
  return /E404/.test(r.stderr) ? false : null;
}

function publish({ dryRun, resumeHint }) {
  const { name, version, private: isPrivate } = pkg();
  if (isPrivate) {
    console.error(`${name} is private; nothing to publish.`);
    return;
  }
  const tag = `v${version}`;
  const problems = [];
  const tagsAtHead = (out('git', ['tag', '--points-at', 'HEAD']) ?? '').split('\n');
  if (!tagsAtHead.includes(tag)) problems.push(`HEAD is not tagged ${tag}; publish only from the release commit.`);
  if (out('git', ['status', '--porcelain']) !== '') problems.push('the working tree is not clean.');
  const user = out('npm', ['whoami']);
  if (!user) problems.push('not logged in to npm (run `npm login`).');
  const published = publishedOnNpm(name, version);
  if (published === true) problems.push(`${name}@${version} is already on npm.`);
  if (published === null) problems.push(`could not check whether ${name}@${version} is on npm (network?).`);
  if (problems.length > 0) {
    fail(`Not publishing ${name}@${version}:\n${problems.map((p) => `  - ${p}`).join('\n')}\n${resumeHint}`);
  }
  console.error(`Publishing ${name}@${version} as ${user}${dryRun ? ' (dry run)' : ''}...`);
  // Inherit stdio: npm asks for a one-time password or opens a browser here when the account uses 2FA.
  const r = spawnSync('npm', ['publish', '--access', 'public', ...(dryRun ? ['--dry-run'] : [])], {
    cwd: root,
    stdio: 'inherit',
  });
  if (r.status !== 0) fail(`npm publish failed. ${resumeHint}`);
  if (!dryRun) console.error(`Published. Check: npm view ${name}@${version}`);
}

const [command, ...rest] = process.argv.slice(2);
switch (command) {
  case 'release': {
    const info = rest.some((a) => ['--help', '-h', '--version', '-v', '--release-version', '--changelog'].includes(a));
    const dryRun = rest.some((a) => a === '--dry-run' || a === '-d');
    const { name, version, private: isPrivate } = pkg();
    if (!info) {
      const problems = [];
      if ((out('git', ['tag', '--points-at', 'HEAD']) ?? '').split('\n').includes(`v${version}`)) {
        problems.push(`HEAD is already the v${version} release. If only the npm publish failed, run \`npm run release:publish\`.`);
      }
      if (!isPrivate && !out('npm', ['whoami'])) problems.push('not logged in to npm (run `npm login`); the publish step needs it.');
      if (problems.length > 0) fail(`Not releasing ${name}:\n${problems.map((p) => `  - ${p}`).join('\n')}`);
    }
    const bin = path.join(root, 'node_modules', '.bin', process.platform === 'win32' ? 'release-it.cmd' : 'release-it');
    const r = spawnSync(bin, rest, { cwd: root, stdio: 'inherit' });
    if (r.error) fail(`could not run release-it (${r.error.message}); install dev dependencies first.`);
    if (r.status !== 0) process.exit(r.status ?? 1);
    if (info || dryRun) break;
    publish({
      dryRun: false,
      resumeHint: 'The release commit, tag and GitHub Release are done; only the npm publish is left. Fix this, then run `npm run release:publish`.',
    });
    break;
  }
  case 'publish':
    publish({ dryRun: rest.includes('--dry-run'), resumeHint: 'Fix this, then run `npm run release:publish` again.' });
    break;
  default:
    fail('usage: node scripts/release.mjs release [release-it args] | publish [--dry-run]  (see RELEASING.md)');
}
