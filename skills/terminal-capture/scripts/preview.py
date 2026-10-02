#!/usr/bin/env python3
"""Rasterize an animated SVG at a chosen moment, to check it by eye.

A CSS-animated SVG has no single "image", so this inlines it in a page, pauses
every animation at --at seconds, and screenshots it with a headless Chromium/Chrome.

  preview.py demo.svg --at 3.5 --out /tmp/demo-3.5s.png [--width 1200 --height 800]

Notes:
  * theme "auto" SVGs render in light mode; render with --theme dark to check dark.
  * Needs chromium, chromium-browser, google-chrome or google-chrome-stable on PATH.
  * If the browser refuses to start because its sandbox is unavailable, you can set
    PREVIEW_NO_SANDBOX=1 for this local, trusted-file preview only.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def main(argv=None):
    p = argparse.ArgumentParser(description="Screenshot an animated SVG at a given time.")
    p.add_argument("svg")
    p.add_argument("--at", type=float, default=0.0, help="seconds into the animation")
    p.add_argument("--out", required=True, help="output .png")
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--height", type=int, default=800)
    a = p.parse_args(argv)

    browser = next((b for b in map(shutil.which, BROWSERS) if b), None)
    if not browser:
        print("preview: no headless Chromium/Chrome found on PATH", file=sys.stderr)
        return 1
    with open(a.svg, encoding="utf-8") as f:
        svg = f.read()
    page = (
        '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#808080">'
        + svg
        + "<script>addEventListener('load',function(){document.getAnimations({subtree:true})"
        f".forEach(function(x){{x.pause();x.currentTime={a.at * 1000}}})}})</script>"
    )
    with tempfile.TemporaryDirectory(prefix="terminal-capture-preview-") as tmp:
        html_path = os.path.join(tmp, "page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page)
        cmd = [browser, "--headless", "--disable-gpu", "--hide-scrollbars",
               f"--window-size={a.width},{a.height}", "--virtual-time-budget=1500",
               f"--screenshot={os.path.abspath(a.out)}", "file://" + html_path]
        if os.environ.get("PREVIEW_NO_SANDBOX") == "1":
            cmd.insert(2, "--no-sandbox")
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(a.out):
        print("preview: browser failed:\n" + r.stderr[-800:], file=sys.stderr)
        return 1
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
