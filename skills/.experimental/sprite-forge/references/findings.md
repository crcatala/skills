# sprite-forge: findings and decisions

From three rounds of experiments in October 2026 on a cosy top-down office set (GPT Image
`gpt-image-2.5-flare` for sheets, Grok Imagine Video 1.5 for motion): office and outdoor props, an
office worker, a robot and a walking-ham mascot. Numbers below are from that set.

## What the models actually give you

- **Sheets keep a style together.** One image per batch (a 3×2 grid of props, a 4-frame row of a
  character) keeps style and identity consistent across cells far better than separate images.
- **The "pixels" are fake.** Each art pixel is a blurry block of roughly 5–12 image pixels, the size
  varies between objects (even within one sheet), and the blocks are not perfectly regular: highlights
  half a pixel wide, features half a pixel off their neighbours.
- **Transparent output has a halo**: a soft semi-transparent glow around every sprite.
- **Sizes in the prompt are ignored.** "20×30 art pixels, each a 10×10 block" still gave 5–8px pixels
  within one sheet.
- **A reference image controls scale.** Passing the worker's turnaround put all six props on one ~8px
  grid, sized sensibly next to him; a new robot came out at his height.
- **Walk frames from an image model are hit and miss.** The 4-frame walk stayed on-model but drew frames
  1 and 3 with the same leg forward (fixed by mirroring in the recipe).

## Decisions

| Decision | Why |
|---|---|
| **Never resample to another size; recover the model's grid.** | Squeezing a 34px-tall character into 24px (a 1.4× non-integer shrink) redraws every pixel: patchy outlines, merged eyes. Recovering the grid is close to lossless. |
| **Sample on a half-size grid.** | The model's blocks are not regular. A one-cell-per-art-pixel grid dropped the worker's half-pixel eye highlights (one eye solid black) and fattened one of the mascot's eyes (it sat half a pixel off the other). A grid that follows the colour edges fixed the mascot but not the worker, and stretched faces. Half-size keeps both. |
| **Game scale follows the sprites: 32px tiles.** | Half-size sampling gives characters about 66px tall, mostly 2×2 blocks. 32px tiles (or 16px tile art shown at 2×) keep Stardew-like proportions. |
| **Exact 2× shrink is the only resize**, and only when a recipe's `max` says the model drew something far too big. | Whole-number shrinks are mostly lossless; anything else is a redraw. |
| **Clean colours per sprite; no shared palette.** | Snapping every sheet to one 32–35 colour palette turned chrome teal and gold brown, because the common colours (an orange hoodie, a pink mascot) crowd out small accents. Per-sprite: merge near-duplicate shades, cap at 24. |
| **Drop pixels under alpha 160.** | Removes the model's halo without eating outlines. |
| **Every recipe after the first takes a `reference`.** | Only reliable way found to keep pixel size and style consistent across batches. |
| **Fix model mistakes in the recipe, not by hand** (`fix: mirror`, `max`). | The set stays reproducible from `recipes.json` + `raw/`. |
| **Walk cycles from video, looped.** | Grok Imagine Video 1.5 with the first and last frame pinned to the same image gives a clean loop. Smoother and more varied than image-model frames. |
| **Animate only from a finished sprite.** | Round 2 clips came from sprites with broken eyes and kept them in every frame; round 3 clips from fixed sprites kept the face. |
| **Video frames: snap to the source sprite's colours, lock the head.** | Snapping removes the video's colour drift (no flicker). The head lock pastes the original head onto each frame so the face cannot drift; it changed little on good clips but costs nothing. |
| **Take 8 evenly spaced frames from one cycle in the middle of the clip.** | The pinned start and end ease in and out; the cycle period is found from frame similarity. |

## Video specifics

- Sprite scaled by an exact 6× onto chroma green (Grok can't output transparency); the video comes back
  848×480, so the grid is `6 × 848 / 960` ≈ 5.3px, known rather than guessed.
- Side-view walks were the cleanest. Toward-camera walks flail the arms unless the prompt asks for a calm
  walk with gentle arm swings. Detected cycles were about 0.9–1.3 s (worker) and 1.2–1.8 s (mascot).
- `last_frame` (needed for a loop) only works on `grok-imagine-video-1.5`; the Lite model rejects it.
- Keying leaves occasional specks; components under 3% of the sprite are dropped.

## Costs seen

| Item | Cost |
|---|---|
| Image sheet, 1k, medium quality | about $0.01 |
| Video clip, 4 s, 480p, `grok-imagine-video-1.5` | $0.34 |
| All three rounds (8 sheets, 6 clips) | about $2.15 |

## Tried and dropped

- Fitting sprites to a target box (round 1): the main cause of poor quality.
- One shared studio palette (round 1): washed out accents.
- "Keep a darker minority colour" when downsampling: produced the dark eye patch.
- A grid that follows colour edges: uneven results, stretched proportions.
- Explicit pixel sizes in prompts: ignored.

## Open

- Paper-doll characters (one hand-made or bought base body with generated accessories) may suit a large
  generated cast better; video suits a few named characters and big moments.
- Dedicated pixel-art models (PixelLab, Retro Diffusion) output true grids and may skip most of this
  clean-up; untested.
