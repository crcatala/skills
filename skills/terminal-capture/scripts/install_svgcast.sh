#!/usr/bin/env bash
# Build the pinned svgcast release from source into a user-local directory.
#
# Source builds go through the Go module proxy and are checked against the Go
# checksum database; the module hash below additionally pins the exact source we
# reviewed. Prebuilt binaries (npm postinstall, brew, release tarballs) are not
# used: the npm installer downloads without verifying checksums.
#
# Usage: install_svgcast.sh            prints the path of the svgcast binary on success
# Env:   SVGCAST_BIN_DIR   install directory (default: ${XDG_CACHE_HOME:-~/.cache}/terminal-capture/bin)
#
# To upgrade: review the upstream diff, then change BOTH values below together.
set -euo pipefail

SVGCAST_VERSION="v0.2.0"
SVGCAST_MODULE_HASH="h1:AKPLq/hDK6U29esPlQbSzm3IPm+mvn7qf9TlXtBf5F0="
MODULE="github.com/co2water/svgcast"

BIN_DIR="${SVGCAST_BIN_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/terminal-capture/bin}"
BIN="$BIN_DIR/svgcast"

verify() {  # binary exists, is the pinned version, and was built from the pinned source
    [ -x "$BIN" ] || return 1
    local info
    info="$(go version -m "$BIN" 2>/dev/null)" || return 1
    grep -q "mod[[:space:]]*${MODULE}[[:space:]]*${SVGCAST_VERSION}[[:space:]]*${SVGCAST_MODULE_HASH}" <<<"$info"
}

if ! command -v go >/dev/null 2>&1; then
    echo "svgcast: Go (>= 1.23) is required to build svgcast from source; install Go and retry." >&2
    echo "  https://go.dev/doc/install  (not installed automatically)" >&2
    exit 1
fi

if verify; then
    echo "$BIN"
    exit 0
fi

mkdir -p "$BIN_DIR"
echo "svgcast: building $MODULE@$SVGCAST_VERSION from source into $BIN_DIR" >&2
# GOTOOLCHAIN=local: never download a different Go toolchain implicitly.
if ! GOTOOLCHAIN=local GOBIN="$BIN_DIR" go install "$MODULE/cmd/svgcast@$SVGCAST_VERSION" >&2; then
    echo "svgcast: build failed. It needs Go >= 1.23 (this machine has $(go env GOVERSION))." >&2
    exit 1
fi

if ! verify; then
    rm -f "$BIN"
    echo "svgcast: built binary does not match the pinned module hash; removed it." >&2
    echo "  expected $MODULE $SVGCAST_VERSION $SVGCAST_MODULE_HASH" >&2
    exit 1
fi
echo "$BIN"
