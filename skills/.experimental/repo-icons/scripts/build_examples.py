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
                                            references/examples/ and write index.html

`prompts` needs only the standard library. After changing a template, generate
its images again (square, transparent, at least 1024 px), then run `build`.
"""

import argparse
import html
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


def render_html(styles, apps, available):
    e = html.escape
    cards = []
    for s in styles:
        figures = []
        for a in apps:
            name = f"{a['id']}-{s['id']}.webp"
            img = (
                f'<img src="{e(name)}" alt="{e(a["name"])}, {e(s["name"])}" loading="lazy">'
                if name in available
                else '<span class="missing">not generated</span>'
            )
            figures.append(f'<figure><div class="img">{img}</div><figcaption>{e(a["name"])}</figcaption></figure>')
        cards.append(
            f'<section class="card" id="{e(s["id"])}"><header><h2>{e(s["name"])}</h2><code>{e(s["id"])}</code>'
            f'<p>{e(s["look"])}</p></header><div class="grid">{"".join(figures)}</div>'
            f'<details><summary>Prompt template</summary><p>{e(s["template"])}</p></details></section>'
        )
    apps_list = "".join(
        f'<li><b>{e(a["name"])}</b> <span>{e(a["industry"])}: {e(a["description"])}</span>'
        f'<span class="subject">Subject: {e(a["subject"])}</span></li>'
        for a in apps
    )
    return PAGE.replace("{{APPS}}", apps_list).replace("{{CARDS}}", "\n".join(cards))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>repo-icons: style examples</title>
<style>
:root{color-scheme:light dark;--fg:#18181b;--muted:#71717a;--card:#fff;--line:#e4e4e7;--bg:#fafafa;--code:#f4f4f5}
@media (prefers-color-scheme:dark){:root{--fg:#f4f4f5;--muted:#a1a1aa;--card:#18181b;--line:#3f3f46;--bg:#09090b;--code:#27272a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,sans-serif}
main{max-width:860px;margin:0 auto;padding:20px 14px 40px}
h1{font-size:22px;margin:0 0 6px}.intro{color:var(--muted);margin:0 0 12px}
.apps{list-style:none;margin:0 0 14px;padding:0;display:grid;gap:8px}
.apps li{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.apps span{display:block;color:var(--muted);font-size:13px}.apps .subject{font-style:italic}
.bg{position:sticky;top:0;z-index:1;display:flex;gap:6px;padding:8px 0;margin:0 0 6px;background:var(--bg)}
.bg button{font:inherit;font-size:14px;padding:6px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:0 0 14px}
.card header{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;margin:0 0 10px}
.card h2{font-size:17px;margin:0}.card code{font-size:12px;color:var(--muted)}
.card header p{flex-basis:100%;margin:0;color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
figure{margin:0}figcaption{text-align:center;font-size:12px;color:var(--muted);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.img{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:10px;border:1px solid var(--line)}
body.bg-checker .img{background:repeating-conic-gradient(#8882 0 25%,#0000 0 50%) 0 0/14px 14px}
body.bg-light .img{background:#f4f4f5}body.bg-dark .img{background:#18181b}
.img img{width:86%;height:86%;object-fit:contain}.missing{color:var(--muted);font-size:12px}
details{margin-top:12px;font-size:13px}summary{cursor:pointer;color:var(--muted)}
details p{margin:8px 0 0;padding:10px 12px;background:var(--code);border-radius:8px;font:12.5px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
@media (max-width:480px){main{padding:14px 10px 32px}.grid{gap:6px}.card{padding:12px}}
</style></head>
<body class="bg-checker"><main>
<h1>Style examples</h1>
<p class="intro">Each card is one template from <code>styles.md</code>, filled with the same subject for three hypothetical apps. Results vary between runs; these show the general look.</p>
<ul class="apps">{{APPS}}</ul>
<div class="bg"><button data-bg="checker">Checker</button><button data-bg="light">Light</button><button data-bg="dark">Dark</button></div>
{{CARDS}}
</main>
<script>document.querySelectorAll("[data-bg]").forEach(b=>b.addEventListener("click",()=>{document.body.className="bg-"+b.dataset.bg;}));</script>
</body></html>
"""


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompts", help="print the prompts to generate, as JSON")
    b = sub.add_parser("build", help="thumbnail generated images and write index.html")
    b.add_argument("--images", help="directory with <app>-<style>.png; omit to only rewrite index.html")
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
    with open(os.path.join(EXAMPLES_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render_html(styles, apps, available))
    print(json.dumps({"thumbnails": made, "available": len(available), "expected": len(styles) * len(apps)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
