# PTY recorder (`scripts/pty_record.py`)

Runs a clean `bash --noprofile --norc` (prompt `$ `) in a pseudo-terminal of a fixed size, plays a scripted list of steps, and writes an asciicast v2 file that svgcast renders. Standard library only; Linux and macOS.

```bash
# one command
python3 {baseDir}/scripts/pty_record.py --out /tmp/x.cast --run "my-cli --help" --wait "Usage:"
# a scenario
python3 {baseDir}/scripts/pty_record.py --out /tmp/x.cast --scenario steps.json --cols 110 --rows 32
```

Normally call it through `scripts/capture.sh`, which adds the secret scans and renders the SVGs.

## Scenario format

A JSON list of steps:

| Step | Meaning |
|---|---|
| `["type", "text"]` | type characters one at a time (`--type-delay`, default 0.04 s) |
| `["run", "cmd"]` | type `cmd`, then Enter |
| `["key", "Down"]` | named key: `Enter Tab Esc Space Backspace Delete Up Down Left Right Home End PageUp PageDown`, `Ctrl+<letter>`; any other string is sent literally (`"j"`, `"?"`) |
| `["sleep", 1.5]` | let output arrive/settle for N seconds |
| `["wait", "regex", 10]` | wait up to N seconds (default 10) for the regex to match ANSI-stripped output produced since the last `type`/`run`/`key`. A timeout fails the recording (exit 3). |

To type the word "Enter" use `["type", "Enter"]`.

## Writing good scenarios

- Use `wait` on distinctive visible text instead of long `sleep`s. TUIs that redraw with cursor movement can split text across writes, so wait on short, stable strings (a title, a label).
- Add a short `sleep` after each interaction so the animation shows the change (0.5-1 s), and a final `sleep` of ~1.5 s so the end state is visible.
- **End on the state you want in the still.** The still SVG is the last frame. The recorder stops the shell after the last step plus a brief settle, without sending `exit`, so a TUI left open stays on screen.
- Keep recordings short. `--svgcast-args "--idle-time-limit 2s"` collapses long pauses.

TUI example:

```json
[
  ["run", "my-tui"],
  ["wait", "Dashboard", 15],
  ["sleep", 1],
  ["key", "j"], ["sleep", 0.6],
  ["key", "j"], ["sleep", 0.6],
  ["key", "Enter"],
  ["wait", "Details", 10],
  ["sleep", 1.5]
]
```

## Environment and safety

- The shell inherits only `PATH`, `LANG`, `LC_ALL`, `LC_CTYPE` and `TZ`. `TERM=xterm-256color`, `COLORTERM=truecolor` and `PS1='$ '` are set. `HOME` is an empty temporary directory (removed afterwards) unless `--keep-home`.
- `--env NAME=VALUE` sets variables (use it to point tools at fixtures, for example a config or data directory). `--pass-env NAME` copies a host variable; never use it for credentials. `PATH` is inherited and may contain your username in paths.
- `--cwd DIR` sets the working directory. Use a fixture directory, not a real project, when the prompt or listings would reveal private paths or files.
- The `.cast` is written with mode 0600 and the recorder refuses to overwrite an existing file. `--max-seconds` (default 180) bounds the whole recording.

Exit codes: `0` ok, `2` bad usage or scenario, `3` wait or overall timeout, `4` the shell exited before the scenario finished.

Teardown is bounded: when the scenario ends (or fails) every process group in the shell's session, including the foreground program and background jobs, gets SIGHUP and then SIGKILL within a few seconds, so a program that ignores SIGHUP cannot hang the recorder or outlive it. Output is decoded incrementally, so multibyte characters split across reads (box-drawing, CJK, emoji) are preserved.

## Limits

No Windows support (needs the POSIX `pty` module). The recording is real terminal output, so what a tool prints depends on it detecting a terminal of this size and on `TERM`. If an app disables color, set an `--env` variable the app documents for forcing it (such as `FORCE_COLOR=1`) rather than editing the scenario.
