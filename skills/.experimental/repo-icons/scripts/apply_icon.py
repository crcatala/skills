#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10"]
# ///
"""Write a repository icon at a standard path and put it in the README title.

Usage:
  apply_icon.py --repo-dir DIR --source IMAGE [--size 512] [--no-readme] [--force]

Raster sources (PNG, WebP, JPEG) are trimmed to their visible content, centered
on a square transparent canvas and resized to --size, then written to
assets/icon.png. SVG sources are copied unchanged to assets/icon.svg. A faint
translucent backdrop, which image models sometimes paint behind a subject, is
removed automatically.

The README's first heading becomes
  <h1><img src="assets/icon.png" width="40" height="40" align="top" alt="" /> Title</h1>
unless it already shows an image.

Prints a JSON summary. Exit code 1 means nothing was written.
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
HTML_H1_RE = re.compile(r"^(\s*<h1\b[^>]*>)(.*?)(</h1>\s*)$", re.I)
# Markdown that would not render inside an HTML <h1>.
UNSAFE_TITLE_RE = re.compile(r"[`*_\[\]<>]|!\[")
FAINT_ALPHA_MAX = 40  # alpha 1..40 counts as "faint"
FAINT_SHARE_LIMIT = 0.10  # more than this share of faint pixels means a backdrop
HAZE_FLOOR = 60  # alpha at or below this is cleared when a backdrop is found


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


def update_readme_text(text, src):
    """Return (new_text, status). status explains what happened."""
    lines = text.split("\n")
    in_fence = False
    for i, line in enumerate(lines[:40]):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        html = HTML_H1_RE.match(line)
        if html:
            if "<img" in html.group(2).lower():
                return text, "unchanged: title already shows an image"
            lines[i] = f"{html.group(1)}{HEADER_IMG.format(src=src)} {html.group(2).strip()}{html.group(3)}"
            return "\n".join(lines), "updated"
        atx = ATX_H1_RE.match(line)
        if atx:
            title = atx.group(1).strip()
            if UNSAFE_TITLE_RE.search(title):
                return text, "unchanged: title has markdown that would not render inside <h1>; edit by hand"
            lines[i] = f"<h1>{HEADER_IMG.format(src=src)} {title}</h1>"
            return "\n".join(lines), "updated"
        if line.startswith("## "):
            break
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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-dir", required=True)
    p.add_argument("--source", required=True, help="chosen image (PNG/WebP/JPEG/SVG)")
    p.add_argument("--size", type=int, default=512, help="raster output size in px (default 512)")
    p.add_argument("--no-readme", action="store_true", help="do not touch the README")
    p.add_argument("--force", action="store_true", help="overwrite an existing assets/icon.*")
    args = p.parse_args(argv)

    repo_dir = os.path.abspath(args.repo_dir)
    is_svg = args.source.lower().endswith(".svg")
    rel = "assets/icon.svg" if is_svg else "assets/icon.png"
    dest = os.path.join(repo_dir, rel)
    summary = {"repo_dir": repo_dir, "icon": rel, "notes": []}

    existing = [p for p in ("assets/icon.svg", "assets/icon.png") if os.path.exists(os.path.join(repo_dir, p))]
    if existing and not args.force:
        summary["error"] = f"{', '.join(existing)} already exists; pass --force to replace"
        print(json.dumps(summary, indent=2))
        return 1

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        if is_svg:
            shutil.copyfile(args.source, dest)
        else:
            summary["notes"] += finalize_raster(args.source, dest, args.size)
    except (OSError, ValueError) as exc:
        summary["error"] = str(exc)
        print(json.dumps(summary, indent=2))
        return 1
    # An icon of the other format would sit earlier or later in the lookup order; remove it.
    for other in existing:
        if other != rel:
            os.remove(os.path.join(repo_dir, other))
            summary["notes"].append(f"removed {other}")

    shadows = icon_paths.shadowing_paths(repo_files(repo_dir), rel)
    if shadows:
        summary["notes"].append(
            f"{', '.join(shadows)} is checked before {rel}, so tools like T3 Code will keep showing it"
        )

    readme = None if args.no_readme else find_readme(repo_dir)
    if readme:
        path = os.path.join(repo_dir, readme)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new_text, status = update_readme_text(text, rel)
        if new_text != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)
        summary["readme"] = f"{readme}: {status}"
    else:
        summary["readme"] = "skipped" if args.no_readme else "no README"

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
