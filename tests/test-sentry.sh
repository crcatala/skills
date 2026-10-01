#!/usr/bin/env bash
set -euo pipefail

# Check the read-only policy and reference delegation without running the CLI.
skill="$(cd "$(dirname "$0")/.." && pwd)/skills/sentry/SKILL.md"

for required in \
    'sentry auth status' \
    'sentry auth login --read-only' \
    'sentry issue events --help' \
    'sentry log list --help' \
    'sentry explore --help' \
    'sentry docs --help' \
    'sentry docs list' \
    'sentry docs query' \
    'https://cli.sentry.dev/' \
    'https://docs.sentry.io/' \
    'Never use it to resolve, reopen, archive, merge, or otherwise change Sentry issues' \
    'Do not use the legacy `sentry-cli` executable or `~/.sentryclirc`' \
    'Never run issue mutations' \
    'Do not install the broad official skill' \
    'Seer' \
    'not implicit authorization' \
    'Never include auth tokens, DSNs, cookies, or sensitive request fields'; do
    grep -Fq "$required" "$skill"
done
# Allow line wrapping while checking the setup and streaming boundaries.
grep -Fq 'Do not run `sentry cli setup`' <(tr '\n' ' ' < "$skill")
grep -Fq 'without a request for a live investigation' "$skill"
! grep -Fq '| Question | Command example |' "$skill"
! find "$(dirname "$skill")" -mindepth 1 -type f ! -name SKILL.md -print -quit | grep -q .

echo 'sentry policy checks passed'
