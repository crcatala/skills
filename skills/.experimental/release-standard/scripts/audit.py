#!/usr/bin/env python3
"""Compare a repository's release setup with the release standard.

Usage: python3 audit.py [repo-dir] [--json]

Read-only. Prints one line per check (ok / FAIL / warn) with what to change, and exits
1 when any check fails. Node repositories are detected by package.json, Python ones
by pyproject.toml.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

SHARED_SCRIPTS = {
    "scripts/prep-release.sh": "shared/prep-release.sh",
    "scripts/check-changelog.sh": "shared/check-changelog.sh",
}
NODE_SCRIPTS = {
    "scripts/release.mjs": "node/release.mjs",
    "scripts/build-info.mjs": "node/build-info.mjs",
    "scripts/test-package.sh": "node/test-package.sh",
}
PYTHON_SCRIPTS = {"scripts/build_info.py": "python/build_info.py"}

NODE_PACKAGE_SCRIPTS = {
    "release": "node scripts/release.mjs release",
    "release:dry": "node scripts/release.mjs release --dry-run",
    "release:publish": "node scripts/release.mjs publish",
    "release:prep": "bash scripts/prep-release.sh",
    "test:package": "bash scripts/test-package.sh",
}

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".venv", "venv", "__pycache__"}


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def check(self, ok: bool, what: str, fix: str = "", level: str = "fail") -> None:
        self.items.append({"status": "ok" if ok else level, "check": what, "fix": "" if ok else fix})

    @property
    def failed(self) -> bool:
        return any(i["status"] == "fail" for i in self.items)


def find_file(repo: Path, name: str, under: str = "src") -> Path | None:
    base = repo / under
    if not base.is_dir():
        return None
    for path in base.rglob(name):
        if not SKIP_DIRS.intersection(path.relative_to(repo).parts):
            return path
    return None


def canonical(report: Report, repo: Path, mapping: dict[str, str]) -> None:
    for dest, template in mapping.items():
        path = repo / dest
        if not path.exists():
            report.check(False, f"{dest} exists", f"copy templates/{template} to {dest}")
        elif path.read_bytes() != (TEMPLATES / template).read_bytes():
            report.check(False, f"{dest} matches the canonical copy",
                         f"replace it with templates/{template}; move project-specific parts to a hook file")
        else:
            report.check(True, f"{dest} matches the canonical copy")


def shared_checks(report: Report, repo: Path) -> None:
    changelog = repo / "CHANGELOG.md"
    report.check(changelog.exists() and "## [Unreleased]" in changelog.read_text(),
                 "CHANGELOG.md has an ## [Unreleased] section",
                 "add CHANGELOG.md in Keep a Changelog format with an ## [Unreleased] section")
    report.check((repo / "RELEASING.md").exists(), "RELEASING.md exists",
                 "write RELEASING.md from the language's template")
    canonical(report, repo, SHARED_SCRIPTS)

    readme = repo / "README.md"
    text = readme.read_text() if readme.exists() else ""
    report.check(bool(re.search(r"^##+ +Install", text, re.M | re.I)), "README has an Install section",
                 "add ## Install from the language's install-section template")
    report.check(bool(re.search(r"^##+ +.*from source", text, re.M | re.I)), "README documents installing from source",
                 "add a ### From source subsection (clone, install, build, link, --version)")
    report.check(bool(re.search(r"\bupdate\b", text)) and "--version" in text,
                 "README mentions --version and the update command",
                 "show `<tool> --version` after linking and add a ### Updating subsection", level="warn")


def node_checks(report: Report, repo: Path) -> None:
    pkg = json.loads((repo / "package.json").read_text())
    scripts = pkg.get("scripts", {})

    config_path = repo / ".release-it.json"
    if not config_path.exists():
        report.check(False, ".release-it.json exists", "copy templates/node/release-it.json to .release-it.json")
    else:
        config = json.loads(config_path.read_text())
        git = config.get("git", {})
        report.check(git.get("tagName") == "v${version}" and git.get("commitMessage") == "chore: release v${version}",
                     "release-it tags v${version} with commit 'chore: release v${version}'",
                     "set git.tagName and git.commitMessage as in the template")
        report.check(git.get("requireBranch") == "main" and git.get("requireCleanWorkingDir") is True,
                     "release-it requires a clean main", "set git.requireBranch: main and git.requireCleanWorkingDir: true")
        report.check(config.get("npm", {}).get("publish") is False, "release-it does not publish (release.mjs does)",
                     "set npm.publish: false; release.mjs publishes after the tag so the build stamp is right")
        hooks = config.get("hooks", {})
        init = " ".join(hooks.get("before:init", [])) if isinstance(hooks.get("before:init"), list) else str(hooks.get("before:init", ""))
        bump = " ".join(hooks.get("after:bump", [])) if isinstance(hooks.get("after:bump"), list) else str(hooks.get("after:bump", ""))
        report.check("check-changelog.sh" in init and "verify" in init, "before:init runs the changelog check and verify",
                     'set hooks["before:init"] to ["bash scripts/check-changelog.sh", "<pm> run verify"]')
        report.check("test:package" in bump, "after:bump runs the package smoke test",
                     'set hooks["after:bump"] to ["<pm> run test:package"]')
        report.check("@release-it/keep-a-changelog" in config.get("plugins", {}), "keep-a-changelog plugin is enabled",
                     "add the @release-it/keep-a-changelog plugin as in the template")

    canonical(report, repo, NODE_SCRIPTS)
    for name, expected in NODE_PACKAGE_SCRIPTS.items():
        report.check(scripts.get(name) == expected, f'package.json script "{name}"', f'set it to "{expected}"')
    report.check("verify" in scripts, 'package.json script "verify"', "add verify: lint, typecheck and tests")
    report.check("build-info.mjs" in scripts.get("build", ""), "build stamps build info",
                 'append "&& node scripts/build-info.mjs" to the build script')
    report.check("prepack" in scripts, 'package.json script "prepack" builds', 'add "prepack": "<pm> run build"')
    report.check("release:first" not in scripts, "no release:first script",
                 "remove it; a first release is `release -- <version> --npm.allowSameVersion`", level="warn")

    files = pkg.get("files")
    if files is not None:
        ships = any(f in ("dist", "dist/", "dist/**", "dist/build-info.json") for f in files)
        report.check(ships, 'package.json "files" ships dist/build-info.json', 'add "dist/build-info.json" to "files"')
    if pkg.get("private"):
        report.check(bool(pkg.get("repository")), "private package declares repository",
                     'add "repository" so `update` can reinstall from git')

    meta = find_file(repo, "cli-meta.ts") or find_file(repo, "cli-meta.js")
    report.check(meta is not None, "src has cli-meta (version line and update)", "copy templates/node/cli-meta.ts to src/")


def python_checks(report: Report, repo: Path) -> None:
    canonical(report, repo, PYTHON_SCRIPTS)
    report.check(find_file(repo, "cli_meta.py", under=".") is not None,
                 "package has cli_meta.py (version line and update)", "copy templates/python/cli_meta.py into the package")
    gitignore = repo / ".gitignore"
    report.check(gitignore.exists() and "_build_info.json" in gitignore.read_text(), ".gitignore ignores _build_info.json",
                 "add _build_info.json to .gitignore")
    makefile = repo / "Makefile"
    targets = set(re.findall(r"^([A-Za-z0-9_-]+):", makefile.read_text(), re.M)) if makefile.exists() else set()
    for target in ("bump", "prepublish", "release-dry", "release"):
        report.check(target in targets, f"Makefile target {target}", "see references/python.md for what it must do",
                     level="warn")


def audit(repo: Path) -> Report:
    report = Report()
    shared_checks(report, repo)
    if (repo / "package.json").exists():
        node_checks(report, repo)
    elif (repo / "pyproject.toml").exists():
        python_checks(report, repo)
    else:
        report.check(False, "language detected", "no package.json or pyproject.toml; apply the shared parts by hand",
                     level="warn")
    return report


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--json"]
    repo = Path(args[0] if args else ".").resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2
    report = audit(repo)
    if "--json" in argv:
        print(json.dumps({"repo": str(repo), "failed": report.failed, "checks": report.items}, indent=2))
    else:
        marks = {"ok": "ok  ", "fail": "FAIL", "warn": "warn"}
        for item in report.items:
            line = f"{marks[item['status']]}  {item['check']}"
            print(line + (f"\n        → {item['fix']}" if item["fix"] else ""))
        fails = sum(i["status"] == "fail" for i in report.items)
        warns = sum(i["status"] == "warn" for i in report.items)
        print(f"\n{fails} failing, {warns} warnings, {len(report.items)} checks")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
