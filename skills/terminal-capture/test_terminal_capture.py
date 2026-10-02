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
