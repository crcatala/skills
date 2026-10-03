---
name: terminal-capture
description: Capture real terminal output from CLI tools and TUIs as animated and static SVG (default, via svgcast and a scripted PTY recorder), or as PNG/GIF/MP4/WebM via Charmbracelet VHS when explicitly requested. Scans for secrets before and after, and stops if anything sensitive appears. Use for terminal, command-line, or TUI screenshots, recordings, demos, or visual proof. Not for browser or desktop-app screenshots, and not for uploading or posting artifacts.
compatibility: "Needs Go >= 1.25 (builds the pinned svgcast and Betterleaks from source) and python3 with POSIX pty (Linux/macOS), plus bash. Optional: asciinema, a headless Chromium/Chrome for previews. VHS fallback (PNG/GIF/video) needs vhs >= 0.12.0, ttyd, ffmpeg."
---

# Terminal Capture

Record a CLI or TUI in a controlled pseudo-terminal and save its rendered output as **SVG**: one animated file and one static still. This skill owns **capture only**: produce and verify local artifacts, then report their paths. Do not upload, post, or commit them unless separately asked.

**The deliverable is SVG.** `NAME.svg` and `NAME-still.svg` are what you hand off, unchanged. Any PNG you make along the way (`preview.py` writes one) is a throwaway for looking at the result: never hand it off as the result, and never upload or attach it. Change the deliverable format only when the user explicitly asks for PNG, GIF, MP4 or WebM. If you think another format would suit the destination better, ask first; never switch silently.

`{baseDir}` below means the directory containing this `SKILL.md`.

## Safety gate (read first, applies to every capture)

A terminal capture can publish whatever the terminal shows: API keys, tokens, private keys, `.env` contents, internal hostnames, customer data, usernames and paths. Treat every capture as something that may be shared.

1. **Before recording,** decide exactly what will appear on screen: the command, its arguments, environment, config and data files, URLs, and any network targets. Use safe dummy or mock values and fixtures. Never `cat .env`, run `env`/`printenv`, or run commands against production or personal data just to have something to show.
2. **After recording,** scan the result with `scripts/scan_secrets.py`, which runs built-in rules plus the pinned Betterleaks engine (`capture.sh` does this for you), **and** look at the capture yourself.
3. **If there is significant risk, stop and abort.** That means: a BLOCK finding from the scanner; a real credential in the command, environment, fixtures or output; the demo needing real credentials or touching sensitive data with no safe substitute; or any output you cannot confidently classify as non-sensitive. Do not render or keep going. Delete artifacts that contain the sensitive content, do not repeat the secret in your message (give its type and location only), and **tell the user and wait** before proceeding.

Full checklist, the stop-and-notify message, and what the scanner can't catch: [references/safety.md](references/safety.md).

## Choose the format

- **Default: svgcast SVG.** Always produce both, unless told otherwise: `NAME.svg` (animated) and `NAME-still.svg` (static, the final frame).
- **Which one to embed.** Use `NAME.svg` when motion is the point: an interaction, a multi-step flow, a dialog opening, output streaming in. Use `NAME-still.svg` for a static view: a final state, a help screen, a table, a list. When unsure, embed the still, or both with a one-line caption each. Dense, constantly redrawing TUIs make large animated files, so prefer the still there.
- **VHS fallback.** Only when the user explicitly asks for PNG, GIF, MP4 or WebM: follow [references/vhs.md](references/vhs.md) instead. The safety gate still applies. If you suspect the destination cannot show SVG (for example chat or email), do not switch on that suspicion: keep the SVG, say SVG may not animate there, and ask whether they want PNG/GIF. Say plainly that this is a guess, not something you checked.
- **If a format fails** (render, preview, or a later upload), report the exact error and ask how to proceed. Do not convert to another format on your own.
- Do not add extras (more states, window chrome, `--controls`) unless asked. `--controls` embeds a `<script>`; the default output has none.

## Requirements

- Check: `command -v go python3 bash`, and `go version` is 1.25 or newer.
- svgcast (**v0.2.0**) and the Betterleaks secret scanner (**v1.9.0**) are built from source at those pinned, hash-checked versions into a user-local directory by `scripts/install_svgcast.sh` and `scripts/install_betterleaks.sh` (both run automatically by `capture.sh`, before anything is recorded). The skill never installs system packages. Details and upgrade policy: [references/install.md](references/install.md).
- If Go or Python is missing, report it and stop. Do not install them yourself.

## Workflow

