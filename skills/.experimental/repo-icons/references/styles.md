# Icon styles

Stock prompt templates for repository icons. Show the user the menu (ID, name,
one-line look), let them pick one or more, then fill `{subject}` per repository.

Example results for every template, on three hypothetical apps, are in
`examples/index.html` (images `examples/<app>-<style-id>.webp`). After changing a
template, regenerate its examples: the skill's `scripts/build_examples.py` prints the
prompts and rebuilds the sheet.

Every template already asks for a centered, isolated subject on a transparent
background with no text. Always also request a transparent background through
the image tool's own option, not just the prompt.

## Writing `{subject}`

One concrete object or scene that stands for what the repository does, in about
15 to 30 words. Read the description and the top of the README first.

- Prefer a single physical thing with a twist over an abstract diagram:
  "a clipboard with a stopwatch clipped to it and green and red status dots"
  beats "an icon representing CI analytics".
- Pick a metaphor from the name when there is one (flashlink: a lightning-bolt
  chain link; social-sifter: a gold-panning sieve).
- Name two or three colors when the project has brand colors (from an existing
  logo, CSS variables or a favicon); otherwise let the style choose.
- Keep it readable at 16px: one silhouette, few small details.
- Never ask for letters, words or logos of real companies.

When the user picks more than one style for a repository, reuse the same subject
across styles so the picks compare like for like, unless they ask for variety.

## Menu

| ID | Name | Look |
|---|---|---|
| `pixel-8bit` | 8-bit pixel item | NES-era sprite: chunky pixels, 3–4 colors, bold black outline |
| `pixel-16bit` | 16-bit pixel item | SNES/GBA RPG inventory item: richer palette, highlights, dark outline |
| `pixel-hd` | HD pixel art | Modern indie pixel art: finer grid, soft shading, glow accents |
| `flat-logo` | Flat logo mark | Simple geometric vector mark, two or three flat colors |
| `app-tile` | App tile | Bold glyph on a rounded-square colored tile, like a phone app icon |
| `sticker` | Sticker emblem | Cartoon sticker with a thick white die-cut border |
| `mascot` | Mascot | Cute character that personifies the project |
| `clay-3d` | 3D clay / toy | Soft glossy 3D render, like a vinyl toy or clay model |
| `line-glyph` | Line glyph | Single-weight monoline icon, one or two colors, very minimal |

The three pixel styles differ mainly in grid size and palette: `pixel-8bit` is
the boldest at tiny sizes, `pixel-16bit` has the most detail of the three while
still reading as a game item, and `pixel-hd` looks like a modern indie game.

## Templates

### `pixel-8bit`
```
Retro 8-bit pixel art sprite of {subject}, in the style of an NES-era item pickup. Very coarse grid (about 16x16 sprite scaled up), crisp hard-edged square pixels, no anti-aliasing, a limited palette of 3 to 4 bold colors plus a thick black outline, flat shading. Centered single isolated object, transparent background, no text, no letters.
```

### `pixel-16bit`
```
Retro 16-bit pixel art icon of {subject}, like an inventory item in a SNES or Game Boy Advance RPG. Crisp hard-edged pixels on a coarse grid (about 32x32 sprite scaled up), limited vibrant palette with highlight and shadow tones, dark 1-pixel outline. Centered single isolated object, transparent background, no text, no letters.
```

### `pixel-hd`
```
Modern high-detail pixel art icon of {subject}, in the style of a contemporary indie game (fine 64x64 pixel grid). Clean pixel clusters, soft dithered shading, a few glowing accent pixels, subtle rim light, no blur. Centered single isolated object, transparent background, no text, no letters.
```

### `flat-logo`
```
App icon logo mark: {subject}. Flat vector style, simple geometric shapes, two or three flat colors, no gradients, no outline shadow. Iconic and legible at 16px and 256px, centered with even padding, single isolated mark, transparent background, no text, no letters.
```

### `app-tile`
```
App icon: a rounded-square tile filled with one bold color, with {subject} as a simple high-contrast glyph in the middle. Flat style, generous padding inside the tile, crisp edges. The tile is centered and everything outside the tile is transparent background. No text, no letters.
```

### `sticker`
```
Sticker emblem icon: {subject}. Bold cartoon illustration with a thick white die-cut border and a dark outline, vivid colors, simple cel shading. Centered, single isolated subject, legible at small sizes, transparent background, no text, no letters.
```

### `mascot`
```
Cute mascot character icon: {subject}. Chibi proportions, big expressive eyes, friendly pose, clean cartoon line art with soft shading, two or three main colors. Head and upper body fill most of the frame, centered, single isolated character, transparent background, no text, no letters.
```

### `clay-3d`
```
3D icon of {subject}, rendered like a glossy vinyl toy or soft clay model. Rounded chunky forms, soft studio lighting, gentle highlights, pastel to medium saturated colors, no harsh shadows on the ground. Centered single isolated object, transparent background, no text, no letters.
```

### `line-glyph`
```
Minimal line icon of {subject}. Single consistent stroke weight, rounded line caps, one or two colors, no fill or only one small flat fill accent, lots of negative space. Centered with even padding, single isolated glyph, transparent background, no text, no letters.
```

## Generation settings

- Square, at least 1024×1024, PNG with a transparent background.
- Medium quality is enough for concepts. Higher quality costs more and rarely
  changes which idea the user picks.
- Name files `<repo-name>-<style-id>.png` (add `-2`, `-3` for extra variations)
  so the gallery manifest is easy to build.
