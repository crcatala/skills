#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10"]
# ///
"""Animate a finished sprite with Retro Diffusion. Its output is true 1:1 pixel art, so nothing needs
cleaning up. Every run is a new take: regenerate until one looks right, then pick it.

    cd <sprite set>
    uv run {baseDir}/scripts/rd_anim.py <sprite.png> <name> "<motion prompt>" [--action walking] [--frames 8] [--dry-run]
    uv run {baseDir}/scripts/rd_anim.py --pick <name> <take number>
    uv run {baseDir}/scripts/rd_anim.py --mirror <name> <source name>

The sprite goes, unchanged, on a transparent square canvas (a multiple of 8 from 32 to 256px, feet
just above the bottom) as the start frame of rd_advanced_animation__<action> (walking, idle, jump,
crouch, attack, destroy, custom_action, subtle_motion). A free check_cost call prices it first.
Writes anim/<name>/take-NN/01.png... and take-NN/info.json (request, cost, time), and points
anim/<name>/pick at the new take. forge.py packs the picked take as the animation <name> and shows
every take on the review page. --mirror makes <name> the left-right mirror of another animation's
picked take, for free. Needs RETRO_DIFFUSION_API_KEY.
"""
import argparse, base64, io, json, math, os, pathlib, sys, time, urllib.error, urllib.request, uuid
from PIL import Image

WORK = os.getcwd()  # the sprite set
API = os.environ.get('RETRO_DIFFUSION_BASE_URL', 'https://api.retrodiffusion.ai/v2')
ACTIONS = ('walking', 'idle', 'jump', 'crouch', 'attack', 'destroy', 'custom_action', 'subtle_motion')
RETRY = ('inference_failed', 'provider_timeout', 'request_timeout')  # the API's own advice: retry once


