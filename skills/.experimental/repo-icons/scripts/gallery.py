#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10"]
# ///
"""Build a self-contained HTML page for picking one icon per repository.

Usage:
  gallery.py MANIFEST.json [-o gallery.html]

MANIFEST.json:
  {
    "title": "Repo icon concepts",                        (optional)
    "repos": [
      {
        "repo": "owner/name",
        "description": "one line",                        (optional)
        "current": "/abs/path/current-icon.svg",          (optional: offers "keep")
        "current_label": "assets/logo.svg",               (optional)
        "candidates": [
          {"id": "pixel-16bit", "label": "Stim injector", "style": "16-bit pixel item",
           "file": "/abs/path/name-pixel-16bit.png"}
        ]
      }
    ]
  }

Images are embedded (downscaled), so the page works offline and can be opened
from anywhere. Each repo gets a radio group (candidates, keep current, redo,
skip) and a note field. "Copy picks" copies lines such as

  repo-icons picks
  owner/name: pixel-16bit
  owner/other: redo | note: warmer colors, no robot

which the user pastes back to the agent.
"""

import argparse
import base64
import html
import io
import json
import os
import sys

THUMB = 256
SMALL = 32


def data_uri(path, size):
    """Downscaled data: URI for a raster image, or the file itself for SVG."""
    if path.lower().endswith(".svg"):
        with open(path, "rb") as fh:
            return "data:image/svg+xml;base64," + base64.b64encode(fh.read()).decode()
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    buf = io.BytesIO()
    canvas.resize((size, size), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def tile(repo_key, value, title, subtitle, path, symbol=""):
    e = html.escape
    big = data_uri(path, THUMB) if path else None
    small = data_uri(path, SMALL) if path else None
    preview = (
        f'<div class="big"><img src="{big}" alt=""></div>'
        f'<div class="small"><span class="sw lt"><img src="{small}" width="16" height="16" alt=""></span>'
        f'<span class="sw dk"><img src="{small}" width="16" height="16" alt=""></span>'
        f'<span class="sw dk"><img src="{small}" width="32" height="32" alt=""></span></div>'
        if path
        else f'<div class="big empty">{e(symbol)}</div>'
    )
    return (
        f'<label class="tile"><input type="radio" name="{e(repo_key)}" value="{e(value)}">'
        f'{preview}<div class="cap"><b>{e(title)}</b><span>{e(subtitle)}</span></div></label>'
    )


def build(manifest):
    e = html.escape
    sections = []
    for r in manifest["repos"]:
        key = r["repo"]
        tiles = [
            tile(key, c["id"], c.get("label") or c["id"], c.get("style", ""), c["file"])
            for c in r.get("candidates", [])
        ]
        if r.get("current"):
            tiles.append(tile(key, "keep", "Keep current", r.get("current_label", ""), r["current"]))
        tiles.append(tile(key, "redo", "Redo", "new ideas (add a note)", None, "↻"))
        tiles.append(tile(key, "skip", "Skip", "leave this repo alone", None, "—"))
        sections.append(
            f'<section data-repo="{e(key)}"><h2>{e(key)}</h2>'
            f'<p>{e(r.get("description", ""))}</p><div class="row">{"".join(tiles)}</div>'
            f'<input class="note" type="text" placeholder="Note (optional): e.g. warmer colors, smaller outline"></section>'
        )
    title = e(manifest.get("title", "Repo icon concepts"))
    return PAGE.replace("{{TITLE}}", title).replace("{{SECTIONS}}", "\n".join(sections))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title>
<style>
:root{color-scheme:light dark;--fg:#18181b;--muted:#71717a;--card:#fff;--line:#e4e4e7;--accent:#6366f1;--bg:#fafafa}
@media (prefers-color-scheme:dark){:root{--fg:#f4f4f5;--muted:#a1a1aa;--card:#18181b;--line:#3f3f46;--bg:#09090b}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 120px}
h1{font-size:20px;margin:0 0 4px} h2{font:600 15px ui-monospace,monospace;margin:0}
.intro,p{color:var(--muted);margin:2px 0 10px;font-size:13px}
section{margin:0 0 28px}
.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.tile{position:relative;border:2px solid var(--line);border-radius:10px;padding:8px;background:var(--card);cursor:pointer}
.tile input{position:absolute;opacity:0}
.tile:has(input:checked){border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 25%,transparent)}
.big{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:6px}
body.bg-checker .big{background:repeating-conic-gradient(#8882 0 25%,#0000 0 50%) 0 0/16px 16px}
body.bg-light .big{background:#f4f4f5} body.bg-dark .big{background:#18181b}
.big img{width:84%;height:84%;object-fit:contain}
.big.empty{color:var(--muted);font-size:40px;border:1px dashed var(--line)}
.small{display:flex;gap:6px;margin:8px 0 4px;align-items:center}
.sw{display:inline-flex;padding:4px;border-radius:5px}.lt{background:#f4f4f5}.dk{background:#18181b}
.cap b{display:block;font-size:13px}.cap span{color:var(--muted);font-size:12px}
.note{width:100%;box-sizing:border-box;margin-top:8px;padding:7px 9px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px}
.bar .in{max-width:1100px;margin:0 auto;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
#status{color:var(--muted);font-size:13px}
textarea{width:100%;box-sizing:border-box;height:120px;margin-top:8px;font:12px ui-monospace,monospace;display:none;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px}
</style></head>
<body class="bg-checker"><main>
<h1>{{TITLE}}</h1>
<div class="intro">Pick one option per repo. Each tile shows the icon full size, then at 16px on light, 16px on dark and 32px on dark, roughly how app sidebars show it. Use “Redo” with a note to get new ideas, then press “Copy picks” and paste the result back to the agent.</div>
{{SECTIONS}}
</main>
<div class="bar"><div class="in">
<button class="primary" id="copy">Copy picks</button>
<button data-bg="checker">Checker</button><button data-bg="light">Light</button><button data-bg="dark">Dark</button>
<span id="status"></span>
<textarea id="out" readonly></textarea>
</div></div>
<script>
const sections=[...document.querySelectorAll("section[data-repo]")];
function picks(){
  const lines=["repo-icons picks"];let open=0;
  for(const s of sections){
    const repo=s.dataset.repo;const c=s.querySelector("input[type=radio]:checked");
    const note=s.querySelector(".note").value.trim();
    if(!c){ if(note){lines.push(`${repo}: undecided | note: ${note}`);} else {open++;} continue; }
    lines.push(`${repo}: ${c.value}`+(note?` | note: ${note}`:""));
  }
  return {text:lines.join("\\n"),open};
}
function update(){const {open}=picks();document.getElementById("status").textContent=open?`${open} repo(s) without a pick (left out)`:"All repos picked";}
document.addEventListener("change",update);document.addEventListener("input",update);update();
document.getElementById("copy").addEventListener("click",async()=>{
  const {text}=picks();const out=document.getElementById("out");out.value=text;
  try{await navigator.clipboard.writeText(text);document.getElementById("status").textContent="Copied. Paste it to the agent.";}
  catch(_){out.style.display="block";out.select();document.getElementById("status").textContent="Clipboard blocked here: copy the text below.";}
});
document.querySelectorAll("[data-bg]").forEach(b=>b.addEventListener("click",()=>{document.body.className="bg-"+b.dataset.bg;}));
</script>
</body></html>
"""


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("manifest")
    p.add_argument("-o", "--output", help="output HTML path (default: gallery.html next to the manifest)")
    args = p.parse_args(argv)
    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    out = args.output or os.path.join(os.path.dirname(os.path.abspath(args.manifest)), "gallery.html")
    page = build(manifest)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(json.dumps({"output": os.path.abspath(out), "bytes": len(page)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
