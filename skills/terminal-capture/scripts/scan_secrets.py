#!/usr/bin/env python3
"""Scan terminal captures (and scenario/tape files) for secrets and personal identifiers.

Reads asciicast (.cast), SVG, or any text file and reports findings without ever
printing a full secret (only a short prefix and the length).

  BLOCK  credential-shaped content (keys, tokens, private keys, passwords in
         assignments, credentials in URLs). Stop and tell the user.
  WARN   identifiers that may be sensitive when shared (emails, IP addresses,
         home-directory paths, long high-entropy strings). Review each one.

The built-in rules are a dependency-free baseline. With --betterleaks BIN the same
extracted text is also scanned by a pinned Betterleaks binary (see
install_betterleaks.sh), which knows far more provider key formats; its findings
are BLOCK too. The two engines catch different things, so use both when you can.

A clean scan is a heuristic, not proof: it only knows common formats. Always
look at the capture too.

Usage: scan_secrets.py [--betterleaks BIN] [--fail-on-warn] [--json] PATH...   ("-" reads stdin)
Exit:  0 no BLOCK findings, 1 BLOCK findings (or WARN with --fail-on-warn),
       2 unreadable input, or the second engine failed and nothing blocking was found
       (fail closed: the scan is incomplete, treat it as not passed). Findings from the
       built-in rules are always reported, even when the second engine fails.
"""
import argparse
import base64
import binascii
import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile

_ANSI = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[=>78]"
)

