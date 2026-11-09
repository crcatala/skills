---
name: image-gen
description: Generate or edit images with OpenAI GPT Image (gpt-image-2.6-flare, default) or xAI Grok Imagine (grok-imagine-image-2.0). Use when an agent needs a persistent image asset from a text prompt, a transparent-background asset (icon, sticker, logo, cutout), an SVG vector logo or icon, a short animated GIF, or to modify local or public images with natural-language instructions or a circled markup overlay. Requires OPENAI_API_KEY and/or XAI_API_KEY and incurs API charges.
compatibility: "Requires python3, network access, and OPENAI_API_KEY and/or XAI_API_KEY. Incurs API charges."
---

# Image Generation

In the commands below, `{baseDir}` is the directory containing this `SKILL.md`.

One wrapper for multiple image providers. It calls each provider's REST API directly (Python standard library only, no SDKs), saves images locally rather than returning temporary URLs, and checks options against what the chosen provider supports before any API call. An unsupported option stops the run with an explanation; it is never silently dropped. The checks follow the default model families (GPT Image 2.5/2.6 and Grok Imagine). Older OpenAI models such as `gpt-image-2` or `gpt-image-1.5` may reject some sizes or qualities with an API error (`gpt-image-1` was shut down in October 2026).

## Choosing a provider

| Situation | Use |
|---|---|
| No provider or model named | OpenAI (default): `gpt-image-2.6-flare` |
| **Transparent background requested** (icon, sticker, logo, cutout, "no background", PNG with alpha) and no provider named | OpenAI with `--transparent` |
| User asks for Grok/xAI | `--provider xai` (default model `grok-imagine-image-2.0`) |
| User asks for Grok/xAI **and** transparency | **Do not run it.** Tell the user Grok Imagine cannot produce transparent images (it returns an opaque image, and prompting for transparency paints a fake checkerboard into the pixels). Offer OpenAI instead, or Grok with an opaque background. |
| Exact pixel size, masks or markup, WebP/PNG/JPEG choice, or more than 3 reference images | OpenAI |
| SVG (editable vector) or animated GIF output | OpenAI with a GPT Image 2.6 model (the default) |
| Many cheap `low`/`medium` drafts where cost matters more than speed | `--model gpt-image-2.5-flare` (see Cost) |

When the user wants a transparent asset, always pass `--transparent`. Do not rely on wording like "transparent background" in the prompt alone.

## Setup

```bash
export OPENAI_API_KEY="..."   # for --provider openai (default)
export XAI_API_KEY="..."      # for --provider xai
```

If only `XAI_API_KEY` is set and neither `--provider` nor `--model` is given, requests that xAI can serve use xAI, and a note is printed on stderr. Requests that need OpenAI, such as `--transparent`, never fall back.

Optional: `OPENAI_BASE_URL` or `XAI_BASE_URL` override the API base URL.

## Usage

```bash
python3 {baseDir}/generate.py "prompt describing the image" [options]
```

By default, images are saved to `/tmp/image-gen/`, keeping them out of the current project. Use `--output` to save an asset into the project. The command prints the saved paths, or structured metadata with `--json`. **Always use the printed path.** The file extension always matches the returned image format. For OpenAI the format follows the `--output` extension, so `-o hero.webp` saves `hero.webp`. xAI picks its own format (JPEG or PNG), so the extension can change; a note is printed when it does.

### Examples

