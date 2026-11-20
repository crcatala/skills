#!/usr/bin/env bash
# Run one or more independent PR reviewers (codex, claude, pi, antigravity) without a UI, in parallel.
# Each reviewer gets two turns in one session: the review prompt, then the triage prompt.
# The triage reply is written to a file the calling agent reads.
#
# Usage:
#   run-review.sh [--reviewers a,b | --all] [--pr <number|url>] [--note <text>]
#   run-review.sh --list
#
# A reviewer is a name from the config, or an ad-hoc spec harness:model[:effort]
# (e.g. codex:gpt-6.2-sol:high, claude:opus, pi:anthropic/claude-sonnet-5-5:medium,
# antigravity:gemini-4-neon:high).
#
# The antigravity harness runs Google's Antigravity CLI: $ANTIGRAVITY_CLI if set, else agy or
# antigravity on PATH, else the copy T3 Code installs under <T3 home>/tools/antigravity-acp
# (T3 home: $T3CODE_HOME, ~/.t3 or ${XDG_DATA_HOME:-~/.local/share}/t3).
#
# Config: $INDEPENDENT_PR_REVIEW_CONFIG, else ${XDG_CONFIG_HOME:-~/.config}/independent-pr-review/config.json.
# Without a config file, the built-in presets are used: codex-sol (default; codex, gpt-6.2-sol, medium),
# codex-astra (codex, gpt-6.2-astra, medium), claude-fable (claude, claude-fable-5-2, medium) and
# antigravity-neon (antigravity, gemini-4-neon, medium).
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
  "reviewers": {
    "codex-sol": {"harness": "codex", "model": "gpt-6.2-sol", "effort": "medium"},
    "codex-astra": {"harness": "codex", "model": "gpt-6.2-astra", "effort": "medium"},
    "claude-fable": {"harness": "claude", "model": "claude-fable-5-2", "effort": "medium"},
    "antigravity-neon": {"harness": "antigravity", "model": "gemini-4-neon", "effort": "medium"}
  }
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

# T3 Code's home directories to look in: $T3CODE_HOME, ~/.t3 (its default), ${XDG_DATA_HOME:-~/.local/share}/t3.
t3_homes() { printf '%s\n' "${T3CODE_HOME:-}" "$HOME/.t3" "${XDG_DATA_HOME:-$HOME/.local/share}/t3" | grep .; }

# Prints the path of the Antigravity CLI. Order: $ANTIGRAVITY_CLI; agy or antigravity on PATH
# (antigravity only when it is the CLI, not the Antigravity IDE's launcher); the release T3 Code
# marks active in <T3 home>/tools/antigravity-acp/<platform>-<arch>/active.json.
find_antigravity() {
    local cand t3_home os arch exe release
    if [ -n "${ANTIGRAVITY_CLI:-}" ]; then
        [ -x "$ANTIGRAVITY_CLI" ] && echo "$ANTIGRAVITY_CLI"
        return
    fi
    for cand in agy antigravity; do
        cand="$(command -v "$cand")" || continue
        "$cand" --help 2>&1 | grep -q -- '--print' && { echo "$cand"; return; }
    done
    case "$(uname -s)" in
        Linux) os=linux ;; Darwin) os=darwin ;; MINGW*|MSYS*|CYGWIN*) os=win32 ;; *) return ;;
    esac
    case "$(uname -m)" in
        x86_64|amd64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; *) return ;;
    esac
    exe=antigravity; [ "$os" = win32 ] && exe=agy.exe
    while IFS= read -r t3_home; do
        cand="$t3_home/tools/antigravity-acp/$os-$arch"
        release="$(jq -r '.releaseId // empty' "$cand/active.json" 2>/dev/null)" || continue
        [ -n "$release" ] && [ -x "$cand/versions/$release/$exe" ] && { echo "$cand/versions/$release/$exe"; return; }
    done < <(t3_homes)
}

