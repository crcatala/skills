#!/usr/bin/env bash
# Validate every skill against the Agent Skills specification plus repo conventions.
#
# Spec validation uses the reference validator (`skills-ref`, run via uvx). That
# validator only knows core spec fields and rejects harness extensions such as
# `disable-model-invocation`, so a copy of each SKILL.md with the known
# extension fields removed is validated instead. The checked-in files are not
# modified.
#
# Usage: scripts/validate.sh [skill-dir ...]   (default: every skill under skills/)
# Env:   SKILLS_REF="uvx --from skills-ref agentskills"   override the validator command

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_REF="${SKILLS_REF:-uvx --from skills-ref agentskills}"
# Frontmatter keys supported by harnesses (Claude Code, pi) but not by the core spec.
HARNESS_EXTENSIONS='disable-model-invocation|argument-hint'
MAX_SKILL_LINES=500

errors=0
warnings=0
err()  { echo "  ✗ $*"; errors=$((errors + 1)); }
warn() { echo "  ! $*"; warnings=$((warnings + 1)); }

if [ "$#" -gt 0 ]; then
    skill_dirs=("$@")
else
    mapfile -t skill_dirs < <(find "$ROOT/skills" -name SKILL.md -not -path '*/node_modules/*' -printf '%h\n' | sort)
fi

if [ "${#skill_dirs[@]}" -eq 0 ]; then
    echo "No skills found" >&2
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

for dir in "${skill_dirs[@]}"; do
    name="$(basename "$dir")"
    echo "• $name"

    # 1. Spec validation on a copy without harness-extension keys.
    mkdir -p "$tmp/$name"
    awk -v ext="^($HARNESS_EXTENSIONS):" '
        NR == 1 && /^---$/ { infm = 1; print; next }
        infm && /^---$/    { infm = 0; print; next }
        infm && $0 ~ ext   { next }
        { print }
    ' "$dir/SKILL.md" > "$tmp/$name/SKILL.md"
    if ! out="$($SKILLS_REF validate "$tmp/$name" 2>&1)"; then
        err "spec: ${out//$'\n'/$'\n    '}"
    fi

    # 2. SKILL.md length (progressive disclosure: move detail into references/).
    lines="$(wc -l < "$dir/SKILL.md")"
    [ "$lines" -le "$MAX_SKILL_LINES" ] || warn "SKILL.md is $lines lines (> $MAX_SKILL_LINES); consider moving detail to references/"

    # 3. Layout: skills/<name> or skills/.experimental/<name> only. Stable skills
    #    must be in the README catalog; experimental ones must not be.
    rel="${dir#"$ROOT"/}"
    experimental=0
    if [[ "$rel" == skills/* ]]; then
        [[ "$rel" =~ ^skills/(\.experimental/)?[^/]+$ ]] || err "unsupported location '$rel' (use skills/<name> or skills/.experimental/<name>)"
        [[ "$rel" == skills/.experimental/* ]] && experimental=1
    fi
    if [ "$experimental" -eq 1 ]; then
        ! grep -q "\`$name\`" "$ROOT/README.md" || err "experimental skills must not be listed in README.md"
    else
        grep -q "\`$name\`" "$ROOT/README.md" || err "not listed in README.md (add it as \`$name\`)"
    fi

    # 4. No Claude-only features: skills are shared with pi and other harnesses.
    #    Invocation text arrives as appended instructions, not via placeholders.
    claude_only="$(grep -nE '\$ARGUMENTS|\$\{CLAUDE_|^context:[[:space:]]*fork|!`[^`]+`' "$dir/SKILL.md" || true)"
    [ -z "$claude_only" ] || err "Claude-only feature(s) in SKILL.md (see docs/authoring.md):"$'\n'"$(sed 's/^/    /' <<<"$claude_only")"

    # 5. User-invoked skills must end with the standard note about invocation text.
    if grep -q '^disable-model-invocation:[[:space:]]*true' "$dir/SKILL.md"; then
        grep -qE 'extra context or instructions for this task|text supplied when this skill was invoked' "$dir/SKILL.md" \
            || err "user-invoked skill is missing the standard invocation-text note (see docs/authoring.md)"
    fi

    # 6. No environment-specific paths or hosts leaking into a portable skill.
    leaks="$(grep -rnIE '/home/[a-z]|/opt/agent' "$dir" --exclude-dir=node_modules --exclude-dir=__pycache__ || true)"
    [ -z "$leaks" ] || err "environment-specific reference(s):"$'\n'"$(sed 's/^/    /' <<<"$leaks")"
done

# 7. Generated or vendored junk must not be tracked.
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    junk="$(git -C "$ROOT" ls-files | grep -E '(^|/)(node_modules|__pycache__)/|\.pyc$' || true)"
    [ -z "$junk" ] || err "tracked generated files:"$'\n'"$(sed 's/^/    /' <<<"$junk")"
fi

echo
echo "${#skill_dirs[@]} skill(s) checked: $errors error(s), $warnings warning(s)"
[ "$errors" -eq 0 ]
