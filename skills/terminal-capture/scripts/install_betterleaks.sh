#!/usr/bin/env bash
# Build the pinned Betterleaks release from source into a user-local directory.
# Betterleaks is the second secret-scanning engine used by scan_secrets.py.
#
# Like install_svgcast.sh: the source comes through the Go module proxy, is
# checked against the Go checksum database, and must match the module hash
# below (the exact source that was reviewed). Prebuilt binaries are not used.
#
# Usage: install_betterleaks.sh        prints the path of the betterleaks binary on success
# Env:   BETTERLEAKS_BIN_DIR   install directory (default: ${XDG_CACHE_HOME:-~/.cache}/terminal-capture/bin)
#
# To upgrade: review the upstream diff (new network or exec code, new default
# behavior), then change BOTH values below together and re-check the flags in
# scan_secrets.py (the CLI changed between v1 and v2).
set -euo pipefail

BETTERLEAKS_VERSION="v1.9.0"
BETTERLEAKS_MODULE_HASH="h1:mYAZBNUGBww1ihIwcb68Z2QmLh5hZwKbLG0jsf4PfpE="
MODULE="github.com/betterleaks/betterleaks"

BIN_DIR="${BETTERLEAKS_BIN_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/terminal-capture/bin}"
BIN="$BIN_DIR/betterleaks"

verify() {  # binary exists, is the pinned version, and was built from the pinned source
    [ -x "$BIN" ] || return 1
    local info
    info="$(go version -m "$BIN" 2>/dev/null)" || return 1
    grep -q "mod[[:space:]]*${MODULE}[[:space:]]*${BETTERLEAKS_VERSION}[[:space:]]*${BETTERLEAKS_MODULE_HASH}" <<<"$info"
}

if ! command -v go >/dev/null 2>&1; then
    echo "betterleaks: Go (>= 1.25) is required to build betterleaks from source; install Go and retry." >&2
    echo "  https://go.dev/doc/install  (not installed automatically)" >&2
    exit 1
fi

if verify; then
    echo "$BIN"
    exit 0
fi

mkdir -p "$BIN_DIR"
echo "betterleaks: building $MODULE@$BETTERLEAKS_VERSION from source into $BIN_DIR (first run takes a minute)" >&2
# GOTOOLCHAIN=local: never download a different Go toolchain implicitly.
if ! GOTOOLCHAIN=local GOBIN="$BIN_DIR" go install "$MODULE@$BETTERLEAKS_VERSION" >&2; then
    echo "betterleaks: build failed. It needs Go >= 1.25 (this machine has $(go env GOVERSION))." >&2
    exit 1
fi

if ! verify; then
    rm -f "$BIN"
    echo "betterleaks: built binary does not match the pinned module hash; removed it." >&2
    echo "  expected $MODULE $BETTERLEAKS_VERSION $BETTERLEAKS_MODULE_HASH" >&2
    exit 1
fi
echo "$BIN"
