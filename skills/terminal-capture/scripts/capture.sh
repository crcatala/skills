#!/usr/bin/env bash
# Record a scripted terminal session and render it as animated + still SVG,
# scanning for secrets before and after (built-in rules plus the pinned
# Betterleaks engine), and aborting (deleting its own artifacts) if anything
# credential-shaped shows up.
#
# Usage:
#   capture.sh [options] NAME SCENARIO.json
#
# Options:
#   --out-dir DIR          output directory (default: a fresh mktemp dir)
#   --cols N --rows N      terminal size (default 100x30)
#   --cwd DIR              working directory for the recorded shell
#   --theme auto|light|dark  svgcast theme (default auto: follows the viewer)
#   --env NAME=VALUE       set a variable in the recorded shell (repeatable)
#   --pass-env NAME        copy a host variable into the shell (never a credential)
#   --keep-home            use the real $HOME inside the recorded shell
#   --svgcast-args "..."   extra svgcast flags, e.g. "--idle-time-limit 2s --speed 1.5"
#
# Outputs (in the output directory): NAME.cast, NAME.svg (animated), NAME-still.svg
# (static, the final frame). Exit: 0 ok, 10 blocked by the secret scan, 11 the scan
# could not complete (artifacts deleted), other = tool failure.
#
# An artifact is deleted unless it has passed a scan: the recording until the scan of
# the recording passes, the SVGs until the scan of the SVGs passes. This also applies
# when the script is interrupted or crashes.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out_dir="" cols=100 rows=30 cwd="$PWD" theme=auto extra=""
rec_args=()

die() { echo "capture: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --out-dir) out_dir="$2"; shift 2 ;;
        --cols) cols="$2"; shift 2 ;;
        --rows) rows="$2"; shift 2 ;;
        --cwd) cwd="$2"; shift 2 ;;
        --theme) theme="$2"; shift 2 ;;
        --env) rec_args+=(--env "$2"); shift 2 ;;
        --pass-env) rec_args+=(--pass-env "$2"); shift 2 ;;
        --keep-home) rec_args+=(--keep-home); shift ;;
        --svgcast-args) extra="$2"; shift 2 ;;
        -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        --) shift; break ;;
        -*) die "unknown option $1" ;;
        *) break ;;
    esac
done
[ $# -eq 2 ] || die "usage: capture.sh [options] NAME SCENARIO.json"
name="$1" scenario="$2"
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || die "NAME may only contain letters, digits, '.', '_' and '-'"
[ -f "$scenario" ] || die "scenario file not found: $scenario"

[ -n "$out_dir" ] || out_dir="$(mktemp -d "${TMPDIR:-/tmp}/terminal-capture-XXXXXX")"
mkdir -p "$out_dir"
cast="$out_dir/$name.cast" svg="$out_dir/$name.svg" still="$out_dir/$name-still.svg"
for f in "$cast" "$svg" "$still"; do [ ! -e "$f" ] || die "refusing to overwrite $f"; done

cast_ok=0 svg_ok=0
cleanup() {  # runs on every exit: never leave an unscanned artifact behind
    [ "$cast_ok" = 1 ] || rm -f "$cast"
    [ "$svg_ok" = 1 ] || rm -f "$svg" "$still"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

blocked() {  # scan results already printed; the exit trap removes this run's artifacts
    echo "capture: BLOCKED ($1). Generated artifacts were deleted. Stop and tell the user before continuing." >&2
    exit 10
}
failed() {
    echo "capture: the secret scan could not complete ($1), so it did not pass. Generated artifacts were deleted." >&2
    echo "  Fix the scanner problem and re-run; do not skip the scan." >&2
    exit 11
}
check_scan() {  # check_scan STAGE FILE... : exit 10 on a finding, 11 if the scan was incomplete
    local stage="$1" rc=0
    shift
    scan "$@" || rc=$?
    case "$rc" in
        0) ;;
        1) blocked "$stage" ;;
        *) failed "$stage" ;;
    esac
}

# 0. Build the pinned tools first so a missing requirement fails before anything is recorded.
svgcast="$("$HERE/install_svgcast.sh")"
betterleaks="$("$HERE/install_betterleaks.sh")"
scan() { python3 "$HERE/scan_secrets.py" --betterleaks "$betterleaks" "$@"; }

# 1. Preflight: the scenario file itself must not contain secrets.
check_scan "scenario file" "$scenario"

# 2. Record in a scrubbed environment.
python3 "$HERE/pty_record.py" --out "$cast" --scenario "$scenario" --cols "$cols" --rows "$rows" \
    --cwd "$cwd" ${rec_args[@]+"${rec_args[@]}"}

# 3. Scan the raw recording (typed input and all output) before rendering anything.
check_scan "recording" "$cast"
cast_ok=1

# 4. Render animated + still. Word-splitting of $extra is intentional.
# shellcheck disable=SC2086
"$svgcast" "$cast" -o "$svg" --still "$still" --theme "$theme" $extra

# 5. Scan what was actually rendered.
check_scan "rendered SVG" "$svg" "$still"
svg_ok=1

echo
echo "capture: done (scan clean of blocking findings; still inspect the result by eye)"
ls -l "$cast" "$svg" "$still"
