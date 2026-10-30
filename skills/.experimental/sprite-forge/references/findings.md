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
| **Walk cycles from Retro Diffusion, by takes** (`rd_anim.py`). | $0.14 a try for true pixel art from our own sprite, nothing to clean up, and the only service that added hair, tail and blink motion unasked. Quality varies by take on every service, so regenerate and pick rather than fix (see the comparison below). |
| **Grok video as the alternative, looped.** | Grok Imagine Video 1.5 with the first and last frame pinned to the same image gives a clean loop, smoother and more varied than image-model frames, but costs $0.34 a clip and needs the clean-up below. For no Retro Diffusion key, or sprites over its 256px. Cheaper video models were tried and none was better in every direction (see the video bake-off below). |
| **Already-1:1 frames skip grid recovery** (`anim/`). | Grid recovery reads true 1px detail as 4-7px blocks and shrinks a sprite to a smudge. |
| **A character's views share one pixel size** (their median), or exactly the recipe's `pixel`. | Detected per view, the sizes drifted 9.9-12.7px on four same-height figures, so views and walk frames came out at different heights (65-75px on one walk). |
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
| Video clip, 4 s, through OpenRouter: Veo 3.1 Lite 720p / Seedance 2.0 Mini 480p / Wan 3.0 480p | $0.12 / $0.14 / $0.21 |
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
- Characters made in different sheets still differ in scale by their sheets' pixel size (the new cast
  came out 73px tall to the worker's 66px); set `pixel` to the reference's size to match them.
- Still frames from the services (PixelLab rotations, Retro Diffusion props) have no import path yet,
  only animations through `anim/`.

## Compared with PixelLab, Retro Diffusion and Sprite Fusion

Same set, through each service's REST API, 29 October 2026, in two rounds: the cases above on PixelLab
(v2) and Retro Diffusion (v2), then walks for three new characters (a long-haired staffer, a courier, a
cat) on those two and Sprite Fusion (v1), two runs each where credits allowed. Cost: $5.24 on Retro
Diffusion, 38 free PixelLab generations (about $0.009 each at credit prices) and 300 Sprite Fusion
credits.

- **All three give a true grid**: 1 image pixel = 1 art pixel, no semi-transparent pixels. **Don't run
  forge.py on their output**: it reads 1px detail as 4-7px blocks and shrinks a sprite to a smudge,
  and `pixel: 1` makes it enlarge by a non-integer factor. A native mode should skip grid recovery
  and keep the atlas, animations and review page.
- **From text, neither PixelLab nor Retro Diffusion matches our look** (Sprite Fusion untested).
  PixelLab's standard mode ignored "chibi"; its v3 is chibi but detailed (54 colours). Retro Diffusion
  drew realistic people, and a pig for the ham. PixelLab v3 without a reference draws only humanoids.
- **From our finished sprite, both stay on model**, keep our 2×2 blocks and both eyes:
  PixelLab `create-character-v3` with a reference (4 directions, 1 generation) and Retro Diffusion
  `rd_advanced_animation__rotate` (8 views, $0.10). PixelLab keeps the view it is given exactly but
  redraws the others: on the new cast, shorter hair side on and a crouching cat.
- **Walks: Retro Diffusion, and regenerate rather than fix.** Over five characters every service gave
  good and bad runs, so choose on price per try. `rd_advanced_animation__walking` from our sprite
  ($0.14 a direction, 2-5 min) worked 16 of 16 times, kept our palette (8-16 colours) and was the only
  one to add secondary motion unasked: hair sways, a tail curls, the cat blinks.
- **Sprite Fusion `animate` from our sprite is close** (15 credits, 15-50 s, in parallel), but skip
  the `edit` into a walking pose its guide recommends: 3 of 6 edits returned a pose at the wrong size
  or redrawn, and the animation inherits it. **PixelLab v3 custom walks** (2 generations a direction)
  add detail (44-61 colours against our 13-17) and walk from its own redrawn side views; its template
  walks are 1 generation but redraw on a skeleton: smaller head, thinner outline.
- **Per walk direction**: Retro Diffusion $0.14; Grok video $0.34 plus keying, cycle detection and
  colour snapping; Sprite Fusion $0.25-0.50 depending on plan ($0.50-1.00 with the pose edit);
  PixelLab 2 generations. Mirror a side walk for the other side on any of them.
- **Props: keep sheets.** One $0.01 sheet keeps one scale. RD Pro with the worker as a reference
  matched his outline ($0.18 each) but each prop fills its canvas, so relative size is lost. PixelLab
  Pixen props were busy and off-style; Bitforge with a style image redrew the worker.
- **Tiles: PixelLab.** `create-tileset` (1 generation) makes Wang sets, and `transition_size: 1.0`
  gives raised walls. Retro Diffusion tilesets are flat two-texture blends: no walls.
- **Practicalities.** PixelLab's free tier runs one job and one direction at a time (1-5 min each);
  its ZIP export dropped frames (use the frame URLs), and its usage field reports a USD price even
  when the trial charges generations. Retro Diffusion runs in parallel and has a free `check_cost`,
  but RD Pro failed 4 of 14 attempts, mostly under parallel load (refunded); its walk and rotate
  styles never failed. Sprite Fusion is built for agents (one `POST /generate` that streams events),
  runs in parallel, trims output to the sprite, and sells credits by subscription ($9-49 a month for
  450-3,000) or top-up ($5 for 150). All three allow commercial use and forbid training other models
  on outputs; Retro Diffusion may train on yours, and Sprite Fusion may show work made with free
  credits in its public gallery.

## Video bake-off: replacements for Grok

30 October 2026, on the courier walking right and toward the camera: two takes per model and
direction through OpenRouter's video API (`POST /api/v1/videos`), the same green canvas, prompt and
pinned first and last frame as `video.py`, cleaned up with `extract.py --lock 0.45`. Three Grok takes
and four Retro Diffusion takes for comparison. Cost: $3.06.

- **Kept Grok.** No cheaper model was better in both directions, and switching needs a second
  provider path for a fallback that only runs without Retro Diffusion.
- **Veo 3.1 Lite** ($0.12, about a minute) was the most faithful side-on, with the cleanest frames, but
  both front walks ignored "calm": arms flung out, stomping. Worth retrying with a stronger prompt
  (small steps, arms close to the body) before reconsidering.
- **Wan 3.0** ($0.21) made the best calm front walk and the worst take: one turned the character
  three-quarters and walked diagonally, which the head lock can't repair. Softer frames side-on.
- **Seedance 2.0 Mini** ($0.14) redrew the side view (a satchel became a backpack) and barely walked
  toward the camera; it also darkens the frame and returns 864×496, not quite 16:9.
- **Grok** toward the camera: one near-standing shuffle, one fair walk. **Retro Diffusion**: all four
  takes on model.
- **Kling 3.0 std** was not run: on OpenRouter its only provider was outside the account's allowed
  providers.
- Practicalities: every clip looped, and `extract.py` cleaned up all 15 unchanged, whatever the
  resolution. Toward-camera walks vary far more between models and takes than side walks.
  OpenRouter video can't run under Zero Data Retention (providers keep the clip for download), so an
  account that enforces it needs a separate key or workspace. On OpenRouter, Grok accepts only a first
  frame, so it can't loop there; use xAI directly.
