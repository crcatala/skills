#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10"]
# ///
"""Write a repository icon at a standard path and put it in the README title.

Usage:
  apply_icon.py --repo-dir DIR --source IMAGE [--size 512] [--no-readme]
                [--force] [--allow-shadowed]

Raster sources (PNG, WebP, JPEG) are trimmed to their visible content, centered
on a square transparent canvas and resized to --size, then written to
assets/icon.png. SVG sources are copied unchanged to assets/icon.svg. A faint
translucent backdrop, which image models sometimes paint behind a subject, is
removed automatically.

The README's title (its first heading) becomes
  <h1><img src="assets/icon.png" width="40" height="40" align="top" alt="" /> Title</h1>
unless it already shows an image. Only the first heading is ever changed.

Everything is checked before anything is written. It stops without writing
(exit code 1, "error" in the JSON) when:
  - assets/icon.* already exists (pass --force to replace it),
  - another icon would still be shown first, such as a t3.json iconPath or a
    favicon earlier in the lookup order ("shadowed_by"; pass --allow-shadowed),
  - the README cannot be read as UTF-8.

Prints a JSON summary.
"""

import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import icon_paths  # noqa: E402

HEADER_IMG = '<img src="{src}" width="40" height="40" align="top" alt="" />'
ATX_H1_RE = re.compile(r"^# +(.+?)\s*#*\s*$")
ANY_ATX_RE = re.compile(r"^#{1,6} ")
SETEXT_H1_RE = re.compile(r"^=+\s*$")
SETEXT_H2_RE = re.compile(r"^-+\s*$")
HTML_H1_OPEN_RE = re.compile(r"<h1\b[^>]*>", re.I)
HTML_HEADING_RE = re.compile(r"^\s*<h[1-6]\b", re.I)
# Markdown that would not render inside an HTML <h1>.
UNSAFE_TITLE_RE = re.compile(r"[`*_\[\]<>]|!\[")
FAINT_ALPHA_MAX = 40  # alpha 1..40 counts as "faint"
FAINT_SHARE_LIMIT = 0.10  # more than this share of faint pixels means a backdrop
HAZE_FLOOR = 60  # alpha at or below this is cleared when a backdrop is found
TITLE_SCAN_LINES = 40
HTML_H1_MAX_LINES = 15


def finalize_raster(src, dest, size):
    """Trim, square, resize. Returns notes about what was done."""
    from PIL import Image

    notes = []
    im = Image.open(src).convert("RGBA")
    alpha = im.getchannel("A")
    hist = alpha.histogram()
    total = im.width * im.height
    if hist[0] == total:
        raise ValueError(f"{src} is fully transparent")
    if hist[0] == 0 and hist[255] == total:
        notes.append("source has no transparency; the icon keeps its background")
    if sum(hist[1 : FAINT_ALPHA_MAX + 1]) / total > FAINT_SHARE_LIMIT:
        r, g, b, a = im.split()
        a = a.point(lambda v: 0 if v <= HAZE_FLOOR else v)
        im = Image.merge("RGBA", (r, g, b, a))
        notes.append("removed a faint translucent backdrop")

    # Trim to visible content, ignoring near-invisible haze at the edges.
    bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    side = max(int(max(w, h) * 1.04), 1)  # small even margin
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    canvas.resize((size, size), Image.LANCZOS).save(dest, optimize=True)
    return notes


def _titled(title, src):
    if UNSAFE_TITLE_RE.search(title):
        return None
    return f"<h1>{HEADER_IMG.format(src=src)} {title}</h1>"


