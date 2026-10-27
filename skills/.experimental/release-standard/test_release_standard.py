"""Tests for the release-standard scripts and Python template (stdlib unittest)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load("audit", HERE / "scripts" / "audit.py")
cli_meta = load("cli_meta", TEMPLATES / "python" / "cli_meta.py")

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def sh(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env=GIT_ENV, capture_output=True, text=True, check=check)


def git_repo(path: Path) -> Path:
    sh(path, "git", "init", "-q", "-b", "main")
    return path


def commit_all(path: Path, message: str) -> None:
    sh(path, "git", "add", "-A")
    sh(path, "git", "commit", "-q", "-m", message)


class TempDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)


class CheckChangelogTest(TempDirTest):
    script = TEMPLATES / "shared" / "check-changelog.sh"

    def run_on(self, text: str) -> subprocess.CompletedProcess:
        (self.dir / "CHANGELOG.md").write_text(text)
        return sh(self.dir, "bash", str(self.script), check=False)

    def test_entries_pass(self):
        r = self.run_on("# Changelog\n\n## [Unreleased]\n\n### Added\n\n- A thing\n\n## [0.1.0] - 2026-01-01\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_empty_unreleased_fails(self):
        r = self.run_on("# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n### Added\n\n- Old\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no unreleased", r.stderr)

    def test_heading_without_items_fails(self):
        self.assertEqual(self.run_on("## [Unreleased]\n\n### Fixed\n\n").returncode, 1)

    def test_missing_file_fails(self):
        self.assertEqual(sh(self.dir, "bash", str(self.script), check=False).returncode, 1)


class PrepReleaseTest(TempDirTest):
    def test_lists_commits_since_last_tag(self):
        repo = git_repo(self.dir)
        (repo / "a").write_text("1")
        commit_all(repo, "feat: old thing")
        sh(repo, "git", "tag", "v0.1.0")
        (repo / "b").write_text("2")
        commit_all(repo, "fix: new thing\n\nCo-authored-by: someone <x@example.com>")
        out = sh(repo, "bash", str(TEMPLATES / "shared" / "prep-release.sh")).stdout
        self.assertIn("Changes since: v0.1.0", out)
        self.assertIn("## fix: new thing", out)
        self.assertNotIn("old thing", out)
        self.assertNotIn("Co-authored-by", out)
        self.assertLess(out.index("Changelog prompt"), out.index("## fix: new thing"))

    def test_first_release_shows_everything(self):
        repo = git_repo(self.dir)
        (repo / "a").write_text("1")
        commit_all(repo, "feat: first")
        out = sh(repo, "bash", str(TEMPLATES / "shared" / "prep-release.sh")).stdout
        self.assertIn("No prior tag", out)
        self.assertIn("## feat: first", out)


class PythonBuildInfoTest(TempDirTest):
    def test_stamps_commit_and_dirty_state(self):
        repo = git_repo(self.dir)
        (repo / ".gitignore").write_text("_build_info.json\n")
        commit_all(repo, "init")
        script = TEMPLATES / "python" / "build_info.py"
        sh(repo, sys.executable, str(script), "_build_info.json")
        info = json.loads((repo / "_build_info.json").read_text())
        self.assertEqual(info["commit"], sh(repo, "git", "rev-parse", "HEAD").stdout.strip())
        self.assertRegex(info["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertFalse(info["dirty"])
        (repo / "new").write_text("x")
        sh(repo, sys.executable, str(script), "_build_info.json")
        self.assertTrue(json.loads((repo / "_build_info.json").read_text())["dirty"])


class PythonCliMetaTest(unittest.TestCase):
    def test_format_version(self):
        info = {"version": "1.4.2", "commit": "a1b2c3d4e5f6", "date": "2026-10-27"}
        self.assertEqual(cli_meta.format_version("mytool", info), "mytool 1.4.2 (a1b2c3d 2026-10-27)")
        self.assertEqual(cli_meta.format_version("mytool", {**info, "dirty": True}), "mytool 1.4.2 (a1b2c3d-dirty 2026-10-27)")
        self.assertEqual(cli_meta.format_version("mytool", {"version": "1.4.2"}), "mytool 1.4.2")

    def test_detect_install(self):
        d = cli_meta.detect_install
        self.assertEqual(d("/src/tool/pkg", True), "checkout")
        self.assertEqual(d("/u/.local/share/uv/tools/x/lib/python3.12/site-packages/x", False), "uv")
        self.assertEqual(d("/u/.local/share/mise/installs/pipx-x/1.0/lib/site-packages/x", False), "mise")
        self.assertEqual(d("/u/.local/pipx/venvs/x/lib/python3.12/site-packages/x", False), "pipx")
        self.assertEqual(d("/proj/.venv/lib/python3.12/site-packages/x", False), "pip")
        self.assertEqual(d("/somewhere/x", False), "unknown")

    def test_installed_copy_is_never_a_checkout(self):
        path = Path("/repo/.venv/lib/python3.12/site-packages/x")
        self.assertIsNone(cli_meta.checkout_root(path))

    def test_update_steps(self):
        self.assertEqual(cli_meta.update_steps("uv", "d"), [["uv", "tool", "upgrade", "d"]])
        self.assertEqual(cli_meta.update_steps("pip", "d", python="py"), [["py", "-m", "pip", "install", "--upgrade", "d"]])
        self.assertEqual(cli_meta.update_steps("mise", "d"), [["mise", "upgrade", "--bump", "pipx:d"]])
        self.assertIsNone(cli_meta.update_steps("unknown", "d"))

    def test_compare_versions(self):
        c = cli_meta.compare_versions
        self.assertLess(c("1.2.3", "1.10.0"), 0)
        self.assertGreater(c("2.0.0", "1.99.99"), 0)
        self.assertEqual(c("v1.0.0", "1.0.0"), 0)
        self.assertLess(c("1.0.0-alpha", "1.0.0"), 0)
        self.assertGreater(c("1.0.0", "1.0.0-rc.1"), 0)


def compliant_node_repo(path: Path) -> Path:
    (path / "scripts").mkdir()
    (path / "src").mkdir()
    for dest, template in {**audit.SHARED_SCRIPTS, **audit.NODE_SCRIPTS}.items():
        shutil.copy(TEMPLATES / template, path / dest)
    shutil.copy(TEMPLATES / "node" / "release-it.json", path / ".release-it.json")
    shutil.copy(TEMPLATES / "node" / "cli-meta.ts", path / "src" / "cli-meta.ts")
    scripts = {**audit.NODE_PACKAGE_SCRIPTS, "build": "tsc && node scripts/build-info.mjs",
               "prepack": "npm run build", "verify": "npm test"}
    (path / "package.json").write_text(json.dumps({"name": "x", "version": "1.0.0", "scripts": scripts,
                                                   "files": ["dist", "README.md"]}))
    (path / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n")
    (path / "RELEASING.md").write_text("# Releasing\n")
    (path / "README.md").write_text("# x\n\n## Install\n\n### From source\n\n`x --version`\n\n### Updating\n\n`x update`\n")
    return path


class AuditTest(TempDirTest):
    def statuses(self, repo: Path) -> dict:
        return {i["check"]: i["status"] for i in audit.audit(repo).items}

    def test_compliant_node_repo_passes(self):
        report = audit.audit(compliant_node_repo(self.dir))
        self.assertFalse(report.failed, [i for i in report.items if i["status"] != "ok"])

    def test_edited_canonical_script_fails(self):
        repo = compliant_node_repo(self.dir)
        with open(repo / "scripts" / "test-package.sh", "a") as f:
            f.write("echo extra\n")
        self.assertEqual(self.statuses(repo)["scripts/test-package.sh matches the canonical copy"], "fail")

    def test_publishing_through_release_it_fails(self):
        repo = compliant_node_repo(self.dir)
        config = json.loads((repo / ".release-it.json").read_text())
        config["npm"] = {"publish": True}
        (repo / ".release-it.json").write_text(json.dumps(config))
        self.assertEqual(self.statuses(repo)["release-it does not publish (release.mjs does)"], "fail")

    def test_files_pattern_that_drops_the_stamp_fails(self):
        repo = compliant_node_repo(self.dir)
        pkg = json.loads((repo / "package.json").read_text())
        pkg["files"] = ["dist/**/*.js"]
        (repo / "package.json").write_text(json.dumps(pkg))
        self.assertEqual(self.statuses(repo)['package.json "files" ships dist/build-info.json'], "fail")

    def test_python_repo(self):
        repo = self.dir
        (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        (repo / "scripts").mkdir()
        statuses = self.statuses(repo)
        self.assertEqual(statuses["scripts/build_info.py exists"], "fail")
        self.assertEqual(statuses["Makefile target release"], "warn")
        self.assertNotIn(".release-it.json exists", statuses)

    def test_cli_exit_codes(self):
        audit_py = HERE / "scripts" / "audit.py"
        ok = sh(self.dir, sys.executable, str(audit_py), str(compliant_node_repo(self.dir)), check=False)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        os.remove(self.dir / "RELEASING.md")
        bad = sh(self.dir, sys.executable, str(audit_py), str(self.dir), "--json", check=False)
        self.assertEqual(bad.returncode, 1)
        self.assertTrue(json.loads(bad.stdout)["failed"])


if __name__ == "__main__":
    unittest.main()
