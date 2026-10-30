---
name: sprite-forge
description: "Make game-ready pixel-art sprites (props, decorations, characters with turnarounds and looping walk cycles) from image-model output, animated with Retro Diffusion or Grok video: recovers the model's pixel grid, cleans colours, packs a PixiJS atlas and builds a review page. Use when asked to generate, add or redo pixel-art sprites, walk cycles or game art."
compatibility: "Requires uv (or python3 with numpy and Pillow) and an image-generation skill or tool in the session that makes transparent PNGs from a prompt plus a reference image (paid API calls). Animation needs network access and RETRO_DIFFUSION_API_KEY (Retro Diffusion, paid), or ffmpeg and XAI_API_KEY (Grok Imagine Video, paid)."
---

# sprite-forge

Image models draw convincing "pixel art" that is not on a real pixel grid. Generate a sheet per batch,
then let the scripts recover the grid and pack real sprites: the model supplies the look, the scripts
make it usable. In the commands below, `{baseDir}` is the directory containing this file. Why it works
this way: [references/findings.md](references/findings.md).

## Requirements

Check before generating anything, and report what is missing:

```bash
uv --version || python3 -c "import numpy, PIL"
```

- Neither: install uv (https://docs.astral.sh/uv/) or `pip install numpy pillow`.
- **Image generation.** Look through the skills and tools in this session for one that makes an image
  from a prompt, with a **transparent background** and a **reference image** input. Do not assume any
  particular one exists. Found: name it. Found without transparency or reference input: say so and stop
  (the halo removal needs alpha; consistent scale needs references). None: say an image-generation skill
  or tool is a prerequisite and stop.
- Animation only: `RETRO_DIFFUSION_API_KEY` set (Retro Diffusion), or `ffmpeg -version` and
  `XAI_API_KEY` set (Grok video). Neither: skip animation and say why.

## A sprite set

A folder (for a game, something like `art/`) holding `recipes.json`. The scripts write `raw/` (model
output), `video/` and `out/` next to it; run them from that folder. Recipe fields:
[references/recipes.md](references/recipes.md); a starting set with every kind of recipe:
[references/example-recipes.json](references/example-recipes.json).

## Make sprites

1. Write recipes. Start a cast with one character turnaround; **give every other recipe that
   turnaround as its `reference`**, so the sheet matches its pixel size and style.
2. `python3 {baseDir}/scripts/prompt.py` lists each missing sheet, references first: prompt, aspect
   ratio, reference image and output path. Generate each with the session's image tool, transparent
   background, medium quality, saved to `raw/<id>.png`. Look at every sheet; regenerate one that is
   missing a cell, merges cells or drifts off-model.
3. `uv run {baseDir}/scripts/forge.py` writes `out/`: sprites, `atlas.png` + `atlas.json` (PixiJS
   spritesheet format, with animations), `report.json` and the review page `index.html`.
4. Show the user the review page (publish it if a page-sharing tool is available). Check faces and eyes,
   outlines, sizes next to the reference character, and that animations hold steady.

## Animate (optional)

Animate only a finished sprite whose face is right: every method copies whatever it is given. Side
views come out cleanest; mirror right for left instead of paying for both.

### Retro Diffusion (default, $0.14 a take)

`rd_anim.py` sends the sprite as the start frame of a Retro Diffusion animation and gets back true
pixel art: nothing to clean up. Takes vary in quality (so did every service tried), so **regenerate
rather than fix**: each run adds a take, the newest is picked, and the review page plays them all.

```bash
uv run {baseDir}/scripts/rd_anim.py out/sprites/<char>/right.png <char>-walk-right "steady side-view walk cycle in place, facing right, legs stepping and arms swinging gently"
uv run {baseDir}/scripts/forge.py                                    # review every take
uv run {baseDir}/scripts/rd_anim.py --pick <char>-walk-right 2       # keep take 2
uv run {baseDir}/scripts/rd_anim.py --mirror <char>-walk-left <char>-walk-right
uv run {baseDir}/scripts/forge.py
```

Toward the camera: "calm walk toward the camera in place, gentle arm swings, legs alternating".
`--action` also does idle, jump, crouch, attack, destroy, custom_action and subtle_motion (the last
two $0.25); `--frames` 4-16 (8 loops best); `--dry-run` prices a call for free. Sprites up to 256px.
Takes live in `anim/<name>/take-NN/`; forge.py packs the picked one, unchanged, as animation `<name>`.
Frames that are already 1:1 from any other tool can go in `anim/` the same way.

### Grok video (alternative, about $0.34 a clip)

Use it when there is no Retro Diffusion key or the sprite is over 256px. Loops come from Grok Imagine
Video 1.5; the clip is cleaned back onto the sprite's grid and colours.

```bash
uv run {baseDir}/scripts/video.py out/sprites/<char>/right.png <char>-walk-right "<prompt>"
uv run {baseDir}/scripts/extract.py <char>-walk-right --lock 0.45
uv run {baseDir}/scripts/forge.py
```

Prompt for motion in place, for example: "This pixel-art game character, seen from the side facing
right, walks in place: a steady looping side-view walk cycle, legs stepping and arms swinging. The
character stays in the centre and does not travel. Locked-off camera. The flat solid green background
stays exactly the same and empty. Keep the crisp blocky pixel-art look, the same colours and outline,
and keep the face exactly as it is." `--lock` is the head's share of the sprite's height; it pastes the
original head onto every frame.

## Don't

- Resize sprites to fit a tile size. Choose the game's scale to fit them (characters come out about
  66px tall: 32px tiles, or 16px art drawn at 2×).
- Snap different sheets to one shared palette.
- Run art that is already 1:1 (Retro Diffusion, PixelLab, Sprite Fusion output) through grid recovery:
  it reads 1px detail as blocks and shrinks the sprite to a smudge. Put its frames in `anim/` instead.
- Hand-edit `out/`. Fix the recipe (`fix`, `max`) or regenerate, so the set can always be rebuilt.