def update_readme_text(text, src):
    """Return (new_text, status). Only the README's first heading is considered."""
    lines = text.split("\n")
    in_fence = False
    limit = min(len(lines), TITLE_SCAN_LINES)
    for i in range(limit):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip():
            continue

        # HTML <h1>, on one line or spread over several.
        if HTML_H1_OPEN_RE.match(line.lstrip()):
            end = next(
                (j for j in range(i, min(len(lines), i + HTML_H1_MAX_LINES)) if "</h1>" in lines[j].lower()),
                None,
            )
            if end is None:
                return text, "unchanged: <h1> title is not closed; edit by hand"
            block = "\n".join(lines[i : end + 1])
            if "<img" in block.lower():
                return text, "unchanged: title already shows an image"
            opening = HTML_H1_OPEN_RE.search(line)
            insert = HEADER_IMG.format(src=src) + (" " if end == i else "")
            lines[i] = line[: opening.end()] + insert + line[opening.end() :].lstrip()
            return "\n".join(lines), "updated"

        # Markdown "# Title".
        atx = ATX_H1_RE.match(line)
        if atx:
            new = _titled(atx.group(1).strip(), src)
            if new is None:
                return text, "unchanged: title has markdown that would not render inside <h1>; edit by hand"
            lines[i] = new
            return "\n".join(lines), "updated"

        # Setext "Title" underlined with "===".
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if SETEXT_H1_RE.match(nxt) and not ANY_ATX_RE.match(line):
            new = _titled(line.strip(), src)
            if new is None:
                return text, "unchanged: title has markdown that would not render inside <h1>; edit by hand"
            lines[i : i + 2] = [new]
            return "\n".join(lines), "updated"

        # Any other heading first means there is no title to decorate.
        if ANY_ATX_RE.match(line) or HTML_HEADING_RE.match(line) or SETEXT_H2_RE.match(nxt):
            return text, "unchanged: the first heading is not a top-level title"
    return text, "unchanged: no top-level title found"


def find_readme(repo_dir):
    for name in ("README.md", "readme.md", "Readme.md", "README.markdown"):
        if os.path.isfile(os.path.join(repo_dir, name)):
            return name
    return None


def repo_files(repo_dir):
    out = set()
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for f in files:
            out.add(os.path.relpath(os.path.join(root, f), repo_dir).replace(os.sep, "/"))
    return out


def read_text(repo_dir, rel):
    try:
        with open(os.path.join(repo_dir, rel), encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-dir", required=True)
    p.add_argument("--source", required=True, help="chosen image (PNG/WebP/JPEG/SVG)")
    p.add_argument("--size", type=int, default=512, help="raster output size in px (default 512)")
    p.add_argument("--no-readme", action="store_true", help="do not touch the README")
    p.add_argument("--force", action="store_true", help="overwrite an existing assets/icon.*")
    p.add_argument(
        "--allow-shadowed", action="store_true", help="write even if another icon would still be shown first"
    )
    args = p.parse_args(argv)

    repo_dir = os.path.abspath(args.repo_dir)
    is_svg = args.source.lower().endswith(".svg")
    rel = "assets/icon.svg" if is_svg else "assets/icon.png"
    dest = os.path.join(repo_dir, rel)
    summary = {"repo_dir": repo_dir, "icon": rel, "shadowed_by": [], "notes": []}

    def fail(message):
        summary["error"] = message
        print(json.dumps(summary, indent=2))
        return 1

    # --- Checks: nothing is written until all of them pass. ---
    if not os.path.isfile(args.source):
        return fail(f"source not found: {args.source}")

    existing = [p for p in ("assets/icon.svg", "assets/icon.png") if os.path.exists(os.path.join(repo_dir, p))]
    if existing and not args.force:
        return fail(f"{', '.join(existing)} already exists; pass --force to replace")

    files = repo_files(repo_dir) - set(existing)
    summary["shadowed_by"] = icon_paths.shadowing_paths(files, rel, lambda f: read_text(repo_dir, f))
    if summary["shadowed_by"] and not args.allow_shadowed:
        return fail(
            f"{', '.join(summary['shadowed_by'])} would still be shown instead of {rel}; "
            "remove or update it, or pass --allow-shadowed"
        )

    readme = None if args.no_readme else find_readme(repo_dir)
    new_readme = None
    if readme:
        text = read_text(repo_dir, readme)
        if text is None:
            return fail(f"{readme} could not be read as UTF-8; nothing was written")
        new_readme, status = update_readme_text(text, rel)
        summary["readme"] = f"{readme}: {status}"
        if new_readme == text:
            new_readme = None
    else:
        summary["readme"] = "skipped" if args.no_readme else "no README"

    # --- Write. ---
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        if is_svg:
            shutil.copyfile(args.source, dest)
        else:
            summary["notes"] += finalize_raster(args.source, dest, args.size)
    except (OSError, ValueError) as exc:
        return fail(str(exc))
    # The other format would be picked first (svg) or linger unused (png); remove it.
    for other in existing:
        if other != rel:
            os.remove(os.path.join(repo_dir, other))
            summary["notes"].append(f"removed {other}")
    if new_readme is not None:
        with open(os.path.join(repo_dir, readme), "w", encoding="utf-8") as fh:
            fh.write(new_readme)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
