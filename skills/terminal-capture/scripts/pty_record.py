#!/usr/bin/env python3
"""Record a scripted terminal session to an asciicast v2 file.

Runs a clean bash in a pseudo-terminal of a fixed size, plays a scripted list of
steps (typing, keys, waits, sleeps), and writes the output stream as asciicast v2,
the format svgcast reads. Standard library only; Linux and macOS (needs `pty`).

The shell gets a scrubbed environment by default (see SAFE_ENV and --keep-home),
so credentials in the caller's environment cannot show up in the recording.

Usage:
  pty_record.py --out demo.cast --scenario steps.json [--cols 100] [--rows 30]
  pty_record.py --out demo.cast --run "my-cli --help" [--wait "Usage:"]

Scenario: a JSON list of steps, each a list:
  ["type", "text"]            type text, one character at a time
  ["run", "command"]          type the command, then press Enter
  ["key", "Enter"]            send a named key (see KEYS), or a literal string
  ["sleep", 1.5]              let the screen settle for N seconds
  ["wait", "regex", 10]       wait up to N seconds for regex in the output produced
                              since the last type/run/key step; fail if it never appears

Exit codes: 0 ok, 2 bad usage or scenario, 3 wait timed out, 4 shell exited early.
"""
import argparse
import fcntl
import json
import os
import pty
import re
import select
import shutil
import signal
import struct
import sys
import tempfile
import termios
import time

KEYS = {
    "Enter": "\r", "Tab": "\t", "Esc": "\x1b", "Escape": "\x1b", "Space": " ",
    "Backspace": "\x7f", "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C",
    "Left": "\x1b[D", "Home": "\x1b[H", "End": "\x1b[F", "PageUp": "\x1b[5~",
    "PageDown": "\x1b[6~", "Delete": "\x1b[3~",
}
# Host variables the recorded shell may inherit. Everything else is dropped.
SAFE_ENV = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ")

_ANSI = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"          # CSI
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC
    r"|\x1b[()][0-9A-Za-z]|\x1b[=>78]"  # charset / keypad / save-restore
)


class ScenarioError(Exception):
    pass


def strip_ansi(text):
    return _ANSI.sub("", text)


def key_bytes(name):
    """Named key, Ctrl+<letter>, or a literal string."""
    if name in KEYS:
        return KEYS[name]
    m = re.fullmatch(r"(?i)ctrl\+([a-z])", name)
    if m:
        return chr(ord(m.group(1).lower()) - 96)
    return name


def validate_scenario(steps):
    if not isinstance(steps, list) or not steps:
        raise ScenarioError("scenario must be a non-empty JSON list of steps")
    arity = {"type": 2, "run": 2, "key": 2, "sleep": 2}
    for i, step in enumerate(steps, 1):
        if not isinstance(step, list) or not step or not isinstance(step[0], str):
            raise ScenarioError(f"step {i}: expected a list like [\"type\", \"text\"]")
        op = step[0]
        if op == "wait":
            if len(step) not in (2, 3) or not isinstance(step[1], str):
                raise ScenarioError(f"step {i}: wait is [\"wait\", \"regex\", seconds?]")
            try:
                re.compile(step[1])
            except re.error as e:
                raise ScenarioError(f"step {i}: bad wait regex: {e}")
        elif op in arity:
            if len(step) != 2:
                raise ScenarioError(f"step {i}: {op} takes exactly one argument")
            if op == "sleep" and not isinstance(step[1], (int, float)):
                raise ScenarioError(f"step {i}: sleep takes a number of seconds")
            if op != "sleep" and not isinstance(step[1], str):
                raise ScenarioError(f"step {i}: {op} takes a string")
        else:
            raise ScenarioError(f"step {i}: unknown step '{op}' (type, run, key, sleep, wait)")


def build_env(pass_env, extra_env, keep_home, home_dir):
    env = {k: os.environ[k] for k in SAFE_ENV if k in os.environ}
    env.update(TERM="xterm-256color", COLORTERM="truecolor", PS1="$ ",
               HOME=os.environ.get("HOME", home_dir) if keep_home else home_dir)
    for name in pass_env:
        if name in os.environ:
            env[name] = os.environ[name]
    for item in extra_env:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise ScenarioError(f"--env expects NAME=VALUE, got '{item}'")
        env[name] = value
    return env


