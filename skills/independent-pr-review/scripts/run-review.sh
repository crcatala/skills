#!/usr/bin/env bash
# Run one or more independent PR reviewers (codex, claude, pi) without a UI, in parallel.
# Each reviewer gets two turns in one session: the review prompt, then the triage prompt.
# The triage reply is written to a file the calling agent reads.
#
# Usage:
#   run-review.sh [--reviewers a,b | --all] [--pr <number|url>] [--note <text>]
#   run-review.sh --list
#
# A reviewer is a name from the config, or an ad-hoc spec harness:model[:effort]
# (e.g. codex:gpt-6.1-sol:high, claude:opus, pi:anthropic/claude-sonnet-5-5:medium).
#
# Config: $INDEPENDENT_PR_REVIEW_CONFIG, else ${XDG_CONFIG_HOME:-~/.config}/independent-pr-review/config.json.
# Without a config file, one built-in reviewer is used (codex, gpt-6.1-sol, medium effort).
#
# Output: <git common dir>/independent-pr-review/<branch>/<timestamp>/<reviewer>.{review.md,triage.md,log}
# With $INDEPENDENT_PR_REVIEW_OUTPUT_DIR set: $INDEPENDENT_PR_REVIEW_OUTPUT_DIR/<repo>/<branch>/<timestamp>/...
# After each run, only the newest keep_runs runs (config, default 10; 0 keeps all) of the branch are kept.
# Exit status: 0 if at least one reviewer finished, 1 if none did, 2 on usage or setup errors.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPTS_DIR="$SCRIPT_DIR/../prompts"
CONFIG="${INDEPENDENT_PR_REVIEW_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/independent-pr-review/config.json}"

BUILTIN_CONFIG='{
  "default": ["codex-sol"],
  "timeout_minutes": 30,
  "keep_runs": 10,
  "reviewers": {"codex-sol": {"harness": "codex", "model": "gpt-6.1-sol", "effort": "medium"}}
}'

die() { echo "error: $*" >&2; exit 2; }

command -v jq >/dev/null || die "jq is required (https://jqlang.org/download/)"
command -v git >/dev/null || die "git is required"

if [ -f "$CONFIG" ]; then
    config_json="$(jq -e . "$CONFIG")" || die "invalid JSON in $CONFIG"
    config_source="$CONFIG"
else
    config_json="$BUILTIN_CONFIG"
    config_source="built-in default (no $CONFIG)"
fi

cfg() { jq -r "$1" <<<"$config_json"; }

reviewers=""
pr=""
note=""
list=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --reviewers) reviewers="${2:-}"; shift 2 ;;
        --all)       reviewers="$(cfg '.reviewers | keys_unsorted | join(",")')"; shift ;;
        --pr)        pr="${2:-}"; shift 2 ;;
        --note)      note="${2:-}"; shift 2 ;;
        --list)      list=1; shift ;;
        -h|--help)   sed -n '2,/^$/{/^$/d;s/^# \{0,1\}//;p;}' "$0"; exit 0 ;;
        *)           die "unknown argument: $1 (see --help)" ;;
    esac
done

if [ "$list" -eq 1 ]; then
    echo "config: $config_source"
    echo "default: $(cfg '(.default // [(.reviewers | keys_unsorted)[0]]) | join(", ")')"
    cfg '.reviewers | to_entries[] | "  \(.key): \(.value.harness) \(.value.model // "(harness default model)") \(.value.effort // "(default effort)")"'
    exit 0
fi

[ -n "$reviewers" ] || reviewers="$(cfg '(.default // [(.reviewers | keys_unsorted)[0]]) | join(",")')"
[ -n "$reviewers" ] && [ "$reviewers" != "null" ] || die "no reviewers configured in $config_source"

timeout_minutes="$(cfg '.timeout_minutes // 30')"
timeout_cmd=()
if command -v timeout >/dev/null; then timeout_cmd=(timeout "${timeout_minutes}m")
elif command -v gtimeout >/dev/null; then timeout_cmd=(gtimeout "${timeout_minutes}m")
fi

