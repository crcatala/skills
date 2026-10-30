#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy>=1.24", "pillow>=10"]
# ///
"""sprite-forge: turn AI-generated "pixel art" sheets into real, game-ready pixel sprites.

    cd <sprite set>; uv run {baseDir}/scripts/forge.py [recipes.json]

Reads raw/<recipe>.png (made by the image-gen skill from recipes.json), video/extracted/ (Grok walks)
and anim/ (true pixel-art frames from rd_anim.py, packed as they are) and writes out/:
  sprites/<recipe>/<name>.png   each sprite at 1x
  atlas.png + atlas.json        one packed sheet in PixiJS's spritesheet format, with animations
  report.json                   detected pixel size, scale and final size per sprite
  takes/                        every take of each anim/ animation, for the review page
  index.html                    review page: every sprite, the animations and their takes, the raw sheets, the recipes

Each sprite keeps the model's own pixel grid (found per sprite) and its own colours, cleaned up.
Resampling to a different size redraws pixel art badly, so the only resize is an exact 2x shrink,
and only when a recipe's "max" says the model drew something far too big.
"""
import json, sys, os, collections, glob, pathlib
import numpy as np
from PIL import Image

ALPHA_CUT = 160          # below this the model's soft glow/halo is dropped
HERE = os.path.dirname(os.path.abspath(__file__))  # scripts + review template
WORK = os.getcwd()                                  # the sprite set: recipes.json, raw/, video/, out/
RAW, OUT = os.path.join(WORK, 'raw'), os.path.join(WORK, 'out')


def load(path):
    a = np.array(Image.open(path).convert('RGBA'))
    return a[..., :3].astype(np.int32), a[..., 3] >= ALPHA_CUT


def components(mask):
    """4-connected components; returns a label image and sizes (no scipy needed)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    sizes = [0]
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        n = len(sizes); lab[y0, x0] = n; q = collections.deque([(y0, x0)]); s = 0
        while q:
            y, x = q.popleft(); s += 1
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = n; q.append((ny, nx))
        sizes.append(s)
    return lab, sizes


def find_sprites(mask, grid):
    """Split the sheet into its grid cells and keep each cell's real sprite (drop specks)."""
    cols, rows = grid
    h, w = mask.shape
    out = []
    for r in range(rows):
        for c in range(cols):
            y0, y1, x0, x1 = r * h // rows, (r + 1) * h // rows, c * w // cols, (c + 1) * w // cols
            cell = mask[y0:y1, x0:x1]
            lab, sizes = components(cell)
            if len(sizes) == 1:
                out.append(None); continue
            big = max(sizes[1:])
            keep = np.isin(lab, [i for i, s in enumerate(sizes) if i and s >= big * 0.02])
            ys, xs = np.nonzero(keep)
            out.append((y0 + ys.min(), y0 + ys.max() + 1, x0 + xs.min(), x0 + xs.max() + 1, keep[ys.min():ys.max() + 1, xs.min():xs.max() + 1]))
    return out


def pixel_period(rgb, mask):
    """Estimate the model's fake pixel size from the gaps between colour edges.

    Along rows and columns, find edges (big colour steps), merge the blurry 1-2px smear of each edge
    into one, and take the most common gap: most runs in pixel art are one art-pixel long."""
    gaps = []
    for arr, m in ((rgb, mask), (rgb.transpose(1, 0, 2), mask.T)):
        for line, ml in zip(arr[::2], m[::2]):
            d = np.abs(np.diff(line, axis=0)).sum(1) * (ml[1:] & ml[:-1])
            e = np.nonzero(d > 90)[0]
            if len(e) < 2:
                continue
            groups = np.split(e, np.nonzero(np.diff(e) > 2)[0] + 1)
            centres = np.array([g.mean() for g in groups])
            gaps.extend(np.diff(centres))
    gaps = np.array(gaps)
    gaps = gaps[(gaps >= 3) & (gaps <= 60)]
    if len(gaps) < 10:
        return 8.0
    hist = np.bincount(np.round(gaps).astype(int), minlength=62).astype(float)
    smooth = np.convolve(hist, [1, 2, 1], 'same')
    mode = int(smooth[3:].argmax()) + 3
    near = gaps[np.abs(gaps - mode) <= max(1.5, mode * 0.2)]
    return float(np.median(near))