class Recorder:
    def __init__(self, cols, rows, env, cwd, type_delay, max_seconds):
        self.cols, self.rows, self.type_delay = cols, rows, type_delay
        self.events, self.since = [], ""
        self.deadline = time.time() + max_seconds
        shell = shutil.which("bash", path=env.get("PATH")) or "/bin/sh"
        args = [shell, "--noprofile", "--norc"] if shell.endswith("bash") else [shell]
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # child: the pty slave is stdin
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
            os.chdir(cwd)
            os.execvpe(shell, args, env)
        self.t0 = time.time()
        self.alive = True
        self.pump(0.4)  # initial prompt

    def pump(self, seconds):
        end = min(time.time() + seconds, self.deadline)
        while time.time() < end and self.alive:
            ready, _, _ = select.select([self.fd], [], [], 0.02)
            if not ready:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                data = b""
            if not data:
                self.alive = False
                break
            text = data.decode("utf-8", "replace")
            self.events.append([round(time.time() - self.t0, 3), "o", text])
            self.since += strip_ansi(text)
        if time.time() >= self.deadline:
            raise TimeoutError("--max-seconds exceeded")

    def send(self, text, delay):
        self.since = ""
        for ch in text:
            if not self.alive:
                return
            os.write(self.fd, ch.encode())
            self.pump(delay)

    def run_step(self, step):
        op = step[0]
        if op == "type":
            self.send(step[1], self.type_delay)
        elif op == "run":
            self.send(step[1], self.type_delay)
            self.send("\r", 0.05)
        elif op == "key":
            self.send(key_bytes(step[1]), 0.05)
        elif op == "sleep":
            self.pump(float(step[1]))
        elif op == "wait":
            limit = float(step[2]) if len(step) == 3 else 10.0
            pattern, end = re.compile(step[1]), time.time() + limit
            while not pattern.search(self.since):
                if time.time() > end:
                    raise LookupError(f"timed out after {limit:g}s waiting for /{step[1]}/")
                self.pump(0.05)

    def finish(self):
        self.pump(0.3)  # settle, so the last frame is the state the caller asked for
        try:
            os.kill(self.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(self.pid, 0)
        except ChildProcessError:
            pass


def write_cast(path, rec):
    header = {"version": 2, "width": rec.cols, "height": rec.rows, "timestamp": int(rec.t0),
              "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"}}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # may hold sensitive output
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        for ev in rec.events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description="Record a scripted terminal session as asciicast v2.")
    p.add_argument("--out", required=True, help="output .cast path")
    p.add_argument("--scenario", help="JSON file with the list of steps")
    p.add_argument("--run", help="shortcut scenario: run one command, wait, settle")
    p.add_argument("--wait", help="with --run: regex to wait for before settling")
    p.add_argument("--cols", type=int, default=100)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--cwd", default=os.getcwd(), help="working directory for the shell")
    p.add_argument("--type-delay", type=float, default=0.04, help="seconds between typed characters")
    p.add_argument("--max-seconds", type=float, default=180, help="hard limit for the whole recording")
    p.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="set a variable in the shell")
    p.add_argument("--pass-env", action="append", default=[], metavar="NAME",
                   help="copy a host variable into the shell (never a credential)")
    p.add_argument("--keep-home", action="store_true", help="use the real $HOME instead of an empty temp dir")
    a = p.parse_args(argv)

    home = None
    try:
        if bool(a.scenario) == bool(a.run):
            raise ScenarioError("give exactly one of --scenario or --run")
        if a.scenario:
            with open(a.scenario, encoding="utf-8") as f:
                steps = json.load(f)
        else:
            steps = [["run", a.run]] + ([["wait", a.wait, 15]] if a.wait else []) + [["sleep", 1.5]]
        validate_scenario(steps)
        if not (10 <= a.cols <= 500 and 3 <= a.rows <= 200):
            raise ScenarioError("--cols must be 10-500 and --rows 3-200")
        if os.path.exists(a.out):
            raise ScenarioError(f"refusing to overwrite existing {a.out}")
        if not os.path.isdir(a.cwd):
            raise ScenarioError(f"--cwd {a.cwd} is not a directory")
        home = tempfile.mkdtemp(prefix="terminal-capture-home-")
        env = build_env(a.pass_env, a.env, a.keep_home, home)
    except (ScenarioError, OSError, json.JSONDecodeError) as e:
        print(f"pty_record: {e}", file=sys.stderr)
        if home:
            shutil.rmtree(home, ignore_errors=True)
        return 2

    rec = None
    try:
        rec = Recorder(a.cols, a.rows, env, a.cwd, a.type_delay, a.max_seconds)
        for i, step in enumerate(steps, 1):
            if not rec.alive:
                print(f"pty_record: the shell exited before step {i}", file=sys.stderr)
                return 4
            try:
                rec.run_step(step)
            except LookupError as e:
                print(f"pty_record: step {i}: {e}", file=sys.stderr)
                return 3
        rec.finish()
        write_cast(a.out, rec)
    except TimeoutError as e:
        print(f"pty_record: {e}", file=sys.stderr)
        return 3
    finally:
        if rec and rec.alive:
            try:
                os.kill(rec.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        shutil.rmtree(home, ignore_errors=True)
    print(f"wrote {a.out} ({len(rec.events)} events, {rec.events[-1][0]:.1f}s)" if rec.events
          else f"wrote {a.out} (no output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