keep_runs="$(cfg '.keep_runs // 10')"
[[ "$keep_runs" =~ ^[0-9]+$ ]] || die "keep_runs must be a whole number (got $keep_runs)"

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository"
branch="$(git rev-parse --abbrev-ref HEAD)"
common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
if [ -n "${INDEPENDENT_PR_REVIEW_OUTPUT_DIR:-}" ]; then
    # Shared location for every repo: add the repo name (the main worktree's directory).
    branch_dir="$INDEPENDENT_PR_REVIEW_OUTPUT_DIR/$(basename "$(dirname "$common_dir")")/${branch//\//_}"
else
    branch_dir="$common_dir/independent-pr-review/${branch//\//_}"
fi
out_dir="$branch_dir/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out_dir" || die "cannot create $out_dir"

review_prompt="$(cat "$PROMPTS_DIR/review.md")"
[ -n "$pr" ] && review_prompt+=$'\n\n'"Target PR: $pr (use this instead of looking up the PR for the current branch)."
[ -n "$note" ] && review_prompt+=$'\n\n'"Additional instructions from the user: $note"
triage_prompt="$(cat "$PROMPTS_DIR/triage.md")"

new_uuid() {
    if command -v uuidgen >/dev/null; then uuidgen | tr 'A-Z' 'a-z'
    elif [ -r /proc/sys/kernel/random/uuid ]; then cat /proc/sys/kernel/random/uuid
    else python3 -c 'import uuid; print(uuid.uuid4())'
    fi
}

# Claude Code marks its child processes as nested sessions; a reviewer launched from
# inside Claude Code must not inherit those markers. Auth/config vars are kept.
clean_env=(env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SESSION_ID
    -u CLAUDE_CODE_CHILD_SESSION -u CLAUDE_CODE_SESSION_ATTENDED -u CLAUDE_CODE_EXECPATH
    -u CLAUDE_CODE_MESSAGING_SOCKET -u CLAUDE_CODE_MESSAGING_TOKEN -u CLAUDE_PID
    -u CLAUDE_EFFORT -u CLAUDE_AGENT_SDK_VERSION)

run() { "${clean_env[@]}" ${timeout_cmd[@]+"${timeout_cmd[@]}"} "$@" </dev/null; }

# Runs both turns for one reviewer. Writes <name>.review.md, <name>.triage.md,
# <name>.log and <name>.status ("ok <resume command>" or "failed <reason>").
review_one() {
    local name="$1" harness="$2" model="$3" effort="$4"
    local base="$out_dir/$name" log="$out_dir/$name.log" sid flags=()

    fail() { echo "failed $*" > "$base.status"; }
    command -v "$harness" >/dev/null || { fail "$harness CLI not found on PATH"; return; }

    case "$harness" in
        codex)
            # Full access: no approvals, no sandbox (gh needs network).
            flags=(--dangerously-bypass-approvals-and-sandbox --json)
            [ -n "$model" ] && flags+=(-m "$model")
            [ -n "$effort" ] && flags+=(-c "model_reasoning_effort=\"$effort\"")
            run codex exec "${flags[@]}" -o "$base.review.md" "$review_prompt" > "$log.jsonl" 2>> "$log" \
                || { fail "review turn exited $? (see $log)"; return; }
            sid="$(jq -r 'select(.type == "thread.started") | .thread_id' "$log.jsonl" | head -n1)"
            [ -n "$sid" ] || { fail "no codex thread id in $log.jsonl"; return; }
            run codex exec resume "${flags[@]}" -o "$base.triage.md" "$sid" "$triage_prompt" >> "$log.jsonl" 2>> "$log" \
                || { fail "triage turn exited $? (see $log)"; return; }
            echo "ok codex resume $sid" > "$base.status"
            ;;
        claude)
            sid="$(new_uuid)"
            flags=(-p --dangerously-skip-permissions --output-format json)
            [ -n "$model" ] && flags+=(--model "$model")
            [ -n "$effort" ] && flags+=(--effort "$effort")
            run claude "${flags[@]}" --session-id "$sid" "$review_prompt" > "$base.review.json" 2>> "$log" \
                || { fail "review turn exited $? (see $log)"; return; }
            jq -e '.is_error != true' "$base.review.json" >/dev/null || { fail "review turn errored (see $base.review.json)"; return; }
            jq -r '.result // empty' "$base.review.json" > "$base.review.md"
            run claude "${flags[@]}" --resume "$sid" "$triage_prompt" > "$base.triage.json" 2>> "$log" \
                || { fail "triage turn exited $? (see $log)"; return; }
            jq -e '.is_error != true' "$base.triage.json" >/dev/null || { fail "triage turn errored (see $base.triage.json)"; return; }
            jq -r '.result // empty' "$base.triage.json" > "$base.triage.md"
            echo "ok claude --resume $sid" > "$base.status"
            ;;
        pi)
            # pi has no permission prompts; it runs tools directly.
            sid="independent-pr-review-$(new_uuid)"
            flags=(-p --session-id "$sid")
            [ -n "$model" ] && flags+=(--model "$model")
            [ -n "$effort" ] && flags+=(--thinking "$effort")
            run pi "${flags[@]}" "$review_prompt" > "$base.review.md" 2>> "$log" \
                || { fail "review turn exited $? (see $log)"; return; }
            run pi "${flags[@]}" "$triage_prompt" > "$base.triage.md" 2>> "$log" \
                || { fail "triage turn exited $? (see $log)"; return; }
            echo "ok pi --session-id $sid" > "$base.status"
            ;;
        *)
            fail "unsupported harness '$harness' (use codex, claude or pi)"
            return
            ;;
    esac
    [ -s "$base.triage.md" ] || fail "empty triage reply (see $log)"
}

