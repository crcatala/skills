#!/usr/bin/env bash
# independent-pr-review: Antigravity CLI detection, setup checks and the two-turn run,
# against a fake CLI. No network, credentials or real reviewer CLI needed.
set -euo pipefail

script="$(cd "$(dirname "$0")/.." && pwd)/skills/independent-pr-review/scripts/run-review.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
expect() { # <description> <haystack> <needle>
    [[ "$2" == *"$3"* ]] || fail "$1: expected '$3' in: $2"
}
reject() { # <description> <haystack> <needle>
    [[ "$2" != *"$3"* ]] || fail "$1: did not expect '$3' in: $2"
}

# Fake Antigravity CLI. FAKE_AGY_MODE picks how `models` answers; every call is logged.
mkdir -p "$tmp/bin"
cat > "$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_AGY_LOG"
case "$1" in
    --help) echo "  --print   Run a single prompt non-interactively"; exit 2 ;;
    models)
        echo "Fetching available models..."
        case "${FAKE_AGY_MODE:-ready}" in
            signed-out) echo "Error: Please sign in to view available models."; exit 1 ;;
            broken) echo "Error: network unreachable"; exit 3 ;;
            hang) sleep 30 ;;
            *) echo "gemini-4-neon-medium	Gemini 4 Neon (Medium)" ;;
        esac
        exit 0 ;;
esac
for arg in "$@"; do [ "$arg" = --conversation ] && turn=triage; done
echo "{\"conversation_id\":\"conv-123\",\"status\":\"SUCCESS\",\"response\":\"${turn:-review} reply\"}"
EOF
chmod +x "$tmp/bin/agy"

# A repository to run in, and an environment without any real CLI, config or T3 install.
git init -q "$tmp/repo"
git -C "$tmp/repo" -c user.name=t -c user.email=t@example.invalid commit -q --allow-empty -m init
export HOME="$tmp/home" XDG_DATA_HOME="$tmp/data" FAKE_AGY_LOG="$tmp/agy.log"
export INDEPENDENT_PR_REVIEW_CONFIG="$tmp/no-config.json" INDEPENDENT_PR_REVIEW_OUTPUT_DIR="$tmp/out"
unset T3CODE_HOME ANTIGRAVITY_CLI FAKE_AGY_MODE
base_path="/usr/bin:/bin"
cd "$tmp/repo"

list() { PATH="$base_path" bash "$script" --list 2>&1 || true; }

# Not found anywhere.
out="$(list)"
expect "missing CLI" "$out" "antigravity CLI: not found"
expect "missing CLI hint" "$out" "Set up Antigravity in T3 Code"

# agy on PATH, even though its --help exits non-zero.
out="$(PATH="$tmp/bin:$base_path" bash "$script" --list)"
expect "agy on PATH" "$out" "antigravity CLI: $tmp/bin/agy"
expect "ready" "$out" "  ready"

# ANTIGRAVITY_CLI, signed out, no T3 sign-in.
out="$(ANTIGRAVITY_CLI="$tmp/bin/agy" FAKE_AGY_MODE=signed-out list)"
expect "signed out" "$out" "Antigravity CLI is not signed in. Sign it in once per machine"
reject "signed out without T3" "$out" "T3 Code does not count"
reject "signed out is not ready" "$out" "  ready"

# A failed check is reported, not taken as ready.
out="$(ANTIGRAVITY_CLI="$tmp/bin/agy" FAKE_AGY_MODE=broken list)"
expect "failed check" "$out" "models exited 3: Error: network unreachable"
reject "failed check is not ready" "$out" "  ready"

# A stuck check times out (needs timeout or gtimeout).
if command -v timeout >/dev/null || command -v gtimeout >/dev/null; then
    out="$(ANTIGRAVITY_CLI="$tmp/bin/agy" FAKE_AGY_MODE=hang INDEPENDENT_PR_REVIEW_CHECK_TIMEOUT=1 list)"
    expect "timed-out check" "$out" "models timed out after 1s"
fi

# T3 Code's managed copy and its own sign-in.
case "$(uname -s)" in Linux) os=linux ;; Darwin) os=darwin ;; *) os=other ;; esac
case "$(uname -m)" in x86_64|amd64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; *) arch=other ;; esac
t3="$tmp/t3"
mkdir -p "$t3/tools/antigravity-acp/$os-$arch/versions/rel1" "$t3/userdata/providers/antigravity/k/antigravity-acp"
cp "$tmp/bin/agy" "$t3/tools/antigravity-acp/$os-$arch/versions/rel1/antigravity"
echo '{"releaseId":"rel1"}' > "$t3/tools/antigravity-acp/$os-$arch/active.json"
echo '{"token":{}}' > "$t3/userdata/providers/antigravity/k/antigravity-acp/antigravity-oauth-token"
if [ "$os" != other ] && [ "$arch" != other ]; then
    out="$(T3CODE_HOME="$t3" FAKE_AGY_MODE=signed-out list)"
    expect "T3 copy" "$out" "antigravity CLI: $t3/tools/antigravity-acp/$os-$arch/versions/rel1/antigravity"
    expect "T3 sign-in does not carry over" "$out" "Being signed in to Antigravity in T3 Code does not count"
fi

# A signed-out reviewer fails at once with the setup message.
set +e
out="$(ANTIGRAVITY_CLI="$tmp/bin/agy" FAKE_AGY_MODE=signed-out PATH="$base_path" bash "$script" --reviewers antigravity-neon 2>&1)"
code=$?
set -e
[ "$code" -eq 1 ] || fail "signed-out run: expected exit 1, got $code"
expect "signed-out run" "$out" "antigravity-neon: failed setup needed: Antigravity CLI is not signed in"

# A full run: review turn, then triage resuming the review's conversation.
: > "$FAKE_AGY_LOG"
out="$(ANTIGRAVITY_CLI="$tmp/bin/agy" PATH="$base_path" bash "$script" --reviewers antigravity-neon)"
expect "run ok" "$out" "antigravity-neon: ok"
expect "resume command" "$out" "resume: $tmp/bin/agy --conversation conv-123"
triage="$(sed -n 's/^  triage: //p' <<<"$out")"
[ "$(cat "$triage")" = "triage reply" ] || fail "triage reply: got $(cat "$triage")"
calls="$(cat "$FAKE_AGY_LOG")"
expect "review turn model" "$calls" "--model gemini-4-neon --effort medium --print=Review the PR"
expect "triage resumes review" "$calls" "--conversation conv-123 --print="

echo 'independent-pr-review antigravity checks passed'
