#!/usr/bin/env python3
"""List recently active GitHub repositories and report their icon status.

Reads repositories through the GitHub API (the gh CLI); nothing is cloned.

Usage:
  scan.py [--owner LOGIN ...] [--days 30] [--repo OWNER/NAME ...] [--json]

With no --owner or --repo, scans every repository the authenticated gh account
can access (owned, collaborator, organization member). Forks, archived and empty
repositories are always skipped.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import icon_paths  # noqa: E402

README_IMG_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


class GhError(RuntimeError):
    pass


GH_TIMEOUT = 60  # seconds per gh call


def gh(*args):
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise GhError(f"gh {' '.join(args)} timed out after {GH_TIMEOUT}s")
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip() or f"gh {' '.join(args)} failed")
    return proc.stdout


def gh_json(*args):
    return json.loads(gh(*args) or "null")


def _normalize_rest(r):
    return {
        "nameWithOwner": r["full_name"],
        "description": r.get("description"),
        "pushedAt": r.get("pushed_at") or "1970-01-01T00:00:00Z",
        "isPrivate": r.get("private", False),
        "defaultBranchRef": {"name": r["default_branch"]} if r.get("default_branch") else None,
        "isFork": r.get("fork", False),
        "isArchived": r.get("archived", False),
        "isEmpty": r.get("size", 1) == 0,
    }


def list_accessible_repos():
    """Every repository the authenticated account can access: owned, collaborator, org member."""
    out = gh(
        "api", "--paginate",
        "user/repos?affiliation=owner,collaborator,organization_member&sort=pushed&per_page=100",
        "--jq", ".[]",
    )
    return [_normalize_rest(json.loads(line)) for line in out.splitlines() if line.strip()]


def list_owner_repos(owner):
    fields = "nameWithOwner,description,pushedAt,isPrivate,defaultBranchRef,isEmpty,isFork,isArchived"
    return gh_json("repo", "list", owner, "--limit", "1000", "--json", fields)


def recent_sources(repos, days):
    """Drop forks, archived, empty and stale repositories."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    keep, seen = [], set()
    for r in repos:
        if r["nameWithOwner"] in seen:
            continue
        seen.add(r["nameWithOwner"])
        if r.get("isFork") or r.get("isArchived") or r.get("isEmpty") or not r.get("defaultBranchRef"):
            continue
        if datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00")) >= cutoff:
            keep.append(r)
    return keep


def view_repo(name):
    fields = "nameWithOwner,description,pushedAt,isPrivate,defaultBranchRef,isFork,isArchived"
    return gh_json("repo", "view", name, "--json", fields)


def readme_header_image(name):
    """src of an image in the README's first heading, if any."""
    try:
        data = gh_json("api", f"repos/{name}/readme")
    except GhError:
        return None, False
    text = base64.b64decode(data.get("content", "")).decode("utf-8", "replace")
    for line in text.splitlines()[:15]:
        stripped = line.strip()
        if stripped.startswith("#") or stripped.lower().startswith("<h1"):
            match = README_IMG_RE.search(stripped) or MD_IMG_RE.search(stripped)
            return (match.group(1) if match else None), True
    return None, True


def inspect(repo):
    name = repo["nameWithOwner"]
    branch = (repo.get("defaultBranchRef") or {}).get("name")
    out = {
        "repo": name,
        "description": repo.get("description") or "",
        "pushed_at": (repo.get("pushedAt") or "")[:10],
        "private": repo.get("isPrivate", False),
        "default_branch": branch,
        "icon": None,
        "via": None,
        "note": None,
        "logos": [],
    }
    if not branch:
        out.update(status="error", error="empty repository (no default branch)")
        return out
    try:
        tree = gh_json("api", f"repos/{name}/git/trees/{branch}?recursive=1")
    except GhError as exc:
        out.update(status="error", error=str(exc))
        return out
    paths = {e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"}

    def read_file(path):
        try:
            data = gh_json("api", f"repos/{name}/contents/{path}?ref={branch}")
            return base64.b64decode(data.get("content", "")).decode("utf-8", "replace")
        except (GhError, ValueError):
            return None

    out.update(icon_paths.classify(paths, read_file))
    if tree.get("truncated"):
        out["note"] = ((out.get("note") or "") + " (file list truncated; large repo)").strip()
    out["readme_header_image"], out["has_readme"] = readme_header_image(name)
    return out


def render_table(rows):
    lines = [
        "| # | Repo | Last push | Icon status | Icon path / candidates | README header image |",
        "|---|---|---|---|---|---|",
    ]
    labels = {"ok": "✅ found", "nonstandard": "⚠️ logo, not standard", "none": "❌ none", "error": "error"}
    for i, r in enumerate(rows, 1):
        if r["status"] == "ok":
            detail = f"`{r['icon']}`" + (f" (via {r['via']})" if r["via"] != "well-known" else "")
        elif r["status"] == "error":
            detail = r.get("error", "")
        else:
            detail = ", ".join(f"`{p}`" for p in r["logos"]) or "—"
        if r.get("note"):
            detail += f"; {r['note']}"
        header = (
            f"`{r['readme_header_image']}`"
            if r.get("readme_header_image")
            else ("—" if r.get("has_readme") else "no README")
        )
        lines.append(
            f"| {i} | {r['repo']} | {r['pushed_at']} | {labels[r['status']]} | {detail} | {header} |"
        )
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--owner", action="append", help="only this user or org (repeatable)")
    p.add_argument("--repo", action="append", help="scan only this OWNER/NAME (repeatable)")
    p.add_argument("--days", type=int, default=30, help="pushed within this many days (default 30)")
    p.add_argument("--json", action="store_true", help="print JSON instead of a markdown table")
    args = p.parse_args(argv)

    try:
        if args.repo:
            repos = []
            for name in args.repo:
                r = view_repo(name)
                if r.get("isFork") or r.get("isArchived"):
                    print(f"skipping {name}: fork or archived", file=sys.stderr)
                    continue
                repos.append(r)
        else:
            if args.owner:
                found = [r for o in args.owner for r in list_owner_repos(o)]
            else:
                found = list_accessible_repos()
            repos = recent_sources(found, args.days)
    except GhError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(inspect, repos))
    rows.sort(key=lambda r: r["pushed_at"], reverse=True)

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(render_table(rows) if rows else "No matching repositories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