1. **Understand the target.** Identify the command and the state that proves the behavior. Prepare fixtures or mock data and a safe working directory. Run the Safety gate step 1.
2. **Write a scenario** (a JSON list of steps) in a scratch location, not in the source tree:

   ```json
   [
     ["run", "my-cli --help"],
     ["wait", "Usage:", 10],
     ["sleep", 1.5]
   ]
   ```

   Steps: `type`, `run` (type then Enter), `key` (`Enter`, `Down`, `Esc`, `Ctrl+C`, or a literal like `j`; each is sent as one write, so arrow keys reach the app as a single escape sequence), `sleep`, `wait` (regex, timeout seconds). Prefer `wait` on stable visible text over fixed sleeps. A failed `wait` fails the recording. Format and TUI examples: [references/pty-recorder.md](references/pty-recorder.md).
3. **End on the state you want to show.** The still is the **last frame**. For a TUI, finish while the target screen is visible; do not quit it (the recorder stops the process itself).
4. **Run the pipeline.** One command records, scans, renders, and scans again:

   ```bash
   {baseDir}/scripts/capture.sh --cols 100 --rows 30 NAME scenario.json
   ```

   Useful options: `--out-dir DIR`, `--theme auto|light|dark`, `--cwd DIR`, `--env NAME=VALUE`, `--svgcast-args "--idle-time-limit 2s --speed 1.5"`. By default the output directory is a fresh `mktemp -d` under `$TMPDIR` or `/tmp`; use another location only if the user asks. Never overwrite existing artifacts without checking. `capture.sh` refuses to overwrite: to re-record a fixed scenario, use a fresh `--out-dir` (or omit it) or delete that run's old `NAME.cast`, `NAME.svg` and `NAME-still.svg` first.
5. **Handle the exit code.** `10` means the scan blocked the capture and already deleted this run's artifacts: stop and notify the user (Safety gate step 3). `11` means the scan could not complete (for example the second engine failed): it did not pass, and the unscanned artifacts were deleted, so fix the scanner problem and re-run; never skip the scan. Other non-zero codes are tool failures: read the message, fix the scenario, and retry. Printed WARN lines (emails, IPs, home paths, high-entropy strings) do not stop the run: review each and report them in the handoff. If the artifact will be shared or committed, resolve them first.
6. **Inspect the result yourself.** Rasterize it: `python3 {baseDir}/scripts/preview.py NAME-still.svg --out shot.png` (and `--at SECONDS` on the animated file to check a moment mid-animation), then view the PNG. **That PNG is for inspection only.** Keep it out of the handoff and out of any upload; the deliverable is still `NAME.svg` / `NAME-still.svg`. Confirm the expected state is visible and legible, colors and styling look right, and nothing sensitive or unrelated is on screen. If it is wrong, adjust the scenario and re-record.
   - The window is sized to the SVG, so there is no grey margin; pass `--width`/`--height` only to override.
   - If Chromium fails with "No usable sandbox", re-run with `PREVIEW_NO_SANDBOX=1` (local, trusted files only, which these are).
7. **Hand off concisely.** State what was captured, the exact SVG paths and sizes, any WARN findings, and caveats. Do not claim it was uploaded, attached, or committed unless a separate authorized step did that. When the request combines capture with posting, pass the `NAME.svg` / `NAME-still.svg` paths (not preview PNGs) to that step, say which one suits embedding, and suggest a short caption. If the posting step has any reason to use a different format, that is a question for the user (see "If a format fails"), not something to do quietly.

## Facts that affect the output

- svgcast reads **asciicast v2** only. The bundled recorder writes v2; if you record with asciinema 3.x, ask for v2 (see install reference).
- Defaults to `--theme auto`: the SVG follows the viewer's light/dark setting (white background in a light viewer). Pass `--theme dark` or `light` to fix it.
- Animated SVG plays in `<img>` tags, including GitHub READMEs, but many chat and email clients show it as a still image or not at all. It is text-based, so it stays crisp and selectable, and is usually far smaller than a GIF; dense, constantly redrawing TUIs can be larger.
- Known svgcast limits: CJK and double-width characters may misalign; blinking text, faint text and strikethrough are not rendered; fonts come from the viewer's system unless embedded (`--embed-font` for Nerd Font glyphs).
- The recorder runs a clean `bash` (`$ ` prompt) in a scrubbed environment with an empty temporary `HOME`. Tools that need their config or state must be pointed at fixtures with `--env` or `--cwd`. Credentials are never passed through by default; do not add them with `--pass-env`.
- Do not include secrets in scenarios, tapes, command arguments, environment values, or captures.
