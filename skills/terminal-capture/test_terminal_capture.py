import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "scripts"))

import pty_record  # noqa: E402
import scan_secrets  # noqa: E402

# Fake credentials are assembled at runtime so this file never contains a
# credential-shaped literal (repo secret scanners would flag it).
FAKE_AWS = "AKIA" + "ABCDEFGHJKLMNPQR"
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
# Built so the validator's "no environment-specific paths" check does not trip on test data.
HOME_DIR = "/ho" + "me/"
FAKE_JWT = ".".join(["eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0", "dBjftJeZ4CVPmB92K27uhbUJU1p1r"])


def rules(findings, severity=None):
    return {f["rule"] for f in findings if severity in (None, f["severity"])}


class ScanTextTests(unittest.TestCase):
    def test_blocks_common_credential_formats(self):
        for secret, rule in [(FAKE_AWS, "aws-access-key-id"), (FAKE_GH, "github-token"), (FAKE_JWT, "jwt")]:
            with self.subTest(rule=rule):
                self.assertIn(rule, rules(scan_secrets.scan_text(f"key is {secret}"), "BLOCK"))

    def test_blocks_private_key_and_url_credentials(self):
        found = scan_secrets.scan_text("-----BEGIN OPENSSH PRIVATE KEY-----\nclone https://bot:hunter2pw@host.test/x.git")
        self.assertEqual(rules(found, "BLOCK"), {"private-key-block", "url-credentials"})

    def test_blocks_sensitive_assignments_in_env_and_json_styles(self):
        for line in ['export MY_API_TOKEN=abcd1234efgh5678', '"password": "correct-horse-battery"', "db_secret: s3cr3tvalue99"]:
            with self.subTest(line=line):
                self.assertIn("sensitive-assignment", rules(scan_secrets.scan_text(line), "BLOCK"))

    def test_placeholders_and_non_secrets_pass(self):
        clean = [
            "API_KEY=your_api_key_here", "TOKEN=${TOKEN}", "password=<redacted>", "AWS_KEY=" + "AKIA" + "IOSFODNN7EXAMPLE",
            "SECRET_TOKEN=dummy-token-for-demo", "AUTHOR=Someone Else", "authored: yesterday", "export PATH=/usr/bin:/bin",
        ]
        for line in clean:
            with self.subTest(line=line):
                self.assertEqual(rules(scan_secrets.scan_text(line), "BLOCK"), set())

    def test_identifiers_warn_but_do_not_block(self):
        found = scan_secrets.scan_text(f"mail dev@corp.test from 10.1.2.3 in {HOME_DIR}alice/work")
        self.assertEqual(rules(found, "BLOCK"), set())
        self.assertEqual(rules(found, "WARN"), {"email-address", "ip-address", "home-directory-path"})

    def test_benign_identifiers_are_ignored(self):
        text = f"ping 127.0.0.1 ; mail a@example.com ; cd {HOME_DIR}demo/app ; git <12345@users.noreply.github.com>"
        self.assertEqual(scan_secrets.scan_text(text), [])

    def test_report_never_contains_the_full_secret(self):
        for f in scan_secrets.scan_text(f"x {FAKE_GH}"):
            self.assertNotIn(FAKE_GH, json.dumps(f))
            self.assertIn("chars", f["preview"])


class LoadTextTests(unittest.TestCase):
    def test_cast_output_is_ansi_stripped_and_input_included(self):
        cast = "\n".join([
            json.dumps({"version": 2, "width": 80, "height": 24}),
            json.dumps([0.1, "o", "\x1b[1;31mtoken: \x1b[0m"]),
            json.dumps([0.2, "o", FAKE_GH[:20] + "\x1b[0m" + FAKE_GH[20:]]),
            json.dumps([0.3, "i", "typed"]),
        ])
        text = scan_secrets.load_text("x.cast", cast.encode())
        self.assertIn(FAKE_GH, text.replace("\n", ""))
        self.assertIn("typed", text)

    def test_svg_text_lines_are_extracted_and_unescaped(self):
        svg = f'<svg><text x="0">a &amp; b <tspan>{FAKE_AWS}</tspan></text><text>second</text></svg>'
        text = scan_secrets.load_text("x.svg", svg.encode())
        self.assertEqual(text.splitlines()[0], f"a & b {FAKE_AWS}")
        self.assertEqual(text.splitlines()[1], "second")


