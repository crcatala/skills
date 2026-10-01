---
name: terminal-capture
description: Capture real rendered terminal output from CLI tools and TUIs as PNG screenshots or scripted GIF/video using Charmbracelet VHS. Use when asked for terminal, command-line, or TUI screenshots, recordings, or visual proof. Not for browser or desktop-app screenshots, and not for uploading or posting artifacts.
compatibility: "Requires the vhs CLI (>= 0.12.0) with ttyd and ffmpeg on PATH."
---

# Terminal Capture with VHS

Use Charmbracelet VHS to render a CLI or TUI inside a controlled virtual terminal and save its visible output as an image or recording. This skill owns **capture only**: create and verify the requested local artifact, then report its path. Do not upload, post, or commit artifacts unless separately requested.

VHS captures terminal sessions, not browser or desktop windows. Its virtual terminal works well for normal ANSI styling and most TUIs, but may differ from a user's particular terminal emulator or fail to reproduce emulator-specific graphics/protocols.

## Choose the smallest useful artifact

- **Static proof / final state:** PNG via VHS `Screenshot`. Default to one PNG unless the user asks for more.
- **Interaction, transitions, progress, or animation:** GIF when a compact, easily previewed loop is useful; MP4/WebM when video is requested or a longer, smoother recording is more appropriate.
- Don't create a GIF/video just to show a still screen. Don't capture extra states or add decorative window chrome unless useful or requested.

When the request combines capture with posting (for example to a PR), create and verify the artifact here, then report the exact local path and a concise suggested caption so the upload step can use them.

## Requirements

- Check: `vhs --version` (needs **0.12.0 or newer**, which introduced `Set Columns` and `Set Rows`), plus `command -v ttyd ffmpeg`.
- Install: see the [VHS installation guide](https://github.com/charmbracelet/vhs#installation) (package managers, Docker).
- If anything is missing or too old, report it and stop, or ask to use an approved setup. Never install system packages or change the host environment on your own.

## Workflow

1. **Understand the target and state.** Identify the CLI/TUI command, the state that proves the behavior, and any needed fixture/setup. Reuse a suitable project `.tape` if one exists. Do not guess at destructive, external, or credentialed actions; use a safe fixture or ask first.
2. **Plan a reproducible tape.** Use an explicit shell and terminal dimensions appropriate to the output. Set `TERM` to a suitable terminal type (usually `xterm-256color`) and force color only if the application otherwise disables styling in the capture environment. Prefer fixture data and stable commands over network services or personal data.
3. **Capture the requested state.** Use `Screenshot <path>.png` for a still. For a recording, declare an `Output <path>.gif`, `.mp4`, or `.webm`, then script the actual keys and pauses needed to show the behavior. Use `Wait` with stable visible text when practical; use a short `Sleep` only when output has no reliable wait condition. For TUIs, send navigation/selection keys and wait for the intended screen before taking the screenshot.
4. **Keep the artifact easy to find.** Use a unique path under `/tmp` by default so generated captures don't pollute or accidentally enter the source tree. If the user requests a durable location, use that instead. Never overwrite an existing artifact without checking first.
5. **Verify the result.** Confirm the expected file exists, is non-empty, and has the requested format. Open/inspect the image or recording with available image/video viewing tools. Check that the relevant styling and state are visible, text is legible, and no secrets, unrelated terminal output, or accidental prompts are exposed. Re-capture or report the limitation if it is not right; don't present an uninspected artifact as verified.
6. **Return a concise handoff.** State what was captured, the exact artifact path, and any relevant caveat. Do not claim the artifact was attached, posted, or committed unless another authorized step actually did that.

## Tape patterns

### Static screenshot

```tape
Set Shell bash
Set Columns 100
Set Rows 30
Env TERM "xterm-256color"

Type "./my-cli --help"
Enter
Wait+Screen /Usage:/
Screenshot /tmp/my-cli-help.png
```

Replace the command and wait expression with ones that match the project. `Screenshot` captures the current terminal frame as PNG. If the target is a TUI, launch it, script the necessary key presses, wait for the target state, then screenshot that state.

### Short interaction recording

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

Choose an output extension supported by VHS for the requested format. Keep recordings focused and short; use `Set Framerate` or `Set PlaybackSpeed` only when needed. A tape can also include `Screenshot path.png` at a key point if both a still and a recording are useful.

## Practical details

- VHS tape settings belong before interaction commands. Set shell, dimensions, theme, and output configuration up front.
- Use explicit dimensions (`Set Columns` / `Set Rows`, or pixel `Set Width` / `Set Height`) so wrapping and TUI layout are repeatable. Do not combine `Set Columns` with `Set Width`, or `Set Rows` with `Set Height`.
- VHS supports scripted typing and keys (`Type`, `Enter`, arrows, `Tab`, `Ctrl+…`), waits, sleeps, `Hide`/`Show`, screenshots, and multiple output formats. See the [official tape command reference](https://github.com/charmbracelet/vhs#vhs-command-reference) when a command or setting is unclear.
- Avoid timing-only tapes where an output-ready signal exists. Fixed delays can be flaky on slower machines; use bounded `Wait` patterns for stable visible text where possible.
- Don't include secrets in tape source, command arguments, environment values, or captures. Use redacted fixtures and hide setup from recordings when appropriate.
- VHS can render PNG screenshots and GIF/MP4/WebM recordings; it does not post those files anywhere. Preserve the generated file until any separately requested handoff is complete.