def start_canvas(sprite):
    """The sprite cropped to its pixels, bottom-centred on the smallest square canvas the API accepts."""
    sprite = sprite.convert('RGBA')
    box = sprite.getbbox()
    if not box:
        sys.exit('the sprite is empty')
    s = sprite.crop(box)
    side = max(32, math.ceil((max(s.size) + 2) / 8) * 8)
    if side > 256:
        sys.exit(f'{s.width}x{s.height}px is too big for Retro Diffusion (256px at most); use video.py instead')
    c = Image.new('RGBA', (side, side))
    c.paste(s, ((side - s.width) // 2, side - s.height - max(1, (side - s.height) // 6)))
    return c


def split_sheet(sheet, side, n):
    """The first n cells, row by row, of a spritesheet made of side x side frames."""
    sheet = sheet.convert('RGBA')
    cols, rows = sheet.width // side, sheet.height // side
    cells = [sheet.crop((c * side, r * side, (c + 1) * side, (r + 1) * side)) for r in range(rows) for c in range(cols)]
    cells = [c for c in cells if c.getbbox()]
    if len(cells) < n:
        sys.exit(f'expected {n} frames, the sheet has {len(cells)}')
    return cells[:n]


def call(method, path, body=None, headers=None):
    h = {'X-RD-Token': os.environ.get('RETRO_DIFFUSION_API_KEY') or sys.exit('RETRO_DIFFUSION_API_KEY is not set'),
         'Content-Type': 'application/json', **(headers or {})}
    req = urllib.request.Request(API + path, method=method, headers=h, data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code}: {e.read().decode()[:1500]}')


def run(body):
    """Submit once (retried once on the failures the API says to retry) and return the finished result."""
    for attempt in (1, 2):
        task = call('POST', '/inferences', body, {'Idempotency-Key': str(uuid.uuid4())})['task_id']
        while True:
            time.sleep(4)
            t = call('GET', f'/inferences/tasks/{task}')
            if t.get('status') in ('succeeded', 'failed'):
                break
        if t['status'] == 'succeeded':
            return t['result']
        err = t.get('error') or {}
        print(f"attempt {attempt} failed (refunded): {err.get('code')} {err.get('message', '')}", file=sys.stderr)
        if err.get('code') not in RETRY:
            break
    sys.exit('generation failed' + (': the animation provider is busy, try again in a few minutes' if err.get('code') == 'provider_busy' else ''))


def frames_from(result, side, n):
    if result.get('base64_images'):
        raw = base64.b64decode(result['base64_images'][0])
    else:
        with urllib.request.urlopen(result['output_urls'][0], timeout=120) as r:
            raw = r.read()
    return split_sheet(Image.open(io.BytesIO(raw)), side, n)


def takes(name):
    d = os.path.join(WORK, 'anim', name)
    return sorted(t for t in os.listdir(d) if t.startswith('take-')) if os.path.isdir(d) else []


def set_pick(name, take):
    pathlib.Path(WORK, 'anim', name, 'pick').write_text(take + '\n')


def main():
    ap = argparse.ArgumentParser(description='Animate a sprite with Retro Diffusion; each run is a new take.')
    ap.add_argument('args', nargs='*', help='<sprite.png> <name> "<prompt>"')
    ap.add_argument('--action', default='walking', choices=ACTIONS)
    ap.add_argument('--frames', type=int, default=8, choices=(4, 6, 8, 10, 12, 16))
    ap.add_argument('--dry-run', action='store_true', help='print the price (free) and stop')
    ap.add_argument('--pick', nargs=2, metavar=('NAME', 'TAKE'), help='use take TAKE of animation NAME')
    ap.add_argument('--mirror', nargs=2, metavar=('NAME', 'SOURCE'), help='make NAME the mirror of SOURCE')
    a = ap.parse_args()

    if a.pick:
        name, n = a.pick
        take = f'take-{int(n):02d}'
        if take not in takes(name):
            sys.exit(f'{name} has no {take}; it has {", ".join(takes(name)) or "no takes"}')
        set_pick(name, take); print(f'{name}: picked {take}'); return
    if a.mirror:
        name, src = a.mirror
        if not takes(src):
            sys.exit(f'{src} has no takes to mirror')
        os.makedirs(os.path.join(WORK, 'anim', name), exist_ok=True)
        pathlib.Path(WORK, 'anim', name, 'mirror').write_text(src + '\n')
        print(f'{name}: mirror of {src} (follows its pick)'); return
    if len(a.args) != 3:
        ap.error('give <sprite.png> <name> "<prompt>", or --pick / --mirror')

    sprite, name, prompt = a.args
    start = start_canvas(Image.open(sprite))
    side = start.width
    buf = io.BytesIO(); start.save(buf, 'PNG')
    body = {'prompt': prompt, 'prompt_style': f'rd_advanced_animation__{a.action}', 'width': side, 'height': side,
            'num_images': 1, 'frames_duration': a.frames, 'input_image': base64.b64encode(buf.getvalue()).decode(),
            'return_spritesheet': True}
    price = call('POST', '/inferences', {**body, 'check_cost': True})['balance_cost']
    print(f'{body["prompt_style"]} at {side}x{side}, {a.frames} frames: ${price}', file=sys.stderr)
    if a.dry_run:
        return
    t0 = time.time()
    result = run(body)
    secs = round(time.time() - t0)
    frames = frames_from(result, side, a.frames)
    take = f'take-{max([int(t[5:]) for t in takes(name)] or [0]) + 1:02d}'
    d = os.path.join(WORK, 'anim', name, take)
    os.makedirs(d)
    for i, f in enumerate(frames):
        f.save(os.path.join(d, f'{i + 1:02d}.png'))
    info = {k: v for k, v in body.items() if k != 'input_image'} | {
        'sprite': sprite, 'cost_usd': result.get('balance_cost', price), 'remaining_usd': result.get('remaining_balance'), 'seconds': secs}
    pathlib.Path(d, 'info.json').write_text(json.dumps(info, indent=1))
    set_pick(name, take)
    print(f'{name}: {take}, {len(frames)} frames, ${info["cost_usd"]}, {secs}s (picked; rd_anim.py --pick {name} N to change)')


if __name__ == '__main__':
    main()
