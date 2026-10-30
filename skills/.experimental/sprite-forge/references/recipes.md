# Recipes

`recipes.json` in a sprite set:

```json
{
  "style": "16-bit pixel art game sprites in the style of Stardew Valley, … laid out evenly in a grid.",
  "recipes": [
    {
      "id": "office-props-ref",
      "kind": "props",
      "grid": [3, 2],
      "names": ["espresso-machine", "potted-plant", "arcade-cabinet", "server-rack", "water-cooler", "trophy"],
      "reference": "staff-turnaround",
      "prompt": "Draw new props that match the attached character sheet exactly: … Six cosy office props, 3 columns by 2 rows, …"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `style` | Prepended to every prompt. Keep one per set. |
| `id` | Names `raw/<id>.png` and the sprites `out/sprites/<id>/<name>.png`. |
| `kind` | `props` (each sprite stands alone) or `character` (frames bottom-centred in one frame size; becomes an animation named `<id>`). |
| `grid` | `[columns, rows]` of the sheet. Describe the cells in the prompt in reading order. |
| `names` | One per cell, reading order. |
| `reference` | Another recipe whose raw sheet is passed as a reference image. Use on every recipe but the first. |
| `max` | `[w, h]` in px: shrink exactly 2× while the sprite is over 1.3× this. For a model that drew something far too big. |
| `fix` | Per-cell repairs, e.g. `{"walk-down-3": {"mirror": "walk-down-1"}}`. |
| `pixel` | The model's pixel size in image pixels, used exactly. Without it, each sprite's is detected, and a `character`'s views share their median so they come out the same height. To put a new character on another's scale, set this to that character's detected size (`out/report.json`). |
| `note`, `experiment` | Free text shown on the review page. |

Characters: ask for "shown 4 times in a single row as a top-down RPG turnaround: facing the camera,
facing left, facing right, facing away", with names `down`, `left`, `right`, `up`. Video animation
expects those names.

A starting set (a turnaround, a second character matched to it, two prop sheets and a mascot, all
referencing the first turnaround) is in [example-recipes.json](example-recipes.json).

Image-model walk frames (a `character` recipe with a `reference` asking for "a 4-frame walk cycle") work
but are hit and miss; looping video (see SKILL.md) gives better motion.