class ScanCliTests(unittest.TestCase):
    def run_scan(self, name, content, *flags):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, name)
            path.write_text(content)
            return subprocess.run([sys.executable, str(HERE / "scripts/scan_secrets.py"), *flags, str(path)],
                                  capture_output=True, text=True)

    def test_exit_codes(self):
        self.assertEqual(self.run_scan("a.txt", "hello").returncode, 0)
        self.assertEqual(self.run_scan("a.txt", FAKE_AWS).returncode, 1)
        self.assertEqual(self.run_scan("a.txt", f"see {HOME_DIR}alice/x").returncode, 0)
        self.assertEqual(self.run_scan("a.txt", f"see {HOME_DIR}alice/x", "--fail-on-warn").returncode, 1)

    def test_unreadable_input_is_an_error(self):
        r = subprocess.run([sys.executable, str(HERE / "scripts/scan_secrets.py"), "/nonexistent/file"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class ScenarioTests(unittest.TestCase):
    def test_valid_scenario_passes(self):
        pty_record.validate_scenario([["run", "ls"], ["wait", "x", 2], ["key", "Down"], ["sleep", 0.5], ["type", "q"]])

    def test_invalid_scenarios_are_rejected(self):
        for bad in ([], [["jump", "x"]], [["sleep", "soon"]], [["wait", "("]], [["type"]], ["run"], [["key", 3]]):
            with self.subTest(bad=bad):
                with self.assertRaises(pty_record.ScenarioError):
                    pty_record.validate_scenario(bad)

    def test_key_names(self):
        self.assertEqual(pty_record.key_bytes("Enter"), "\r")
        self.assertEqual(pty_record.key_bytes("Down"), "\x1b[B")
        self.assertEqual(pty_record.key_bytes("Ctrl+C"), "\x03")
        self.assertEqual(pty_record.key_bytes("j"), "j")

    def test_strip_ansi(self):
        self.assertEqual(pty_record.strip_ansi("\x1b[1;32mok\x1b[0m \x1b]0;title\x07done"), "ok done")

    def test_env_is_scrubbed_to_an_allowlist(self):
        os.environ["TC_TEST_SECRET_TOKEN"] = "nope"
        try:
            env = pty_record.build_env([], ["X=1"], False, "/tmp/h")
        finally:
            del os.environ["TC_TEST_SECRET_TOKEN"]
        self.assertNotIn("TC_TEST_SECRET_TOKEN", env)
        self.assertEqual((env["HOME"], env["X"], env["PS1"]), ("/tmp/h", "1", "$ "))
        with self.assertRaises(pty_record.ScenarioError):
            pty_record.build_env([], ["BAD"], False, "/tmp/h")


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "needs a POSIX pty and bash")
class RecordTests(unittest.TestCase):
    def record(self, d, *args, env_extra=None):
        out = Path(d, "t.cast")
        env = dict(os.environ, **(env_extra or {}))
        r = subprocess.run([sys.executable, str(HERE / "scripts/pty_record.py"), "--out", str(out), *args],
                           capture_output=True, text=True, env=env, timeout=60)
        return r, out

    def test_records_asciicast_v2_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, "--run", "echo hello-from-pty", "--wait", "hello-from-pty", "--cols", "60", "--rows", "10")
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = out.read_text().splitlines()
            header = json.loads(lines[0])
            self.assertEqual((header["version"], header["width"], header["height"]), (2, 60, 10))
            text = pty_record.strip_ansi("".join(json.loads(line)[2] for line in lines[1:]))
            self.assertIn("hello-from-pty", text)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)

    def test_recorded_shell_does_not_inherit_host_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, "--run", "env", "--wait", "PS1", env_extra={"TC_HOST_API_TOKEN": "leaky-value-123"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("leaky-value-123", out.read_text())

    def test_wait_timeout_fails_loudly_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            scenario = Path(d, "s.json")
            scenario.write_text(json.dumps([["run", "echo hi"], ["wait", "NEVER_APPEARS", 1]]))
            r, out = self.record(d, "--scenario", str(scenario))
            self.assertEqual(r.returncode, 3)
            self.assertFalse(out.exists())

    def test_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "t.cast").write_text("keep me")
            r, out = self.record(d, "--run", "true")
            self.assertEqual(r.returncode, 2)
            self.assertEqual(out.read_text(), "keep me")