# (rule name, regex) for tokens that are credentials by their shape alone.
TOKEN_RULES = [
    ("private-key-block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-style-key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-key", re.compile(r"\b[sr]k_(?:live|test)_[0-9a-zA-Z]{16,}\b")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer-or-basic-auth", re.compile(r"(?i)\bauthorization\s*[:=]\s*[\"']?(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]{3,}@[^/\s]+", re.I)),
]
# Assignments whose name looks sensitive: KEY=value, "key": "value", key: value.
_ASSIGN = re.compile(
    r"(?i)\b[\w.-]*(?:pass(?:word|wd|phrase)?|secret|token|api[_-]?key|apikey|access[_-]?key|"
    r"private[_-]?key|credential|auth(?!or))[\w.-]*[\"']?\s*[:=]\s*[\"']?([^\s\"',;]{8,})"
)
# Values that are clearly stand-ins, not real credentials.
_PLACEHOLDER = re.compile(
    r"(?i)example|dummy|fake|mock|sample|placeholder|redacted|changeme|change[_-]me|your[_-]|"
    r"not[_-]?a[_-]?real|xxxx|\*{3,}|<[^>]*>|\$\{?\w+|^\.{3}|…|^(?:true|false|none|null|undefined)$"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
_IPV4 = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")
_HOME = re.compile(r"(?:/home|/Users)/([A-Za-z_][A-Za-z0-9._-]*)/")
_BENIGN_USERS = {"demo", "user", "you", "me", "example", "runner", "ubuntu", "username", "name", "your-name"}
_ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{32,}")


def strip_ansi(text):
    return _ANSI.sub("", text)


# Escape sequences that carry text a terminal never draws: OSC (window title, OSC 8 hyperlink
# URLs, OSC 52 clipboard writes), DCS, APC, PM, SOS, and the screen/tmux title ESC k.
# strip_ansi() drops them, so their payloads are extracted and scanned separately: a
# recording keeps them even though the rendered SVG does not.
_OSC = re.compile(r"\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)")
_OTHER_STRINGS = re.compile(r"\x1b(?:[P_^X]((?:[^\x1b]|\x1b(?!\\))*)|k([^\x1b]*))\x1b\\", re.S)


def hidden_payloads(stream):
    """Payload text of string escape sequences in a raw terminal stream (OSC 52 also decoded)."""
    payloads = [m.group(1) for m in _OSC.finditer(stream)]
    payloads += [m.group(1) or m.group(2) or "" for m in _OTHER_STRINGS.finditer(stream)]
    for payload in list(payloads):
        if payload.startswith("52;"):  # OSC 52: "52;<selection>;<base64 clipboard data>"
            data = payload.split(";", 2)[-1].strip()
            try:
                payloads.append(base64.b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace"))
            except (binascii.Error, ValueError):
                pass
    return [p for p in payloads if p]


def visible_text(stream):
    """What a person sees, then (appended) the hidden escape-sequence payloads."""
    text = strip_ansi(stream)
    hidden = hidden_payloads(stream)
    return text + ("\n" + "\n".join(hidden) if hidden else "")


def redact(value):
    return f"{value[:4]}…({len(value)} chars)" if len(value) > 6 else "…"


def entropy(s):
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def load_text(path, data=None):
    """Return the text a human would see in the file, one line per screen line where possible."""
    if data is None:
        with open(path, "rb") as f:
            data = f.read()
    raw = data.decode("utf-8", "replace")
    if path.endswith(".cast"):
        lines = raw.splitlines()
        parts = []
        try:
            for line in lines[1:]:
                ev = json.loads(line)
                if isinstance(ev, list) and len(ev) == 3 and ev[1] in ("o", "i"):
                    parts.append(ev[2])
            header = json.loads(lines[0]) if lines else {}
        except (json.JSONDecodeError, TypeError):
            return visible_text(raw)
        env = header.get("env") or {}
        head = "\n".join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else ""
        return head + "\n" + visible_text("".join(parts)).replace("\r\n", "\n").replace("\r", "\n")
    if path.endswith(".svg"):
        texts = re.findall(r"<text\b[^>]*>(.*?)</text>", raw, re.S)
        if texts:  # one <text> is one screen line in svgcast output
            return "\n".join(html.unescape(re.sub(r"<[^>]+>", "", t)) for t in texts)
    return visible_text(raw)


def scan_text(text, source="<text>"):
    findings, seen = [], set()

    def add(sev, rule, lineno, value):
        key = (sev, rule, lineno, value)
        if key not in seen:
            seen.add(key)
            findings.append({"severity": sev, "rule": rule, "source": source,
                             "line": lineno, "preview": redact(value)})

    for lineno, line in enumerate(text.splitlines(), 1):
        for rule, rx in TOKEN_RULES:
            for m in rx.finditer(line):
                if not _PLACEHOLDER.search(m.group(0)):
                    add("BLOCK", rule, lineno, m.group(0))
        for m in _ASSIGN.finditer(line):
            value = m.group(1)
            if not _PLACEHOLDER.search(value):
                add("BLOCK", "sensitive-assignment", lineno, value)
        for m in _EMAIL.finditer(line):
            if not m.group(0).lower().endswith(("@example.com", "@example.org", "@users.noreply.github.com")) \
                    and not _PLACEHOLDER.search(m.group(0)):
                add("WARN", "email-address", lineno, m.group(0))
        for m in _IPV4.finditer(line):
            ip = m.group(0)
            if not ip.startswith(("127.", "0.")) and ip != "255.255.255.255":
                add("WARN", "ip-address", lineno, ip)
        for m in _HOME.finditer(line):
            if m.group(1).lower() not in _BENIGN_USERS:
                add("WARN", "home-directory-path", lineno, m.group(0))
        for m in _ENTROPY_TOKEN.finditer(line):
            tok = m.group(0)
            if (re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok) and entropy(tok) >= 4.3
                    and not _PLACEHOLDER.search(tok) and not any(
                        f["line"] == lineno and f["severity"] == "BLOCK" for f in findings)):
                add("WARN", "high-entropy-string", lineno, tok)
    return findings


class EngineError(Exception):
    """The second engine could not complete. `partial` holds findings already gathered."""

    def __init__(self, message, partial=()):
        super().__init__(message)
        self.partial = list(partial)


def betterleaks_command(binary):
    """The only way this skill invokes Betterleaks. Each flag matters for a safety gate:
    stdin (no files or git), stdlib regex engine (never runs the bundled WASM regex blob),
    --ignore-gitleaks-allow (otherwise a `betterleaks:allow` comment in the scanned text
    silences a finding), --redact (secrets never reach our output), and no --validation
    (never send a found credential to a provider)."""
    return [binary, "stdin", "--no-banner", "--no-color", "--log-level", "error",
            "--ignore-gitleaks-allow", "--regex-engine", "stdlib", "--redact",
            "-f", "json", "-r", "-", "--exit-code", "0"]


def run_betterleaks(binary, text, source):
    # Empty working directory and a near-empty environment: Betterleaks v1 loads
    # .betterleaks.toml / .gitleaks.toml / .gitleaksignore from the working directory
    # and BETTERLEAKS_CONFIG* / GITLEAKS_CONFIG* from the environment, any of which
    # could replace its rules and hide findings.
    with tempfile.TemporaryDirectory(prefix="terminal-capture-bl-") as tmp:
        env = {"HOME": tmp, "TMPDIR": tmp}
        try:
            proc = subprocess.run(betterleaks_command(binary), input=text, capture_output=True,
                                  text=True, env=env, cwd=tmp, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise EngineError(f"betterleaks could not run: {type(e).__name__}")
    if proc.returncode != 0:
        raise EngineError(f"betterleaks exited with status {proc.returncode}")
    try:
        items = json.loads(proc.stdout or "[]")
        return [{"severity": "BLOCK", "rule": "betterleaks:" + str(it["RuleID"]), "source": source,
                 "line": int(it.get("StartLine", 0)), "preview": "(redacted by engine)"}
                for it in items]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise EngineError("betterleaks produced an unreadable report")


def scan_path(path, betterleaks=None):
    if path == "-":
        text, source = visible_text(sys.stdin.read()), "<stdin>"
    else:
        text, source = load_text(path), path
    findings = scan_text(text, source)
    if betterleaks:
        try:
            findings += run_betterleaks(betterleaks, text, source)
        except EngineError as e:
            raise EngineError(str(e), partial=findings)
    return findings


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("paths", nargs="+")
    p.add_argument("--fail-on-warn", action="store_true", help="exit 1 on WARN findings too")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--betterleaks", metavar="BIN",
                   help="also scan with this pinned Betterleaks binary (see install_betterleaks.sh)")
    a = p.parse_args(argv)

    findings, engine, engine_error = [], a.betterleaks, None
    for path in a.paths:
        try:
            findings += scan_path(path, engine)
        except EngineError as e:
            # Keep what the built-in rules found (for this and every remaining file) so a
            # blocking finding is never lost because the second engine failed.
            findings += e.partial
            engine_error, engine = engine_error or str(e), None
        except OSError as e:
            print(f"scan_secrets: {e}", file=sys.stderr)
            return 2

    blocks = [f for f in findings if f["severity"] == "BLOCK"]
    warns = [f for f in findings if f["severity"] == "WARN"]
    if a.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f["severity"] != "BLOCK", f["source"], f["line"])):
            print(f"{f['severity']:5}  {f['source']}:{f['line']}  {f['rule']}  {f['preview']}")
        engines = "builtin+betterleaks" if a.betterleaks and not engine_error else "builtin only"
        print(f"scan_secrets: {len(blocks)} blocking, {len(warns)} warning(s) in {len(a.paths)} file(s) [{engines}]")
    if engine_error:
        print(f"scan_secrets: SCAN INCOMPLETE: {engine_error}; results above are from the built-in rules only",
              file=sys.stderr)
    if blocks or (warns and a.fail_on_warn):
        return 1
    return 2 if engine_error else 0


if __name__ == "__main__":
    sys.exit(main())