```bash
# Transparent sticker/icon (OpenAI); saves a PNG with a real alpha channel
python3 {baseDir}/generate.py \
  "Cheerful cartoon fox mascot waving, flat vector sticker style, isolated subject, no text" \
  --transparent --aspect-ratio 1:1 --output assets/fox.png

# 2K 16:9 website hero as compressed WebP (maps to 2048x1152)
python3 {baseDir}/generate.py \
  "Minimal editorial photo of a desk by a sunlit window, no text" \
  --aspect-ratio 16:9 --resolution 2k --format webp --compression 80 --output assets/hero.webp

# Exact pixel size (OpenAI only)
python3 {baseDir}/generate.py "Abstract teal gradient texture" --size 1536x864 --output assets/bg.png

# Cheap drafts: several low-quality variations
python3 {baseDir}/generate.py "Isometric floating-island coffee shop, pastel" \
  --n 3 --quality low --output drafts/island

# Edit an image while keeping its transparency
python3 {baseDir}/generate.py \
  "Keep the same fox, add round sunglasses. Preserve the transparent background." \
  --image assets/fox.png --transparent --output assets/fox-sunglasses.png

# Masked edit: transparent pixels in the mask mark the area to change
python3 {baseDir}/generate.py "Replace the sky with a starry night" \
  --image photo.png --mask sky-mask.png --output photo-night.png

# Grok Imagine 2.0
# (xAI chooses JPEG or PNG, so the saved extension may differ from --output; use the printed path)
python3 {baseDir}/generate.py "Neon-lit rainy Tokyo alley at night, cinematic" \
  --provider xai --aspect-ratio 16:9 --resolution 2k --quality medium --output assets/alley.jpg

# Grok multi-reference edit (up to 3 images)
python3 {baseDir}/generate.py "Place the robot from the first image into the second scene" \
  --provider xai --image robot.jpg --image lighthouse.png --aspect-ratio 1:1

# SVG logo (GPT Image 2.6; new images only, one per request)
python3 {baseDir}/generate.py "Flat two-colour bakery logo: a wheat stalk in a circle, no text" \
  --output assets/logo.svg

# Looping animated GIF (GPT Image 2.6): 8 frames at 120 ms each
python3 {baseDir}/generate.py \
  "Pixel-art campfire, flames flicker and return to the first pose, seamless loop, dark background" \
  --format gif --frames 8 --frame-duration 120 --size 512x512 --output assets/campfire.gif

# Markup-guided edit: a transparent PNG, the same size as the image, with a circle around the target
python3 {baseDir}/generate.py \
  "Recolor the vase inside the red circle to cobalt blue. Keep everything else unchanged. Remove the red circle." \
  --image kitchen.png --markup vase-circle.png --complexity low --output kitchen-blue-vase.png

# Inspect the request without spending credits
python3 {baseDir}/generate.py "test" --provider xai --aspect-ratio 16:9 --dry-run
```

### Options

| Option | OpenAI | xAI | Description |
|---|---|---|---|
| `--provider` | ✓ | ✓ | `openai` (default) or `xai`. Inferred from `--model` when omitted. |
| `--model` | ✓ | ✓ | Default `gpt-image-2.6-flare` / `grok-imagine-image-2.0`. Others: `gpt-image-2.6-sunburst` (detailed work and edit consistency, about 2–3× slower), `gpt-image-2.5-flare` and `gpt-image-2.5-sunburst` (cheaper at `low`/`medium`; no complexity, SVG or GIF), `grok-imagine-image-quality`, `grok-imagine-image`. DALL-E models are not supported. |
| `--n N` | ✓ | ✓ | Number of images, 1–10 (default 1). |
| `--aspect-ratio W:H` | ✓ | ✓ | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `2:1`, `1:2`, `19.5:9`, `9:19.5`, `20:9`, `9:20`, or `auto`. OpenAI also accepts any other ratio up to 3:1. |
| `--resolution 1k\|2k` | ✓ | ✓ | OpenAI: 1k ≈ 1 megapixel, 2k = 2048px long edge. |
| `--size WxH` | ✓ | ✗ | Exact size: multiples of 16, edge ≤ 3840, ratio ≤ 3:1, 655,360–8,294,400 pixels. Overrides aspect ratio and resolution. |
| `--quality` | ✓ | ✓ | Default `medium`. OpenAI: `low`, `medium`, `high`, `xhigh`, `max`, `auto`. xAI: `low`, `medium` (only `grok-imagine-image-2.0`). |
| `--transparent` | ✓ | ✗ | Transparent background; output must be PNG (default) or WebP. |
| `--format` | ✓ | ✗ | `png`, `jpeg`, `webp`, `svg`, or `gif` (the last two need GPT Image 2.6). Defaults to the `--output` extension, else `png`; a conflicting extension is an error. xAI returns its own format (JPEG or PNG). |
| `--complexity` | ✓ | ✗ | `low`, `medium`, or `high` (GPT Image 2.6 only; the API default is `high`). How much the model plans before rendering, separate from `--quality`. Use `low` for focused edits (a background, a sign), where `high` can change things you did not ask for and adds latency; keep `high` for dense text and complex layouts. No extra fee. |
| `--frames N` | ✓ | ✗ | GIF frames, 2–16 (API default 9). |
| `--frame-duration MS` | ✓ | ✗ | Milliseconds per GIF frame, 20–2000 (API default 200). |
| `--svg-model` | ✓ | ✗ | Model that writes the SVG from a reference image (default `gpt-6.1-terra`). Use `none` to omit it if your organization does not have SVG model selection. |
| `--compression 0-100` | ✓ | ✗ | JPEG/WebP compression. |
| `--image PATH_OR_URL` | ✓ | ✓ | Repeatable input or reference image (OpenAI: up to 16, PNG/JPEG/WebP; xAI: up to 3, PNG/JPEG). Switches to the edit endpoint. With `--format gif`, still images guide the animation. |
| `--mask PATH` | ✓ | ✗ | PNG mask applied to the first `--image`. Not with GIF output. |
| `--markup PATH` | ✓ | ✗ | Transparent PNG of circles, arrows or sketches marking where to edit the first `--image` (GPT Image 2.5/2.6). It must have the same width and height as that image and must not be flattened onto it. Say in the prompt what to change and to remove the marks. Not with `--mask`. |
| `--extra KEY=VALUE` | ✓ | ✓ | Pass any other provider field (for example `moderation=low`); VALUE is parsed as JSON when possible. It cannot set fields that another option controls (such as `background`, `model`, or `size`). |
| `--output, -o` | ✓ | ✓ | File for one image, or a directory (no extension) or filename prefix for several. |
| `--dry-run` | ✓ | ✓ | Print the provider, URL, and request body; no API call. |
| `--json` | ✓ | ✓ | Print paths plus request and response metadata (size, usage, cost). |
| `--timeout SECONDS` | ✓ | ✓ | Request timeout (default 300). |