# True when T3 Code holds its own Antigravity sign-in. T3 keeps it in its private profile,
# which the CLI's print mode cannot read, so it does not sign the CLI in.
t3_antigravity_signed_in() {
    local t3_home token
    while IFS= read -r t3_home; do
        for token in "$t3_home"/userdata/providers/antigravity/*/antigravity-acp/{antigravity-oauth-token,acp_token.json}; do
            [ -s "$token" ] && return 0
        done
    done < <(t3_homes)
    return 1
}

# Checks the Antigravity CLI at $1 (empty: not found) can run reviews. Prints nothing when it can,
# else one line telling the user what to do, and returns 1. `models` answers at once when signed out.
antigravity_setup_problem() {
    local cli="$1" t=() run_cmd out
    if [ -z "$cli" ]; then
        echo "Antigravity CLI not found. Set up Antigravity in T3 Code, or install Google's standalone agy CLI, or set ANTIGRAVITY_CLI to the CLI's path."
        return 1
    fi
    command -v timeout >/dev/null && t=(timeout 60)
    out="$(AGY_CLI_DISABLE_AUTO_UPDATE=1 ${t[@]+"${t[@]}"} "$cli" models </dev/null 2>&1)"
    [[ "$out" == *"Please sign in"* ]] || return 0
    run_cmd="$(printf '%q' "$cli")"
    if t3_antigravity_signed_in; then
        echo "Antigravity CLI is not signed in. Being signed in to Antigravity in T3 Code does not count: T3 keeps that sign-in to itself, so the CLI needs its own, once per machine. Run $run_cmd in a terminal, open the Google link it shows, sign in, and paste the code back if asked."
    else
        echo "Antigravity CLI is not signed in. Sign it in once per machine: run $run_cmd in a terminal, open the Google link it shows, sign in, and paste the code back if asked."
    fi
    return 1
}

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
    if [ "$(cfg '[.reviewers[] | select(.harness == "antigravity")] | length')" -gt 0 ]; then
        agy_cli="$(find_antigravity)"
        echo "antigravity CLI: ${agy_cli:-not found}"
        if agy_problem="$(antigravity_setup_problem "$agy_cli")"; then echo "  ready"; else echo "  $agy_problem"; fi
    fi
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
    local base="$out_dir/$name" log="$out_dir/$name.log" sid flags=() cli problem

    fail() { echo "failed $*" > "$base.status"; }
    if [ "$harness" = antigravity ]; then
        cli="$(find_antigravity)"
        problem="$(antigravity_setup_problem "$cli")" || { fail "setup needed: $problem"; return; }
    else
        command -v "$harness" >/dev/null || { fail "$harness CLI not found on PATH"; return; }
    fi

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
        antigravity)
            # Full access: auto-approve every tool call (gh needs network). No self-update mid-run.
            # --print takes the prompt as its value, so it is attached with '='.
            flags=(--dangerously-skip-permissions --output-format json)
            [ -n "$model" ] && flags+=(--model "$model")
            [ -n "$effort" ] && flags+=(--effort "$effort")
            agy_turn() { # <turn> <output base> <prompt> [args...]: one print-mode turn; writes <base>.json and <base>.md
                local turn="$1" out="$2" prompt="$3"; shift 3
                run env AGY_CLI_DISABLE_AUTO_UPDATE=1 "$cli" "${flags[@]}" "$@" --print="$prompt" > "$out.json" 2>> "$log"
                local code=$?
                # Not signed in: the CLI prints a sign-in link, waits 60s for a code, then fails.
                if grep -q '^Authentication required' "$out.json" "$log" 2>/dev/null; then
                    fail "setup needed: Antigravity CLI is not signed in. Run $(printf '%q' "$cli") in a terminal and sign in."
                    return 1
                fi
                if [ "$code" -ne 0 ] || ! jq -e '.status == "SUCCESS"' "$out.json" >/dev/null 2>&1; then
                    fail "$turn turn failed (exit $code): $(jq -r '.error // empty' "$out.json" 2>/dev/null | head -n1) (see $out.json)"
                    return 1
                fi
                jq -r '.response // empty' "$out.json" > "$out.md"
            }
            agy_turn review "$base.review" "$review_prompt" || return
            sid="$(jq -r '.conversation_id // empty' "$base.review.json")"
            [ -n "$sid" ] || { fail "no antigravity conversation id in $base.review.json"; return; }
            agy_turn triage "$base.triage" "$triage_prompt" --conversation "$sid" || return
            echo "ok $(printf '%q' "$cli") --conversation $sid" > "$base.status"
            ;;
        *)
            fail "unsupported harness '$harness' (use codex, claude, pi or antigravity)"
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
