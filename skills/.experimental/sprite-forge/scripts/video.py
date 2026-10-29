#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10"]
# ///
"""Animate a sprite with Grok Imagine Video, looping by pinning the first and last frame to the same image.

    cd <sprite set>; uv run {baseDir}/scripts/video.py <sprite.png> <out-name> "<motion prompt>" [--seconds 4] [--model grok-imagine-video-1.5] [--scale 12]

The sprite is scaled up by an exact integer (default 6: forge's sprites are on a half-pixel grid) onto a flat chroma-green 16:9 canvas (Grok cannot output
transparency), so the clean-up step knows the pixel grid: it is --scale. Saves video/<out-name>.mp4 and
video/<out-name>.json (request + response, for cost). Needs XAI_API_KEY.
"""
import argparse, base64, io, json, os, sys, time, urllib.request
from PIL import Image

WORK = os.getcwd()  # the sprite set
API = os.environ.get('XAI_BASE_URL', 'https://api.x.ai/v1')
GREEN = (0, 177, 64)


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={'Authorization': f"Bearer {os.environ['XAI_API_KEY']}", 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code}: {e.read().decode()[:2000]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sprite'); ap.add_argument('name'); ap.add_argument('prompt')
    ap.add_argument('--seconds', type=int, default=4); ap.add_argument('--model', default='grok-imagine-video-1.5')
    ap.add_argument('--scale', type=int, default=6); ap.add_argument('--resolution', default='480p')
    a = ap.parse_args()
    spr = Image.open(a.sprite).convert('RGBA')
    big = spr.resize((spr.width * a.scale, spr.height * a.scale), Image.NEAREST)
    W, H = 960, 540
    canvas = Image.new('RGBA', (W, H), GREEN + (255,))
    canvas.alpha_composite(big, ((W - big.width) // 2, (H - big.height) // 2))
    os.makedirs(os.path.join(WORK, 'video'), exist_ok=True)
    first = os.path.join(WORK, 'video', a.name + '-first.png'); canvas.convert('RGB').save(first)
    buf = io.BytesIO(); canvas.convert('RGB').save(buf, 'PNG')
    uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    body = {'model': a.model, 'prompt': a.prompt, 'image': {'url': uri}, 'last_frame': {'url': uri},
            'duration': a.seconds, 'resolution': a.resolution}
    start = call('POST', f'{API}/videos/generations', body)
    rid = start.get('request_id') or sys.exit(f'no request id: {start}')
    print('request', rid, file=sys.stderr)
    while True:
        time.sleep(6)
        res = call('GET', f'{API}/videos/{rid}')
        st = res.get('status')
        if st == 'done':
            break
        if st in ('failed', 'expired'):
            sys.exit(f'{st}: {json.dumps(res)[:1500]}')
    url = res['video']['url']
    out = os.path.join(WORK, 'video', a.name + '.mp4')
    urllib.request.urlretrieve(url, out)
    meta = {k: v for k, v in body.items() if k not in ('image', 'last_frame')} | {'scale': a.scale, 'sprite': a.sprite, 'response': res}
    json.dump(meta, open(os.path.join(WORK, 'video', a.name + '.json'), 'w'), indent=1)
    print(out)


if __name__ == '__main__':
    main()
