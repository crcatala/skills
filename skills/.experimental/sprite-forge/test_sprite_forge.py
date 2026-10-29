"""Synthetic check that forge recovers a sprite from fake, blurry "pixel art" (python -m unittest)."""
import os, sys, unittest
import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
import forge  # noqa: E402

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


if __name__ == '__main__':
    unittest.main()