With OpenAI and no `--aspect-ratio`, `--resolution`, or `--size`, the size is `auto`: for edits it follows the input image, and for generations the model chooses. With `--resolution` but no aspect ratio (or `auto`), the output is square.

SVG and GIF output (GPT Image 2.6):
- **SVG** is for new images only (no `--image`), with `--n 1` and no size options. The API draws a raster reference image at `--quality`, then a second model writes static vector paths from it (no scripts or embedded rasters). Simple logos and icons work well; complex posters have been reported to fail with server errors.
- **GIF** works for new images and edits. `--size` sets each frame (multiples of 16); GIF frames have a smaller pixel budget than stills, and the API rejects requests over it, so start with `512x512` or `auto` (512×512 in testing). GIFs are opaque. With few frames the motion may not loop back to its start, so ask for a seamless loop that returns to the first pose. GIF moderation is stricter than for stills.

## Cost

- **OpenAI:** billed by output image tokens at $30 per million, so cost grows with quality and size. Input images for edits are billed as image input tokens. At API usage tier 1 the limit is 5 images per minute. Prices are the same for 2.5 and 2.6, but at `low` and `medium` **GPT Image 2.6 uses 3–4× more output tokens than 2.5**. Measured at 1024×1024 (November 2026):

  | Model | `low` | `medium` | Time |
  |---|---|---|---|
  | `gpt-image-2.6-flare` | 824 tokens, ~$0.025 | 1,449 tokens, ~$0.043 | 7–8 s |
  | `gpt-image-2.5-flare` | 196 tokens, ~$0.006 | 439 tokens, ~$0.013 | 12–14 s |

  Testers report that `high` and above cost about the same on both versions. For large batches of drafts, `--model gpt-image-2.5-flare` is cheaper. A 4-frame 512×512 GIF at `low` used 555 tokens (~$0.017). SVG output bills the reference image plus the SVG-writing model's tokens.
- **xAI:** `grok-imagine-image-2.0` costs $0.04–0.08 per image depending on quality and resolution; `grok-imagine-image` costs $0.02 and `grok-imagine-image-quality` $0.05.

`--json` reports usage for each request. For xAI, `cost_in_usd_ticks` / 1e10 = USD.

## Notes

- Generated images cost API credits; check the prompt and `--n` before running. Use `--quality low` for drafts.
- Keep output paths inside the current project unless the task requires somewhere else.
- Describe the composition, subject, style, and lighting, and say "no text" when unwanted lettering would be a problem.
- For transparent assets, also describe an isolated subject in the prompt. Inspect edges (hair, glass, shadows) before use.
- Both APIs moderate requests. A filtered request exits non-zero and saves nothing.
- Exit code 2 means the options were invalid for the chosen provider, and no API call was made. Exit code 1 means a missing key or a failed request (HTTP error, timeout, or unreadable response).
- Text rendering is a strength when the exact words are in the prompt; text the model invents (labels, brand names) can still come out garbled. Repeated edits of the same image can drift; prefer Sunburst and `--complexity low` for focused edits.
- Large or `max`-quality OpenAI images can take minutes. If a request times out, retry with a larger `--timeout`.
