#!/usr/bin/env bash
set -euo pipefail

# Static checks for retained policies/notices, not legal or CLI behavior tests.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for skill in brave-web ticket agent-browser; do
    test -f "skills/$skill/THIRD_PARTY_NOTICE.md"
    grep -Fq '[THIRD_PARTY_NOTICE.md](THIRD_PARTY_NOTICE.md)' "skills/$skill/SKILL.md"
done

grep -Fq 'Copyright (c) 2024 Mario Zechner' skills/brave-web/THIRD_PARTY_NOTICE.md
grep -Fxq 'Copyright (c) 2025' skills/ticket/THIRD_PARTY_NOTICE.md
grep -Fq 'Apache-2.0' skills/agent-browser/THIRD_PARTY_NOTICE.md
grep -Fq 'Copyright 2025 Vercel Inc.' skills/agent-browser/LICENSE
! grep -Fq 'Provenance still to confirm before publishing' NOTICE.md

browser=skills/agent-browser/SKILL.md
for reference in \
    'session id --scope worktree --prefix qa-account-form' \
    'agent-browser snapshot -i' \
    'agent-browser skills get core' \
    'agent-browser skills get core --full' \
    'agent-browser skills get dogfood' \
    'agent-browser --help' \
    'agent-browser doctor'; do
    grep -Fq -- "$reference" "$browser"
done
for policy in \
    '**every** browser shell call' \
    'Before `screenshot --full`' \
    'Inspect every screenshot before sharing' \
    'public-page reading' \
    'a successful API or WebMCP' \
    'Batch' \
    '--password-stdin' \
    '--restore' \
    'not permission to act'; do
    grep -Fq -- "$policy" "$browser"
done
! grep -Fq '## Working command reference' "$browser"

grep -Fq 'tk help' skills/ticket/SKILL.md
grep -Fq 'do not modify or stage `.tickets/`' skills/ticket/SKILL.md

# Retired skills must disappear, not remain discoverable in another directory.
test ! -d skills/opentui
! grep -R -Eq '^name: opentui$' skills --include=SKILL.md
grep -Fq 'npx skills add anomalyco/opentui --skill opentui' README.md
! grep -Fq '(skills/opentui/' README.md NOTICE.md

echo 'publication content checks passed'
