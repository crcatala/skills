#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy>=1.24", "pillow>=10"]
# ///
"""Turn a Grok walk-cycle video (from video.py) into a short pixel-art animation.

    cd <sprite set>; uv run {baseDir}/scripts/extract.py <name> [--frames 8] [--lock 0.45]

For every video frame: key out the chroma green, recover the pixel grid (known from video.py's
--scale), and snap colours to the original sprite's own colours so the video's drift cannot flicker.
Then find the walk cycle's period from how similar frames are, and take evenly spaced frames from one
cycle in the middle of the clip (the pinned first/last frames ease in and out). Writes
video/extracted/<name>/NN.png, which forge.py adds to the atlas as an animation.
"""
import argparse, glob, json, os, subprocess
import numpy as np
from PIL import Image
import forge

WORK = os.getcwd()  # the sprite set


def key_green(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return ~((g > 120) & (g > r * 1.6) & (g > b * 1.6))


def snap_to(a, pal):
    op = a[..., 3] > 0
    px = a[op][:, :3].astype(int)
    d = ((px[:, None, :] - pal[None]) ** 2 * [2, 4, 3]).sum(2)
    out = a.copy(); out[op, :3] = pal[d.argmin(1)]
    return out


def pad_to(a, w, h):
    fr = np.zeros((h, w, 4), np.uint8); ox = (w - a.shape[1]) // 2
    fr[h - a.shape[0]:, ox:ox + a.shape[1]] = a[:h, :w]
    return fr


def lock_head(fr, src, frac):
    """Video models redraw the face slightly differently every frame (eyes come and go). Find where the
    original sprite's head sits in this frame and paste it, so only the body and limbs come from video."""
    ys, xs = np.nonzero(src[..., 3] > 0)
    src = src[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    hh = max(1, int(src.shape[0] * frac))
    head = src[:hh]
    fys, fxs = np.nonzero(fr[..., 3] > 0)
    top, cx = fys.min(), (fxs.min() + fxs.max()) // 2
    best = None
    for dy in range(-3, 4):
        for dx in range(-6, 7):
            y0, x0 = top + dy, cx - head.shape[1] // 2 + dx
            if y0 < 0 or x0 < 0 or y0 + hh > fr.shape[0] or x0 + head.shape[1] > fr.shape[1]:
                continue
            win = fr[y0:y0 + hh, x0:x0 + head.shape[1]]
            m = head[..., 3] > 0
            score = (np.abs(win[m][:, :3].astype(int) - head[m][:, :3]).sum(1) > 30).mean() + (win[..., 3] > 0)[~m].mean() * 0.5
            if best is None or score < best[0]:
                best = (score, y0, x0)
    if best is None:
        return fr
    _, y0, x0 = best
    out = fr.copy()
    out[y0:y0 + hh, max(0, x0 - 2):x0 + head.shape[1] + 2] = 0  # clear the video's head (a margin for stray hair)
    reg = out[y0:y0 + hh, x0:x0 + head.shape[1]]
    m = head[..., 3] > 0
    reg[m] = head[m]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('--frames', type=int, default=8)
    ap.add_argument('--lock', type=float, default=0, help='paste the top fraction of the original sprite (its head) onto every frame')
    a = ap.parse_args()
    meta = json.load(open(os.path.join(WORK, 'video', a.name + '.json')))
    src = np.array(Image.open(os.path.join(WORK, meta['sprite'])).convert('RGBA'))
    pal = np.unique(src[src[..., 3] > 0][:, :3], axis=0).astype(int)
    fdir = os.path.join(WORK, 'video', 'frames', a.name)
    if not glob.glob(os.path.join(fdir, '*.png')):
        os.makedirs(fdir, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(WORK, 'video', a.name + '.mp4'), os.path.join(fdir, '%03d.png')], check=True)
    files = sorted(glob.glob(os.path.join(fdir, '*.png')))
    first = np.array(Image.open(files[0]).convert('RGB')).astype(np.int32)
    grid = meta['scale'] * first.shape[1] / 960  # video.py draws on a 960px-wide canvas
    sprites = []
    for f in files:
        rgb = np.array(Image.open(f).convert('RGB')).astype(np.int32)
        m = key_green(rgb)
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        p, phx, phy = forge.refine_grid(rgb[y0:y1, x0:x1], m[y0:y1, x0:x1], grid)
        s = snap_to(forge.sample_native(rgb[y0:y1, x0:x1], m[y0:y1, x0:x1], p, phx, phy), pal)
        lab, sizes = forge.components(s[..., 3] > 0)  # drop specks the keying leaves behind
        s[~np.isin(lab, [i for i, z in enumerate(sizes) if i and z >= max(sizes[1:]) * 0.03])] = 0
        s = forge.tidy(s)
        sprites.append(s)
    W, H = max(s.shape[1] for s in sprites), max(s.shape[0] for s in sprites)
    frames = np.stack([pad_to(s, W, H) for s in sprites])
    # pose distance between frames, then the period that makes frame i look most like frame i+T
    flat = frames.reshape(len(frames), -1).astype(np.int32)
    n = len(frames)
    lo, hi = n // 4, 3 * n // 4  # ignore the eased start and end
    best = None
    for T in range(6, n // 2):
        d = np.mean([np.abs(flat[i] - flat[i + T]).mean() for i in range(lo, min(hi, n - T))])
        if best is None or d < best[0]:
            best = (d, T)
    T = best[1]
    start = (n - T) // 2
    picks = [start + round(j * T / a.frames) for j in range(a.frames)]
    if a.lock:
        frames = np.stack([lock_head(fr, src, a.lock) for fr in frames])
    out = os.path.join(WORK, 'video', 'extracted', a.name)
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.png')):
        os.remove(f)
    for j, i in enumerate(picks):
        Image.fromarray(frames[i]).save(os.path.join(out, f'{j + 1:02d}.png'))
    json.dump({'video_frames': n, 'period_frames': T, 'period_s': round(T / 24, 2), 'picked': picks, 'grid_px': round(grid, 2), 'size': [W, H]},
              open(os.path.join(out, 'info.json'), 'w'))
    print(f'{a.name}: cycle {T} frames ({T / 24:.2f}s), picked {picks}, {W}x{H}px')


if __name__ == '__main__':
    main()
