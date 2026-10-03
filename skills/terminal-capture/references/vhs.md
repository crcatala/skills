# VHS fallback: PNG, GIF, MP4, WebM

Use this path only when the user explicitly asks for a raster or video format (PNG, GIF, MP4, WebM). A suspicion that the destination cannot show animated SVG is not enough: keep the SVG and ask first (see "Choose the format" in `SKILL.md`). Otherwise use the default svgcast SVG workflow in `SKILL.md`.

The **safety gate applies unchanged**: decide what will be on screen first, use mock data, scan before sharing, stop and notify on any significant risk (see [safety.md](safety.md)). VHS has no built-in scanner. Scan your tape with `scripts/scan_secrets.py` before running it, and inspect the final image or video by eye; the scanner can read the tape but not a PNG or GIF, so there is no after-the-fact text check. Use the `Hide`/`Show` commands for setup only when the setup itself is safe.

VHS renders a terminal in headless Chrome via ttyd, so it differs slightly from a user's own emulator. It outputs PNG (`Screenshot`), GIF, MP4 and WebM, not SVG. Do not use unreviewed forks that add SVG output; svgcast covers that need.

## Requirements

- Check: `vhs --version` (needs **0.12.0 or newer**, which introduced `Set Columns` and `Set Rows`), plus `command -v ttyd ffmpeg`.
- Install: see the [VHS installation guide](https://github.com/charmbracelet/vhs#installation) (package managers, Docker).
- If anything is missing or too old, report it and stop, or ask to use an approved setup. Never install system packages or change the host environment on your own.

## Workflow

1. **Understand the target and state.** Identify the command, the state that proves the behavior, and any fixture/setup. Reuse a suitable project `.tape` if one exists. Do not guess at destructive, external, or credentialed actions.
2. **Plan a reproducible tape.** Explicit shell and dimensions, `TERM` set (usually `xterm-256color`), force color only if the app otherwise disables styling. Prefer fixture data over network services or personal data. VHS inherits your environment: run it with credentials unset, or in a clean `env -i` shell, and avoid commands that print the environment.
3. **Capture.** `Screenshot <path>.png` for a still. For a recording, declare `Output <path>.gif|.mp4|.webm`, then script keys and pauses. Use `Wait` with stable visible text where practical; a short `Sleep` only when no reliable wait exists. For TUIs, send navigation keys and wait for the target screen before a screenshot.
4. **Keep the artifact easy to find.** Default to a unique path under `/tmp` (or `mktemp -d`) so captures never enter the source tree. Never overwrite an existing artifact without checking.
5. **Verify.** Confirm the file exists, is non-empty, and has the requested format. View the image or recording (extract a frame with `ffmpeg` for video). Check styling, legibility, the expected state, and that no secrets, personal identifiers, or accidental prompts are visible.
6. **Hand off concisely.** What was captured, the exact path, and caveats. Do not claim it was uploaded or committed unless another authorized step did that.

## Tape patterns

Static screenshot:

```tape
Set Shell bash
Set Columns 100
Set Rows 30
Env TERM "xterm-256color"

Type "./my-cli --help"
Enter
Wait+Screen /Usage:/
Screenshot /tmp/my-cli-help.png
Sleep 500ms
```

`Screenshot` marks the next recorded frame to be saved as PNG, and VHS stops recording as soon as the last command finishes, so end the tape with a short `Sleep` after it or the PNG may never be written (silently).

Short interaction recording:

```tape
Output /tmp/my-tui-demo.gif
Set Shell bash
Set Columns 100
Set Rows 30
Set FontSize 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 0
Env TERM "xterm-256color"

Type "./my-tui"
Enter
Wait+Screen /Dashboard/
Sleep 500ms
Down
Enter
Wait+Screen /Saved successfully/
Sleep 1s
```

## Practical details

- Tape settings belong before interaction commands. Use `Set Columns`/`Set Rows` or pixel `Set Width`/`Set Height`, never both for the same axis.
- Quote `Output` and `Screenshot` paths (`Output "/tmp/my demo.gif"`); unquoted absolute paths with unusual characters can fail to parse.
- If recordings play faster than real time (frames dropped under load), lower the capture rate with `Set Framerate 25`.
- If headless Chrome cannot start because its sandbox is unavailable, report it. `VHS_NO_SANDBOX=true` works around it, but only use it for trusted local pages with the user's awareness.
- Avoid timing-only tapes where an output-ready signal exists.
- VHS can publish GIFs to `vhs.charm.sh` when `VHS_PUBLISH=true` is set or `--publish` is passed. Run `vhs` with `VHS_PUBLISH` unset and never pass `--publish`. After a GIF render VHS prints a "Host your GIF" hint; that is only a hint, nothing is uploaded.
- Preserve the generated file until any separately requested handoff is complete.
- Full command list: the [VHS command reference](https://github.com/charmbracelet/vhs#vhs-command-reference).