def write_fake_engine(directory, report="[]", exit_code=0, log_name="invocation.log"):
    """A stand-in for the betterleaks binary that records how it was invoked."""
    log = Path(directory, log_name)
    script = Path(directory, "fake-betterleaks")
    script.write_text(
        "#!/bin/sh\n"
        f'{{ echo "ARGS:$*"; echo "FILES:$(ls -A | tr "\\n" " ")"; '
        f'echo "ENV:$(env | cut -d= -f1 | sort | tr "\\n" " ")"; }} > "{log}"\n'
        "cat > /dev/null\n"
        f"cat <<'REPORT'\n{report}\nREPORT\n"
        f"exit {exit_code}\n"
    )
    script.chmod(0o755)
    return str(script), log


class BetterleaksEngineTests(unittest.TestCase):
    def test_command_has_the_safety_flags_and_no_network_flags(self):
        cmd = scan_secrets.betterleaks_command("/bin/bl")
        self.assertEqual(cmd[:2], ["/bin/bl", "stdin"])
        for flag in ("--ignore-gitleaks-allow", "--redact"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--regex-engine") + 1], "stdlib")
        for forbidden in ("--validation", "--validate", "-v", "--analyze", "--diagnostics"):
            self.assertNotIn(forbidden, cmd)

    def test_runs_in_an_empty_directory_with_a_scrubbed_environment(self):
        with tempfile.TemporaryDirectory() as d:
            binary, log = write_fake_engine(d)
            extra = {"BETTERLEAKS_CONFIG": "/attacker/config.toml", "GITLEAKS_CONFIG_TOML": "x", "TC_TEST_SECRET": "nope"}
            os.environ.update(extra)
            try:
                scan_secrets.run_betterleaks(binary, "hello", "t.txt")
            finally:
                for k in extra:
                    del os.environ[k]
            lines = log.read_text().splitlines()
            files = next(x for x in lines if x.startswith("FILES:"))
            env = next(x for x in lines if x.startswith("ENV:"))
            self.assertEqual(files.strip(), "FILES:")  # empty working directory
            for leaked in extra:
                self.assertNotIn(leaked, env)

    def test_findings_become_blocking_and_never_expose_the_value(self):
        report = json.dumps([{"RuleID": "some-provider-key", "StartLine": 7, "Secret": "REDACTED", "Match": "REDACTED"}])
        with tempfile.TemporaryDirectory() as d:
            binary, _ = write_fake_engine(d, report)
            found = scan_secrets.run_betterleaks(binary, "x", "t.txt")
        self.assertEqual([(f["severity"], f["rule"], f["line"]) for f in found],
                         [("BLOCK", "betterleaks:some-provider-key", 7)])

    def test_fails_closed_when_the_engine_misbehaves(self):
        with tempfile.TemporaryDirectory() as d:
            for kwargs in ({"exit_code": 3}, {"report": "not json"}, {"report": '[{"nope": 1}]'}):
                with self.subTest(kwargs=kwargs):
                    binary, _ = write_fake_engine(d, **kwargs)
                    with self.assertRaises(scan_secrets.EngineError):
                        scan_secrets.run_betterleaks(binary, "x", "t.txt")
        with self.assertRaises(scan_secrets.EngineError):
            scan_secrets.run_betterleaks("/nonexistent/betterleaks", "x", "t.txt")

    def test_cli_combines_engines_and_maps_exit_codes(self):
        script = str(HERE / "scripts/scan_secrets.py")
        with tempfile.TemporaryDirectory() as d:
            clean = Path(d, "clean.txt")
            clean.write_text("hello")
            hit, _ = write_fake_engine(d, json.dumps([{"RuleID": "r", "StartLine": 1}]))
            r = subprocess.run([sys.executable, script, "--betterleaks", hit, str(clean)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("betterleaks:r", r.stdout)
            self.assertIn("builtin+betterleaks", r.stdout)
            bad, _ = write_fake_engine(d, exit_code=9)
            r = subprocess.run([sys.executable, script, "--betterleaks", bad, str(clean)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            r = subprocess.run([sys.executable, script, str(clean)], capture_output=True, text=True)
            self.assertEqual((r.returncode, "builtin only" in r.stdout), (0, True))


REAL_BETTERLEAKS = os.environ.get("BETTERLEAKS_BIN")


@unittest.skipUnless(REAL_BETTERLEAKS and os.access(REAL_BETTERLEAKS, os.X_OK),
                     "set BETTERLEAKS_BIN to the pinned betterleaks binary to run these")
class RealBetterleaksTests(unittest.TestCase):
    # A provider format the built-in rules do not know but Betterleaks does.
    GROQ_KEY = "gsk_" + "Qm4Zx8Lp2Vt9Kc3Wb7Nd5Rh1Tf6Ys0Ja3Ge8Uo2Xi5Ml9Pq4BnWz"  # 52 chars after the prefix

    def test_fixture_key_has_the_shape_the_rule_expects(self):
        self.assertEqual(len(self.GROQ_KEY) - len("gsk_"), 52)

    def scan(self, text):
        return scan_secrets.run_betterleaks(REAL_BETTERLEAKS, text, "t.txt")

    def test_finds_what_the_builtin_rules_miss(self):
        text = f"$ export VALUE={self.GROQ_KEY}"
        self.assertEqual(rules(scan_secrets.scan_text(text), "BLOCK"), set())
        self.assertTrue(self.scan(text))

    def test_clean_text_has_no_findings(self):
        self.assertEqual(self.scan("$ ls\nREADME.md  src  docs\n"), [])

    def test_allow_comments_cannot_silence_a_finding(self):
        for marker in ("gitleaks:allow", "betterleaks:allow"):
            with self.subTest(marker=marker):
                self.assertTrue(self.scan(f"export VALUE={self.GROQ_KEY}  # {marker}"))

    def test_config_in_cwd_or_env_cannot_hide_findings(self):
        with tempfile.TemporaryDirectory() as d:
            for name in (".betterleaks.toml", ".gitleaks.toml"):
                Path(d, name).write_text("[allowlist]\nregexes = ['''.*''']\n")
            old_cwd = os.getcwd()
            os.chdir(d)
            os.environ["BETTERLEAKS_CONFIG"] = str(Path(d, ".betterleaks.toml"))
            try:
                self.assertTrue(self.scan(f"export VALUE={self.GROQ_KEY}"))
            finally:
                os.chdir(old_cwd)
                del os.environ["BETTERLEAKS_CONFIG"]

    def test_output_never_contains_the_secret(self):
        found = self.scan(f"export VALUE={self.GROQ_KEY}")
        self.assertNotIn(self.GROQ_KEY, json.dumps(found))


def cast_with(*chunks):
    """A minimal asciicast v2 file whose output events are the given raw chunks."""
    header = json.dumps({"version": 2, "width": 80, "height": 24})
    return "\n".join([header] + [json.dumps([0.1 * i, "o", c]) for i, c in enumerate(chunks, 1)]).encode()


class HiddenPayloadTests(unittest.TestCase):
    """Escape sequences that carry text a terminal never draws are still kept in a recording."""

    def scan_cast(self, *chunks):
        return scan_secrets.scan_text(scan_secrets.load_text("x.cast", cast_with(*chunks)))

    def test_secret_in_every_hidden_sequence_form_is_found(self):
        b64 = __import__("base64").b64encode(FAKE_GH.encode()).decode()
        forms = {
            "osc title (BEL)": f"\x1b]0;title {FAKE_AWS}\x07shown\n",
            "osc title (ST)": f"\x1b]2;title {FAKE_AWS}\x1b\\shown\n",
            "osc 8 hyperlink url": f"\x1b]8;;https://example.test/login?t={FAKE_AWS}\x1b\\click\x1b]8;;\x1b\\\n",
            "osc 52 clipboard (base64)": f"\x1b]52;c;{b64}\x07copied\n",
            "dcs": f"\x1bP1;1|{FAKE_AWS}\x1b\\",
            "apc": f"\x1b_Gi=1;{FAKE_AWS}\x1b\\",
            "pm": f"\x1b^{FAKE_AWS}\x1b\\",
            "screen/tmux title": f"\x1bk{FAKE_AWS}\x1b\\",
            "unterminated osc": f"\x1b]0;{FAKE_AWS}",
        }
        for name, chunk in forms.items():
            with self.subTest(form=name):
                found = self.scan_cast(chunk)
                self.assertTrue(rules(found, "BLOCK"), f"{name}: secret not found")

    def test_secret_split_across_events_inside_a_hidden_sequence_is_found(self):
        self.assertTrue(rules(self.scan_cast("\x1b]0;" + FAKE_AWS[:9], FAKE_AWS[9:] + "\x07"), "BLOCK"))

    def test_hidden_text_without_a_secret_is_not_a_finding(self):
        self.assertEqual(self.scan_cast("\x1b]0;my-project - zsh\x07\x1b]8;;https://example.test/docs\x1b\\docs\x1b]8;;\x1b\\\n"), [])

    def test_visible_text_is_unchanged_by_the_extraction(self):
        text = scan_secrets.load_text("x.cast", cast_with("\x1b[1mhello\x1b[0m \x1b]0;t\x07world\n"))
        self.assertIn("hello world", text)

    def test_plain_files_and_stdin_style_text_are_covered_too(self):
        text = scan_secrets.load_text("notes.txt", f"\x1b]0;{FAKE_AWS}\x07ok".encode())
        self.assertTrue(rules(scan_secrets.scan_text(text), "BLOCK"))


class EngineFailureTests(unittest.TestCase):
    SCRIPT = str(HERE / "scripts/scan_secrets.py")

    def run_scan(self, engine, *files):
        return subprocess.run([sys.executable, self.SCRIPT, "--betterleaks", engine, *map(str, files)],
                              capture_output=True, text=True)

    def test_builtin_findings_survive_an_engine_failure(self):
        with tempfile.TemporaryDirectory() as d:
            bad, _ = write_fake_engine(d, exit_code=3)
            leak = Path(d, "leak.txt")
            leak.write_text(f"key {FAKE_AWS}")
            r = self.run_scan(bad, leak)
        self.assertEqual(r.returncode, 1)  # the finding decides the exit code, not the failure
        self.assertIn("aws-access-key-id", r.stdout)
        self.assertIn("SCAN INCOMPLETE", r.stderr)

    def test_a_failure_with_nothing_found_is_an_incomplete_scan(self):
        with tempfile.TemporaryDirectory() as d:
            bad, _ = write_fake_engine(d, exit_code=3)
            clean = Path(d, "clean.txt")
            clean.write_text("hello")
            r = self.run_scan(bad, clean)
        self.assertEqual(r.returncode, 2)
        self.assertIn("SCAN INCOMPLETE", r.stderr)
        self.assertIn("builtin only", r.stdout)

    def test_files_after_the_failure_are_still_scanned_by_the_builtin_rules(self):
        with tempfile.TemporaryDirectory() as d:
            bad, _ = write_fake_engine(d, exit_code=3)
            first, second = Path(d, "a.txt"), Path(d, "b.txt")
            first.write_text("hello")
            second.write_text(f"key {FAKE_AWS}")
            r = self.run_scan(bad, first, second)
        self.assertEqual(r.returncode, 1)
        self.assertIn("b.txt", r.stdout)


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "needs a POSIX pty and bash")
class CaptureScriptTests(unittest.TestCase):
    """capture.sh with stub installers: no network, no Go, real recorder and scanner."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scripts = Path(self.tmp.name, "scripts")
        shutil.copytree(HERE / "scripts", self.scripts, ignore=shutil.ignore_patterns("__pycache__"))
        stub = Path(self.tmp.name, "svgcast")
        stub.write_text(
            "#!/bin/sh\n"
            'while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; --still) still="$2"; shift;; esac; shift; done\n'
            'echo "<svg><text>ok</text></svg>" > "$out"; echo "<svg><text>ok</text></svg>" > "$still"\n')
        stub.chmod(0o755)
        self.install("install_svgcast.sh", str(stub))

    def install(self, name, binary):
        path = self.scripts / name
        path.write_text(f"#!/bin/sh\necho {binary}\n")
        path.chmod(0o755)

    def counting_engine(self, fail_from):
        """An engine that works for the first scans and fails from the Nth call on."""
        counter = Path(self.tmp.name, "calls")
        engine = Path(self.tmp.name, "engine")
        engine.write_text(
            "#!/bin/sh\n"
            f'n=$(cat "{counter}" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{counter}"\n'
            f"cat > /dev/null\nif [ $n -ge {fail_from} ]; then exit 3; fi\necho '[]'\n")
        engine.chmod(0o755)
        self.install("install_betterleaks.sh", str(engine))

    def capture(self, command):
        scenario = Path(self.tmp.name, "s.json")
        scenario.write_text(json.dumps([["run", command], ["sleep", 0.2]]))
        out = Path(self.tmp.name, "out")
        r = subprocess.run(["bash", str(self.scripts / "capture.sh"), "--out-dir", str(out), "demo", str(scenario)],
                           capture_output=True, text=True, timeout=90)
        return r, sorted(p.name for p in out.glob("*")) if out.exists() else []

    def test_clean_capture_keeps_all_three_files(self):
        self.counting_engine(fail_from=99)
        r, files = self.capture("echo hello")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(files, ["demo-still.svg", "demo.cast", "demo.svg"])

    def test_a_secret_in_the_output_blocks_and_deletes_everything(self):
        self.counting_engine(fail_from=99)
        r, files = self.capture(f"python3 -c \"print('AKIA'+'{FAKE_AWS[4:]}')\"")
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertEqual(files, [])

    def test_a_secret_hidden_in_an_osc_payload_blocks_and_deletes_everything(self):
        self.counting_engine(fail_from=99)
        r, files = self.capture(
            f"python3 -c \"import sys;sys.stdout.write('\\x1b]0;'+'AKIA'+'{FAKE_AWS[4:]}'+'\\x07visible\\n')\"")
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertEqual(files, [])

    def test_engine_failure_after_recording_deletes_the_unscanned_recording(self):
        self.counting_engine(fail_from=2)  # scenario scan passes, recording scan fails
        r, files = self.capture("echo hello")
        self.assertEqual(r.returncode, 11, r.stdout + r.stderr)
        self.assertEqual(files, [])
        self.assertIn("could not complete", r.stderr)

    def test_engine_failure_before_recording_records_nothing(self):
        self.counting_engine(fail_from=1)
        r, files = self.capture("echo hello")
        self.assertEqual(r.returncode, 11, r.stdout + r.stderr)
        self.assertEqual(files, [])

    def test_blocking_finding_wins_over_engine_failure_and_is_reported(self):
        self.counting_engine(fail_from=2)
        r, files = self.capture(f"python3 -c \"print('AKIA'+'{FAKE_AWS[4:]}')\"")
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertIn("aws-access-key-id", r.stdout)
        self.assertEqual(files, [])

    def test_existing_artifacts_are_never_deleted_by_a_refused_run(self):
        self.counting_engine(fail_from=99)
        out = Path(self.tmp.name, "out")
        out.mkdir()
        Path(out, "demo.cast").write_text("precious")
        r, files = self.capture("echo hello")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(Path(out, "demo.cast").read_text(), "precious")


class Utf8StreamTests(unittest.TestCase):
    def test_multibyte_characters_split_across_reads_are_preserved(self):
        data = ("─" * 5 + "é漢😀").encode()
        for cut in range(1, len(data)):
            with self.subTest(cut=cut):
                stream = pty_record.Utf8Stream()
                text = stream.feed(data[:cut]) + stream.feed(data[cut:]) + stream.flush()
                self.assertEqual(text, data.decode())

    def test_genuinely_invalid_bytes_are_replaced_not_fatal(self):
        stream = pty_record.Utf8Stream()
        self.assertEqual(stream.feed(b"a\xffb") + stream.flush(), "a�b")

    def test_a_truncated_character_at_the_end_is_flushed_as_a_replacement(self):
        stream = pty_record.Utf8Stream()
        self.assertEqual(stream.feed("é".encode()[:1]) + stream.flush(), "�")


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "needs a POSIX pty and bash")
class RecorderRobustnessTests(unittest.TestCase):
    def record(self, d, steps, *args, timeout=40):
        scenario, out = Path(d, "s.json"), Path(d, "t.cast")
        scenario.write_text(json.dumps(steps))
        r = subprocess.run([sys.executable, str(HERE / "scripts/pty_record.py"), "--out", str(out),
                            "--scenario", str(scenario), *args], capture_output=True, text=True, timeout=timeout)
        return r, out

    def leftover(self, marker):
        if not shutil.which("pgrep"):
            self.skipTest("pgrep not available")
        return subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True).stdout.split()

    def test_long_box_drawing_output_has_no_replacement_characters(self):
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, [["run", 'python3 -c "print(chr(0x2500)*60000)"'], ["sleep", 0.5]], "--cols", "200")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = "".join(json.loads(line)[2] for line in out.read_text().splitlines()[1:])
            self.assertEqual((text.count("─"), text.count("�")), (60000, 0))

    def test_a_foreground_program_that_ignores_sighup_cannot_hang_the_recorder(self):
        marker = "271.5123"
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, [["run", f'trap "" HUP; sleep {marker}'], ["sleep", 0.3]])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out.exists())
        self.assertEqual(self.leftover(marker), [])

    def test_exec_into_a_process_that_ignores_sighup_is_still_torn_down(self):
        marker = "272.5123"
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, [["run", f"exec sh -c 'trap \"\" HUP; sleep {marker}'"], ["sleep", 0.3]])
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.leftover(marker), [])

    def test_a_background_job_that_ignores_sighup_is_torn_down_too(self):
        marker = "273.5123"
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, [["run", f'(trap "" HUP; sleep {marker}) & sleep 1'], ["sleep", 0.3]])
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.leftover(marker), [])

    def test_a_failed_wait_also_tears_the_session_down(self):
        marker = "274.5123"
        with tempfile.TemporaryDirectory() as d:
            r, out = self.record(d, [["run", f'trap "" HUP; sleep {marker}'], ["wait", "NEVER_APPEARS", 1]])
            self.assertEqual(r.returncode, 3)
        self.assertEqual(self.leftover(marker), [])


class PackagingTests(unittest.TestCase):
    def test_pinned_versions_are_consistent_across_files(self):
        for installer, prefix in (("install_svgcast.sh", "SVGCAST"), ("install_betterleaks.sh", "BETTERLEAKS")):
            script = (HERE / "scripts" / installer).read_text()
            version = re.search(rf'^{prefix}_VERSION="(v[\d.]+)"', script, re.M).group(1)
            self.assertRegex(script, re.compile(rf'^{prefix}_MODULE_HASH="h1:[A-Za-z0-9+/=]+"', re.M))
            for doc in ("SKILL.md", "references/install.md"):
                self.assertIn(version, (HERE / doc).read_text(), f"{doc} does not mention {prefix} pin {version}")

    def test_shell_scripts_parse(self):
        for name in ("capture.sh", "install_svgcast.sh", "install_betterleaks.sh"):
            r = subprocess.run(["bash", "-n", str(HERE / "scripts" / name)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
