# Installation and pinning

## What the skill needs

| Tool | Needed for | Check |
|---|---|---|
| Go >= 1.25 | building the pinned svgcast and Betterleaks from source (svgcast alone needs 1.23; Betterleaks sets the floor) | `go version` |
| python3 (POSIX `pty`: Linux/macOS) | PTY recorder, secret scanner, preview | `python3 --version` |
| bash | recorded shell, `capture.sh` | `bash --version` |
| headless Chromium/Chrome (optional) | `preview.py` rasterizing SVGs for inspection | `command -v chromium google-chrome` |
| asciinema (optional) | recording instead of the bundled PTY recorder | `asciinema --version` |
| vhs, ttyd, ffmpeg (fallback only) | PNG/GIF/MP4/WebM | see [vhs.md](vhs.md) |

If a required tool is missing, report it and stop. Do not install system packages yourself; suggest the install command to the user instead (Go: <https://go.dev/doc/install>). Builds use `GOTOOLCHAIN=local`, so Go never downloads a different toolchain behind your back.

## svgcast: pinned, built from source

`scripts/install_svgcast.sh` runs `go install github.com/co2water/svgcast/cmd/svgcast@v0.2.0` with `GOBIN` set to `${SVGCAST_BIN_DIR:-${XDG_CACHE_HOME:-~/.cache}/terminal-capture/bin}`, then checks that the binary was built from the exact reviewed module (`go version -m` must show the pinned `h1:` hash recorded in the script). It prints the binary path, and is a no-op when a verified binary already exists. `capture.sh` calls it automatically.

Why a source build and not `npx`, Homebrew, or release tarballs:

- svgcast is a young, single-maintainer project. The `go install` path is checked against the Go checksum database and our pinned module hash, and the source is small enough to read.
- The npm `postinstall` and the project's GitHub Action download a prebuilt binary over HTTPS **without verifying its checksum**.
- Review of v0.2.0 found no network or process-execution code (standard library plus three small pinned dependencies), escaped output, and no `<script>` unless `--controls` is passed.

**Upgrading:** read the upstream diff between the pinned tag and the new one (look for new imports, network or exec calls, new output elements), then change `SVGCAST_VERSION` and `SVGCAST_MODULE_HASH` in `scripts/install_svgcast.sh` together and update the version mentioned in this file and in `SKILL.md`. The hash is shown by `go version -m <binary>` on the `mod` line after a build. A test checks that the version pin and the docs agree.

## Betterleaks: the second secret-scanning engine

`scripts/install_betterleaks.sh` builds `github.com/betterleaks/betterleaks@v1.9.0` the same way (module proxy, checksum database, pinned `h1:` hash, user-local install directory, no-op when already verified). `capture.sh` runs it automatically and passes the binary to `scan_secrets.py --betterleaks`.

Why Betterleaks, and why this version:

- Hundreds of maintained provider key formats, which the hand-written built-in rules do not cover. It is MIT-licensed, runs fully offline by default, and has actively maintained rules (frequent releases at the time of writing). gitleaks (same lineage) has not had a release in months and its README points users to Betterleaks. TruffleHog was rejected: AGPL-3.0, and it verifies credentials against provider APIs by default.
- v1.9.0 is the stable release. v2 was a release candidate when this was written and changed the CLI and report format; move to it once stable and re-check the flags (it no longer auto-loads config from the scan target, which is better).

How the skill invokes it (`betterleaks_command` in `scan_secrets.py`, covered by tests). Each choice closes a specific gap in using a scanner as a gate over **untrusted terminal output**:

| Choice | Reason |
|---|---|
| `stdin` on text we extract (rendered screen lines for SVG, ANSI-stripped output for `.cast`) | none of these tools understand `.cast` or SVG; no files or git are touched |
| empty temp working directory, near-empty environment | v1 loads `.betterleaks.toml`, `.gitleaks.toml`, `.gitleaksignore` from the working directory and `BETTERLEAKS_CONFIG*` / `GITLEAKS_CONFIG*` from the environment; a config can replace the rules and hide findings (verified) |
| `--ignore-gitleaks-allow` | otherwise a `betterleaks:allow` or `gitleaks:allow` comment in the scanned text silences a finding (verified) |
| `--redact` | the secret never reaches reports or our output |
| `--regex-engine stdlib` | avoids running the default engine's bundled prebuilt WebAssembly blob; detections were identical |
| no `--validation` | validation sends found credentials to provider APIs; never enabled |
| nonzero exit, bad JSON, or missing binary is an error | the scan fails closed |

Source review of v1.9.0 (about 42k lines of Go; reviewed by risk, not line by line): no telemetry or update checks. Network code exists only for the opt-in validation feature and the explicit remote-source subcommands (GitHub, GitLab, S3, Hugging Face). A probe during normal scans saw no outbound connections (with `--validation` it did). `os/exec` is used only by the git sources. The tokenizer data is embedded, not downloaded. About 50 Go module dependencies, all checked against the checksum database. Not verified: the prebuilt WebAssembly regex blob in its `go-re2` dependency (a build recipe is published), which is why the stdlib engine is selected.

**Upgrading:** review the upstream diff, then change `BETTERLEAKS_VERSION` and `BETTERLEAKS_MODULE_HASH` together, update the version mentioned in this file and `SKILL.md`, and re-run the tests with `BETTERLEAKS_BIN=<new binary>` so the allow-comment and config-injection tests exercise the new build.

## asciinema (optional)

The bundled `scripts/pty_record.py` is the default recorder: it is scripted, deterministic, and scrubs the environment. Use asciinema only when a human needs to drive a live session. Install per the [asciinema README](https://github.com/asciinema/asciinema); do not install it automatically.

svgcast only reads **asciicast v2**, but asciinema 3.x writes v3 by default. Record with `asciinema rec --output-format asciicast-v2 demo.cast` (confirm with `asciinema rec --help`), or convert an existing file with `asciinema convert`. Check that the first line of the file contains `"version": 2`. Recordings made this way bypass the recorder's environment scrub, so run `scripts/scan_secrets.py --betterleaks <binary>` on the `.cast` before rendering it, then render with `svgcast demo.cast -o demo.svg --still demo-still.svg`.
