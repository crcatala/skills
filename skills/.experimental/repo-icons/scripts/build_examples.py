#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10"]
# ///
"""Build the style example sheet in references/examples/.

The examples show what each template in references/styles.md produces, using
the hypothetical apps in references/examples/apps.json. Prompts are filled
from styles.md verbatim, so the examples always match the templates.

Usage:
  build_examples.py prompts                 print the prompts to generate, as JSON
  build_examples.py build --images DIR      thumbnail DIR/<app>-<style>.png into
                                            references/examples/ and write README.md

`prompts` needs only the standard library. After changing a template, generate
its images again (square, transparent, at least 1024 px), then run `build`.
"""

import argparse
import json
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLES_MD = os.path.join(SKILL_DIR, "references", "styles.md")
EXAMPLES_DIR = os.path.join(SKILL_DIR, "references", "examples")
APPS_JSON = os.path.join(EXAMPLES_DIR, "apps.json")
THUMB = 256

MENU_ROW_RE = re.compile(r"^\| `([a-z0-9-]+)` \| ([^|]+?) \| ([^|]+?) \|$", re.M)
TEMPLATE_RE = re.compile(r"^### `([a-z0-9-]+)`\n```\n(.+?)\n```", re.M | re.S)


def load_styles(path=STYLES_MD):
    """[{id, name, look, template}] in menu order."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    templates = dict(TEMPLATE_RE.findall(text))
    styles = []
    for style_id, name, look in MENU_ROW_RE.findall(text):
        if style_id not in templates:
            raise ValueError(f"style {style_id} has no template in {path}")
        styles.append({"id": style_id, "name": name.strip(), "look": look.strip(), "template": templates[style_id]})
    missing = set(templates) - {s["id"] for s in styles}
    if missing:
        raise ValueError(f"templates without a menu row: {', '.join(sorted(missing))}")
    return styles


def load_apps(path=APPS_JSON):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["apps"]


def prompts(styles, apps):
    return [
        {
            "app": a["id"],
            "style": s["id"],
            "file": f"{a['id']}-{s['id']}.png",
            "prompt": s["template"].replace("{subject}", a["subject"]),
        }
        for a in apps
        for s in styles
    ]


def thumbnail(src, dest):
    from PIL import Image

    im = Image.open(src).convert("RGBA")
    bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    side = int(max(w, h) * 1.04)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    canvas.resize((THUMB, THUMB), Image.LANCZOS).save(dest, "WEBP", quality=88, method=6)


def render_markdown(styles, apps, available):
    """README.md for references/examples/: GitHub renders it, images inline."""
    lines = [
        "# Style examples",
        "",
        "Each section is one template from [`styles.md`](../styles.md), filled with the same",
        "subject for three hypothetical apps. Results vary between runs; these show the general look.",
        "",
    ]
    for a in apps:
        lines.append(f"- **{a['name']}** ({a['industry']}: {a['description']}). Subject: _{a['subject']}_")
    lines += ["", "| Style | " + " | ".join(a["name"] for a in apps) + " |", "|---|" + ":-:|" * len(apps)]
    for s in styles:
        lines.append(f"| [{s['name']}](#{s['id']}) | " + " | ".join(
            _img(f"{a['id']}-{s['id']}.webp", f"{a['name']}, {s['name']}", 72, available) for a in apps
        ) + " |")
    for s in styles:
        lines += [
            "",
            f'<a id="{s["id"]}"></a>',
            "",
            f"## {s['name']} (`{s['id']}`)",
            "",
            s["look"],
            "",
            "| " + " | ".join(a["name"] for a in apps) + " |",
            "|" + ":-:|" * len(apps),
            "| " + " | ".join(
                _img(f"{a['id']}-{s['id']}.webp", f"{a['name']}, {s['name']}", 200, available) for a in apps
            ) + " |",
            "",
            "<details><summary>Prompt template</summary>",
            "",
            "```text",
            s["template"],
            "```",
            "",
            "</details>",
        ]
    lines += ["", "Regenerate with `scripts/build_examples.py` after changing a template.", ""]
    return "\n".join(lines)


def _img(name, alt, width, available):
    if name not in available:
        return "_not generated_"
    return f'<img src="{name}" width="{width}" alt="{alt}">'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompts", help="print the prompts to generate, as JSON")
    b = sub.add_parser("build", help="thumbnail generated images and write README.md")
    b.add_argument("--images", help="directory with <app>-<style>.png; omit to only rewrite README.md")
    args = p.parse_args(argv)

    styles, apps = load_styles(), load_apps()
    if args.cmd == "prompts":
        print(json.dumps(prompts(styles, apps), indent=2))
        return 0

    made = 0
    if args.images:
        for item in prompts(styles, apps):
            src = os.path.join(args.images, item["file"])
            if os.path.exists(src):
                thumbnail(src, os.path.join(EXAMPLES_DIR, item["file"][: -len(".png")] + ".webp"))
                made += 1
    available = {f for f in os.listdir(EXAMPLES_DIR) if f.endswith(".webp")}
    with open(os.path.join(EXAMPLES_DIR, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(render_markdown(styles, apps, available))
    print(json.dumps({"thumbnails": made, "available": len(available), "expected": len(styles) * len(apps)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