def refine_grid(rgb, mask, p0, fixed=False):
    """Search pixel size and phase near the estimate for the grid whose lines sit on colour edges.
    Scores edge energy on the grid lines minus halfway between them, so a grid twice too fine loses.
    fixed: keep the size p0 and search only the phase."""
    dx = (np.abs(np.diff(rgb, axis=1)).sum(2) * (mask[:, 1:] & mask[:, :-1])).sum(0).astype(float)
    dy = (np.abs(np.diff(rgb, axis=0)).sum(2) * (mask[1:, :] & mask[:-1, :])).sum(1).astype(float)

    def fit(d, p):
        n, top = len(d), (-1e18, 0.0)
        for ph in np.arange(0, p, 0.25):
            lines = np.arange(ph, n, p)
            on = d[np.clip(np.round(lines).astype(int), 0, n - 1)].mean()
            off = d[np.clip(np.round(lines + p / 2).astype(int), 0, n - 1)].mean()
            top = max(top, (on - off, ph))
        return top
    best = None
    for p in [p0] if fixed else np.arange(p0 * 0.8, p0 * 1.25, 0.05):
        (sx, phx), (sy, phy) = fit(dx, p), fit(dy, p)
        if best is None or sx + sy > best[0]:
            best = (sx + sy, float(p), phx + 1, phy + 1)  # diff index i is the boundary before pixel i+1
    return best[1:]


def sample_native(rgb, mask, p, phx, phy):
    """One output pixel per model pixel: the median colour of the cell's centre (edges are blurry)."""
    h, w = mask.shape
    xs, ys = np.arange(phx - p, w, p), np.arange(phy - p, h, p)
    out = np.zeros((len(ys), len(xs), 4), np.uint8)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            m = mask[max(0, int(y)):int(np.ceil(y + p)), max(0, int(x)):int(np.ceil(x + p))]
            if m.size == 0 or m.mean() < 0.5:
                continue
            cy, cx = slice(max(0, int(y + p * .3)), int(y + p * .7) + 1), slice(max(0, int(x + p * .3)), int(x + p * .7) + 1)
            v = rgb[cy, cx][mask[cy, cx]]
            if len(v):
                out[j, i, :3] = np.median(v, axis=0); out[j, i, 3] = 255
    return out


def clean_colours(a, max_colours=24, merge=18):
    """Per-sprite colour clean-up: cap the colour count and merge the model's near-duplicate shades."""
    op = a[..., 3] > 0
    px = a[op][:, :3]
    if len(px) == 0:
        return a
    q = Image.fromarray(px.reshape(1, -1, 3)).quantize(min(max_colours, len(np.unique(px, axis=0))), method=Image.Quantize.MEDIANCUT)
    pal = np.array(q.getpalette()[:3 * 256]).reshape(-1, 3)
    idx = np.array(q).reshape(-1)
    used = np.unique(idx)
    rep = {}
    for c in sorted(used, key=lambda c: -np.sum(idx == c)):  # most common shade absorbs its neighbours
        for k in rep.values():
            if np.sum((pal[c] - pal[k]) ** 2) < merge ** 2:
                rep[c] = k; break
        else:
            rep[c] = c
    out = a.copy()
    out[op, :3] = pal[[rep[c] for c in idx]]
    return out


