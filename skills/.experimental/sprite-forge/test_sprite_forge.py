"""Synthetic checks: forge recovers a sprite from fake, blurry "pixel art", packs native animation
takes, and rd_anim prepares and splits frames (python -m unittest; no network)."""
import os, sys, tempfile, unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
import forge  # noqa: E402
import rd_anim  # noqa: E402

# 10x12 sprite with an outline and two 1-pixel eyes, like a small character's face
SPRITE = [
    "..KKKKKK..",
    ".KSSSSSSK.",
    "KSSSSSSSSK",
    "KSEsSSEsSK",
    "KSSSSSSSSK",
    "KSSSMMSSSK",
    ".KSSSSSSK.",
    "..KKKKKK..",
    ".KBBBBBBK.",
    ".KBBBBBBK.",
    ".KBBKKBBK.",
    ".KK....KK.",
]
COL = {'K': (30, 20, 20), 'S': (240, 190, 150), 'E': (10, 10, 10), 's': (250, 250, 250), 'M': (200, 60, 70), 'B': (60, 90, 170)}


def fake_model_sheet(scale=10.6):
    """Draw the sprite the way an image model does: off-grid blocks, soft edges, a halo."""
    h, w = len(SPRITE), len(SPRITE[0])
    a = np.zeros((h, w, 4), np.uint8)
    for y, row in enumerate(SPRITE):
        for x, ch in enumerate(row):
            if ch != '.':
                a[y, x, :3] = COL[ch]; a[y, x, 3] = 255
    big = Image.fromarray(a).resize((round(w * scale), round(h * scale)), Image.NEAREST).filter(ImageFilter.GaussianBlur(1.2))
    sheet = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    sheet.alpha_composite(big, (91, 67))
    return np.array(sheet), a


class ForgeTest(unittest.TestCase):
    def test_recovers_grid_and_eyes(self):
        sheet, truth = fake_model_sheet()
        rgb, mask = sheet[..., :3].astype(np.int32), sheet[..., 3] >= forge.ALPHA_CUT
        y0, y1, x0, x1, keep = forge.find_sprites(mask, [1, 1])[0]
        sub = rgb[y0:y1, x0:x1]
        p, phx, phy = forge.refine_grid(sub, keep, forge.pixel_period(sub, keep))
        self.assertAlmostEqual(p, 10.6, delta=1.0)
        out = forge.tidy(forge.sample_native(sub, keep, p, phx, phy))
        self.assertEqual(out.shape[:2], truth.shape[:2])
        # both eyes keep a dark pixel and a white highlight
        dark = (out[..., :3].astype(int).sum(2) < 60) & (out[..., 3] > 0)
        white = (out[..., :3].astype(int).sum(2) > 700) & (out[..., 3] > 0)
        self.assertGreaterEqual(dark[3].sum(), 2)
        self.assertGreaterEqual(white[3].sum(), 2)

    def test_half_grid_doubles_size(self):
        sheet, truth = fake_model_sheet()
        rgb, mask = sheet[..., :3].astype(np.int32), sheet[..., 3] >= forge.ALPHA_CUT
        y0, y1, x0, x1, keep = forge.find_sprites(mask, [1, 1])[0]
        sub = rgb[y0:y1, x0:x1]
        p, phx, phy = forge.refine_grid(sub, keep, forge.pixel_period(sub, keep))
        out = forge.tidy(forge.sample_native(sub, keep, p / 2, phx, phy))
        self.assertLessEqual(abs(out.shape[0] - 2 * truth.shape[0]), 2)

    def test_fixed_grid_keeps_size(self):
        sheet, _ = fake_model_sheet()
        rgb, mask = sheet[..., :3].astype(np.int32), sheet[..., 3] >= forge.ALPHA_CUT
        y0, y1, x0, x1, keep = forge.find_sprites(mask, [1, 1])[0]
        p, _, _ = forge.refine_grid(rgb[y0:y1, x0:x1], keep, 9.0, fixed=True)
        self.assertEqual(p, 9.0)


