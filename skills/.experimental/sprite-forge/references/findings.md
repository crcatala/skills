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
- A `native` input mode for art that is already 1:1, and an optional PixelLab backend (see below).

## Compared with PixelLab and Retro Diffusion

Same set, same cases, 29 October 2026, through each service's REST v2 API. Cost: $3.56 on Retro
Diffusion and 26 free PixelLab generations (about $0.009 each at credit prices).

- **Both give a true grid**: 1 image pixel = 1 art pixel, no semi-transparent pixels. **Don't run
  forge.py on their output**: it reads 1px detail as 4-7px blocks and shrinks a sprite to a smudge,
  and `pixel: 1` makes it enlarge by a non-integer factor. A native mode should skip grid recovery
  and keep the atlas, animations and review page.
- **From text, neither matches our look.** PixelLab's standard mode ignored "chibi"; its v3 is chibi
  but detailed (54 colours). Retro Diffusion drew realistic people, and a pig for the ham. PixelLab v3
  without a reference draws only humanoids.
- **From our finished sprite, both stay on model**, keep our 2×2 blocks and both eyes:
  PixelLab `create-character-v3` with a reference (4 directions, 1 generation) and Retro Diffusion
  `rd_advanced_animation__rotate` (8 views, $0.10).
- **Walks from our sprite beat Grok video.** PixelLab v3 custom animation kept our exact pixels with
  calm arms toward the camera (2 generations a direction; one direction tested). Retro Diffusion
  `rd_advanced_animation__walking` was close ($0.14 a direction). PixelLab template walks are 1
  generation a direction but redraw on a skeleton: smaller head, thinner outline.
- **Props: keep sheets.** One $0.01 sheet keeps one scale. RD Pro with the worker as a reference
  matched his outline ($0.18 each) but each prop fills its canvas, so relative size is lost. PixelLab
  Pixen props were busy and off-style; Bitforge with a style image redrew the worker.
- **Tiles: PixelLab.** `create-tileset` (1 generation) makes Wang sets, and `transition_size: 1.0`
  gives raised walls. Retro Diffusion tilesets are flat two-texture blends: no walls.
- **Practicalities.** PixelLab's free tier runs one job and one direction at a time (1-5 min each);
  its ZIP export dropped frames (use the frame URLs), and its usage field reports a USD price even
  when the trial charges generations. Retro Diffusion runs in parallel and has a free `check_cost`,
  but RD Pro failed 4 of 14 attempts, mostly under parallel load (refunded). Both allow commercial
  use; neither allows training other models on outputs; Retro Diffusion may train on yours.