def shrink2(a):
    """Exact 2x reduction (only used when the model drew a sprite far too big): mode of each 2x2,
    ties to the darker colour so outlines survive."""
    h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
    out = np.zeros((h // 2, w // 2, 4), np.uint8)
    for j in range(h // 2):
        for i in range(w // 2):
            blk = a[2 * j:2 * j + 2, 2 * i:2 * i + 2].reshape(-1, 4)
            op = blk[blk[:, 3] > 0]
            if len(op) < 2:
                continue
            cols, counts = np.unique(op[:, :3], axis=0, return_counts=True)
            best = max(range(len(cols)), key=lambda k: (counts[k], -int(cols[k].sum())))
            out[j, i, :3] = cols[best]; out[j, i, 3] = 255
    return out


def tidy(a):
    """Drop orphan pixels (no opaque 4-neighbour) and crop to content."""
    op = a[..., 3] > 0
    pad = np.pad(op, 1)
    nb = pad[:-2, 1:-1].astype(int) + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
    a = a.copy(); a[op & (nb == 0)] = 0
    ys, xs = np.nonzero(a[..., 3] > 0)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else a


def bottom_align(frames):
    """Frames of one animation on a shared canvas (bottom-centred), trimmed to the union of their pixels."""
    w, h = max(f.shape[1] for f in frames), max(f.shape[0] for f in frames)
    out = []
    for f in frames:
        c = np.zeros((h, w, 4), np.uint8); ox = (w - f.shape[1]) // 2
        c[h - f.shape[0]:, ox:ox + f.shape[1]] = f; out.append(c)
    ys, xs = np.nonzero(np.any([f[..., 3] > 0 for f in out], axis=0))
    return [f[ys.min():ys.max() + 1, xs.min():xs.max() + 1] for f in out] if len(ys) else out


def load_anims(work):
    """Animations whose frames are already true pixel art, in anim/<name>/take-NN/*.png (rd_anim.py
    writes them; any tool's 1:1 frames work). No grid recovery: that would wreck 1px detail.
    Returns {name: {'pick', 'frames', 'takes': {take: frames}, 'info': {take: info}, 'mirror'}}."""
    root, out = os.path.join(work, 'anim'), {}
    read = lambda p: pathlib.Path(p).read_text().strip() if os.path.exists(p) else None
    for d in sorted(glob.glob(os.path.join(root, '*', ''))):
        name = os.path.basename(os.path.dirname(d))
        tk = {t: bottom_align([np.array(Image.open(f).convert('RGBA')) for f in sorted(glob.glob(os.path.join(d, t, '*.png')))])
              for t in sorted(os.listdir(d)) if glob.glob(os.path.join(d, t, '*.png'))}
        info = {t: json.loads(read(os.path.join(d, t, 'info.json')) or '{}') for t in tk}
        pick = read(os.path.join(d, 'pick'))
        pick = pick if pick in tk else (sorted(tk)[-1] if tk else None)
        out[name] = {'pick': pick, 'frames': tk.get(pick), 'takes': tk, 'info': info, 'mirror': read(os.path.join(d, 'mirror'))}
    for name, a in out.items():
        src = out.get(a['mirror']) if a['mirror'] else None
        if a['mirror'] and not (src and src['frames']):
            sys.exit(f"anim/{name}: mirror of '{a['mirror']}', which has no picked take")
        if src:
            a['frames'] = [f[:, ::-1].copy() for f in src['frames']]
    return {n: a for n, a in out.items() if a['frames']}


def main():
    recipes = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, 'recipes.json')))['recipes']
    recipes = [r for r in recipes if os.path.exists(os.path.join(RAW, r['id'] + '.png'))]
    os.makedirs(os.path.join(OUT, 'raw'), exist_ok=True)
    report, sprites = {}, {}  # key -> rgba array

    for r in recipes:
        rgb, mask = load(os.path.join(RAW, r['id'] + '.png'))
        found = list(zip(r['names'], find_sprites(mask, r['grid'])))
        est = {n: pixel_period(rgb[f[0]:f[1], f[2]:f[3]], f[4]) for n, f in found if f}
        sheet_p = float(np.median(list(est.values())))
        crop = lambda f: (rgb[f[0]:f[1], f[2]:f[3]], f[4])
        if r.get('pixel'):  # the recipe knows the size: keep it exactly
            grids = {n: refine_grid(*crop(f), r['pixel'], fixed=True) for n, f in found if f}
        else:
            grids = {n: refine_grid(*crop(f), est[n] if abs(est[n] / sheet_p - 1) < 0.4 else sheet_p) for n, f in found if f}
            if r['kind'] == 'character' and grids:
                # one character, one pixel size: per-view sizes drift (9.9-12.7px on four same-height
                # figures), which makes the views different heights. Use their median for every view.
                shared = float(np.median([g[0] for g in grids.values()]))
                grids = {n: refine_grid(*crop(f), shared, fixed=True) for n, f in found if f}
        for name, f in found:
            if f is None:
                continue
            y0, y1, x0, x1, keep = f
            p, phx, phy = grids[name]
            # sample at half the model's pixel size: its "pixels" are not on one consistent grid (eye
            # highlights half a pixel wide, one eye half a pixel off the other), and a full-size grid
            # has to drop or misplace those details. Mostly 2x2 blocks, with the odd half-pixel detail kept.
            a = clean_colours(sample_native(rgb[y0:y1, x0:x1], keep, p / 2, phx, phy))
            a = tidy(a)
            note = ''
            mx = r.get('max')  # [w, h] in px: shrink by exactly 2 while the model drew it far too big
            while mx and (a.shape[1] > mx[0] * 1.3 or a.shape[0] > mx[1] * 1.3):
                a = tidy(shrink2(a)); note = (note + ' ' if note else '') + 'shrunk 2x'
            sprites[f"{r['id']}/{name}"] = a
            report[f"{r['id']}/{name}"] = {'detected_pixel': round(p, 2), 'size': [int(a.shape[1]), int(a.shape[0])],
                                           'colours': int(len(np.unique(a[a[..., 3] > 0][:, :3], axis=0))), **({'fixed': note} if note else {})}
        for name, fix in (r.get('fix') or {}).items():
            if 'mirror' in fix:
                sprites[f"{r['id']}/{name}"] = sprites[f"{r['id']}/{fix['mirror']}"][:, ::-1].copy()
                report[f"{r['id']}/{name}"]['fixed'] = f"mirror of {fix['mirror']}"
        # characters: bottom-centre every frame in one fixed frame so animation does not jitter
        if r['kind'] == 'character':
            keys = [f"{r['id']}/{n}" for n in r['names'] if f"{r['id']}/{n}" in sprites]
            fw, fh = max(sprites[k].shape[1] for k in keys), max(sprites[k].shape[0] for k in keys)
            for k in keys:
                a = sprites[k]; fr = np.zeros((fh, fw, 4), np.uint8); ox = (fw - a.shape[1]) // 2
                fr[fh - a.shape[0]:, ox:ox + a.shape[1]] = a; sprites[k] = fr
        th = Image.open(os.path.join(RAW, r['id'] + '.png'))
        th.thumbnail((560, 560)); th.save(os.path.join(OUT, 'raw', r['id'] + '.png'))

    # animations pulled out of Grok videos by extract.py
    vids = sorted(glob.glob(os.path.join(WORK, 'video', 'extracted', '*', '01.png')))
    more_anims = {}
    for first in vids:
        name = os.path.basename(os.path.dirname(first))
        keys = []
        for f in sorted(glob.glob(os.path.join(os.path.dirname(first), '*.png'))):
            k = f"video-{name}/{os.path.splitext(os.path.basename(f))[0]}"
            sprites[k] = np.array(Image.open(f).convert('RGBA')); keys.append(k)
        more_anims[f'video-{name}'] = keys
        report[keys[0]] = {'detected_pixel': 0, 'size': list(sprites[keys[0]].shape[1::-1]), 'colours': 0,
                           'fixed': 'from Grok video: ' + json.dumps(json.load(open(os.path.join(os.path.dirname(first), 'info.json'))))}

    # animations already on a 1:1 grid (rd_anim.py): the picked take of each goes into the atlas
    native = load_anims(WORK)
    clash = set(native) & ({r['id'] for r in recipes} | set(more_anims))
    if clash:
        sys.exit(f"anim/ names clash with recipes or videos: {', '.join(sorted(clash))}")
    takes = {}
    for name, a in native.items():
        keys = [f'{name}/{i + 1:02d}' for i in range(len(a['frames']))]
        sprites.update(zip(keys, a['frames'])); more_anims[name] = keys
        cols = len(np.unique(np.concatenate([f[f[..., 3] > 0][:, :3] for f in a['frames']]), axis=0))
        report[keys[0]] = {'detected_pixel': 0, 'size': list(a['frames'][0].shape[1::-1]), 'colours': int(cols), 'fps': 8,
                           'fixed': f"mirror of {a['mirror']}" if a['mirror'] else f"native frames, {a['pick']} of {len(a['takes'])}"}
        takes[name] = {'pick': a['pick'], 'mirror': a['mirror'], 'takes': {}}
        for t, frs in a['takes'].items():
            d = os.path.join(OUT, 'takes', name, t); os.makedirs(d, exist_ok=True)
            for f in glob.glob(os.path.join(d, '*.png')):
                os.remove(f)
            paths = []
            for i, f in enumerate(frs):
                Image.fromarray(f).save(os.path.join(d, f'{i + 1:02d}.png')); paths.append(f'takes/{name}/{t}/{i + 1:02d}.png')
            inf = a['info'].get(t, {})
            takes[name]['takes'][t] = {'frames': paths, 'cost_usd': inf.get('cost_usd'), 'seconds': inf.get('seconds'), 'prompt': inf.get('prompt')}

    # write sprites + pack a simple shelf atlas
    frames, x, y, row_h, W = {}, 1, 1, 0, 512
    for k, a in sprites.items():
        os.makedirs(os.path.join(OUT, 'sprites', os.path.dirname(k)), exist_ok=True)
        Image.fromarray(a).save(os.path.join(OUT, 'sprites', k + '.png'))
        h, w = a.shape[:2]
        if x + w + 1 > W:
            x, y, row_h = 1, y + row_h + 1, 0
        frames[k] = (x, y, w, h); x += w + 1; row_h = max(row_h, h)
    H = y + row_h + 1
    atlas = np.zeros((H, W, 4), np.uint8)
    for k, (fx, fy, w, h) in frames.items():
        atlas[fy:fy + h, fx:fx + w] = sprites[k]
    Image.fromarray(atlas).save(os.path.join(OUT, 'atlas.png'))
    anims = {r['id']: [f"{r['id']}/{n}" for n in r['names'] if f"{r['id']}/{n}" in frames] for r in recipes if r['kind'] == 'character'} | more_anims
    sheet = {'frames': {k: {'frame': {'x': fx, 'y': fy, 'w': w, 'h': h}, 'sourceSize': {'w': w, 'h': h},
                            'spriteSourceSize': {'x': 0, 'y': 0, 'w': w, 'h': h}} for k, (fx, fy, w, h) in frames.items()},
             'animations': anims,
             'meta': {'image': 'atlas.png', 'size': {'w': W, 'h': H}, 'scale': '1', 'app': 'sprite-forge'}}
    json.dump(sheet, open(os.path.join(OUT, 'atlas.json'), 'w'), indent=1)
    json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
    write_review(recipes, sheet, report, takes)
    for k, v in report.items():
        print(f"{k:38s} pixel≈{v['detected_pixel']:>6}  -> {v['size'][0]}x{v['size'][1]}  {v['colours']} colours  {v.get('fixed', '')}")


def write_review(recipes, sheet, report, takes=None):
    tpl = open(os.path.join(HERE, 'review.html')).read()
    raw = '\n'.join(f'<figure><img src="raw/{r["id"]}.png" alt="{r["id"]} raw"><figcaption>{r["id"]}</figcaption></figure>' for r in recipes)
    data = json.dumps({'sheet': sheet, 'report': report, 'takes': takes or {},
                       'recipes': [{k: r[k] for k in ('id', 'kind', 'names', 'prompt') if k in r} | {'note': r.get('note')} for r in recipes]})
    open(os.path.join(OUT, 'index.html'), 'w').write(tpl.replace('<!--RAW-->', raw).replace('/*DATA*/null', data))


if __name__ == '__main__':
    main()