def frame(w, h, foot=0, colour=(200, 60, 70)):
    """A w x h block on a 20x24 transparent canvas, its bottom `foot` px above the canvas bottom."""
    a = np.zeros((24, 20, 4), np.uint8)
    a[24 - foot - h:24 - foot, 10 - w // 2:10 - w // 2 + w] = (*colour, 255)
    a[24 - foot - h, 10 - w // 2] = (0, 0, 0, 255)  # a dark top-left corner, so a mirror is detectable
    return Image.fromarray(a)


class AnimTest(unittest.TestCase):
    def write_take(self, root, name, take, frames):
        d = os.path.join(root, 'anim', name, take); os.makedirs(d)
        for i, f in enumerate(frames):
            f.save(os.path.join(d, f'{i + 1:02d}.png'))

    def test_pick_trim_and_mirror(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_take(root, 'walk', 'take-01', [frame(4, 6), frame(4, 8)])
            self.write_take(root, 'walk', 'take-02', [frame(6, 10, foot=1), frame(8, 10, foot=1), frame(6, 9, foot=1)])
            Path(root, 'anim', 'walk', 'pick').write_text('take-01\n')
            os.makedirs(os.path.join(root, 'anim', 'walk-left'))
            Path(root, 'anim', 'walk-left', 'mirror').write_text('walk\n')
            a = forge.load_anims(root)
            self.assertEqual(a['walk']['pick'], 'take-01')
            self.assertEqual(len(a['walk']['frames']), 2)
            self.assertEqual([f.shape[:2] for f in a['walk']['frames']], [(8, 4), (8, 4)])  # trimmed to the union
            self.assertEqual(len(a['walk']['takes']), 2)
            np.testing.assert_array_equal(a['walk-left']['frames'][0], a['walk']['frames'][0][:, ::-1])
            self.assertFalse(np.array_equal(a['walk-left']['frames'][0], a['walk']['frames'][0]))
            os.remove(os.path.join(root, 'anim', 'walk', 'pick'))
            self.assertEqual(forge.load_anims(root)['walk']['pick'], 'take-02')  # no pick: the newest take

    def test_mirror_of_nothing_fails(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'anim', 'left'))
            Path(root, 'anim', 'left', 'mirror').write_text('right\n')
            with self.assertRaises(SystemExit):
                forge.load_anims(root)

    def test_start_canvas(self):
        c = rd_anim.start_canvas(Image.fromarray(np.pad(np.array(frame(10, 20)), ((5, 5), (5, 5), (0, 0)))))
        self.assertEqual(c.size, (32, 32))  # the API's minimum
        x0, y0, x1, y1 = c.getbbox()
        self.assertEqual((x1 - x0, y1 - y0), (10, 20))
        self.assertEqual(y1, 32 - 2)  # feet just above the bottom
        big = Image.fromarray(np.full((67, 35, 4), 255, np.uint8))
        self.assertEqual(rd_anim.start_canvas(big).size, (72, 72))
        with self.assertRaises(SystemExit):
            rd_anim.start_canvas(Image.fromarray(np.full((260, 40, 4), 255, np.uint8)))

    def test_split_sheet(self):
        sheet = Image.new('RGBA', (4 * 32, 2 * 32))
        for i in range(8):
            sheet.paste(Image.new('RGBA', (5, 5), (i * 30, 0, 0, 255)), ((i % 4) * 32 + 3, (i // 4) * 32 + 3))
        cells = rd_anim.split_sheet(sheet, 32, 8)
        self.assertEqual([c.getpixel((4, 4))[0] for c in cells], [i * 30 for i in range(8)])  # row by row
        with self.assertRaises(SystemExit):
            rd_anim.split_sheet(sheet, 32, 10)


if __name__ == '__main__':
    unittest.main()