names=()
IFS=',' read -r -a requested <<<"$reviewers"
for spec in "${requested[@]}"; do
    spec="$(echo "$spec" | tr -d '[:space:]')"
    [ -n "$spec" ] || continue
    if [[ "$spec" == *:* ]]; then
        IFS=':' read -r harness model effort <<<"$spec"
        name="${spec//[^A-Za-z0-9._-]/_}"
    else
        entry="$(jq -c --arg n "$spec" '.reviewers[$n] // empty' <<<"$config_json")"
        [ -n "$entry" ] || die "unknown reviewer '$spec' (configured: $(cfg '.reviewers | keys_unsorted | join(", ")'))"
        harness="$(jq -r '.harness // empty' <<<"$entry")"
        model="$(jq -r '.model // empty' <<<"$entry")"
        effort="$(jq -r '.effort // empty' <<<"$entry")"
        name="$spec"
    fi
    names+=("$name")
    echo "started $name: $harness ${model:-(default model)} ${effort:-(default effort)}"
    review_one "$name" "$harness" "$model" "$effort" &
done
[ "${#names[@]}" -gt 0 ] || die "no reviewers selected"

echo "output: $out_dir"
echo "waiting (up to ${timeout_minutes}m per turn)..."
wait

# Keep the newest keep_runs run directories for this branch. Timestamped names sort by age.
if [ "$keep_runs" -gt 0 ]; then
    runs=()
    while IFS= read -r run_dir; do runs+=("$run_dir"); done \
        < <(find "$branch_dir" -mindepth 1 -maxdepth 1 -type d -name '[0-9]*-[0-9]*' | sort -r)
    if [ "${#runs[@]}" -gt "$keep_runs" ]; then
        for run_dir in "${runs[@]:$keep_runs}"; do rm -rf -- "$run_dir"; done
    fi
fi

ok=0
echo
for name in "${names[@]}"; do
    status="$(cat "$out_dir/$name.status" 2>/dev/null || echo "failed no status written")"
    if [[ "$status" == ok* ]]; then
        ok=$((ok + 1))
        echo "$name: ok"
        echo "  triage: $out_dir/$name.triage.md"
        echo "  review: $out_dir/$name.review.md"
        echo "  resume: ${status#ok }"
    else
        echo "$name: ${status}"
    fi
done
[ "$ok" -gt 0 ] || exit 1
