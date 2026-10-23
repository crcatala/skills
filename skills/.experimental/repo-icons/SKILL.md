---
name: repo-icons
description: "Wizard that finds your recently active GitHub repositories without a usable icon, generates icon concepts in a choice of styles, lets you pick them on a review page, then adds the icon at a standard path, puts it in the README title, and opens one pull request per repository."
compatibility: "Requires git, the gh CLI (authenticated), uv (or python3 with Pillow), network access, and an image-generation skill or tool in the session that can make transparent PNGs (paid API calls)."
disable-model-invocation: true
argument-hint: "[repos, days, styles or other instructions]"
---

# Repo icons

Give repositories a real icon file: one that apps such as T3 Code show next to
the project, and that the README shows next to its title. In the commands below,
`{baseDir}` is the directory containing this `SKILL.md`.

The icon goes to `assets/icon.png` (or `assets/icon.svg` when reusing an SVG
logo). That path works for repositories that are not websites, and it is one of
the paths T3 Code checks. GitHub itself has no repository icon setting; the
README title image is the visible part on GitHub.

Work as a wizard: one step at a time, short messages, and wait for the user at
each **Stop** below. Skip any step the user already answered in the invocation
text (for example, a list of repositories skips the scan).

## Requirements

Check before step 1, and report anything missing:

```bash
gh auth status && git --version && (uv --version || python3 -c "import PIL")
```

- gh missing or logged out: install from https://cli.github.com, then `gh auth login`.
- Neither uv nor Pillow: install uv (https://docs.astral.sh/uv/). The scripts
  that need Pillow declare it inline, so `uv run` fetches it.

Run Python scripts with `uv run {baseDir}/scripts/<script>.py`; when uv is
missing but Pillow is installed, `python3 {baseDir}/scripts/<script>.py` works
too. `scan.py` needs only the standard library.

**Image generation.** Look through the skills and tools available in this
session for one that generates images from a text prompt, preferably with a
transparent-background option. Do not assume any particular one exists.

- Found: name it in step 1 and say whether it supports transparency.
- Found, but without transparency: say the icons will have a solid background,
  and offer to continue that way or stop.
- None found: say that an image-generation skill or tool is a prerequisite.
  The scan and reusing existing logos still work, so offer those; stop before
  any step that needs generation.

## 1. Scope

If the invocation text names repositories, a time window or styles, use them.
Otherwise ask, in one message:

- Which repositories: scan recent activity (default: the last 30 days, every
  non-fork, non-archived repo the gh account can access), a specific owner or
  org, or a list of `owner/name`.
- Mention which image generator was found (see Requirements).

**Stop** until the user answers, unless the invocation text already did.

## 2. Scan

```bash
python3 {baseDir}/scripts/scan.py [--days 30] [--owner LOGIN ...] [--repo OWNER/NAME ...] [--json]
```

It reads each repository through the GitHub API (no cloning) and reports:

- **✅ found**: a standard icon exists; the path shown is what T3 Code would use.
- **⚠️ logo, not standard**: logo-like files exist, but none at a path tools check.
  These are candidates for reuse.
- **❌ none**: nothing usable. Notes explain near misses, such as an inline
  `data:` favicon or an unparseable `t3.json`.

It also shows the image in the README title, if any.

Show the table. Then ask which repositories to work on and, for each, whether to
**generate** new icons or **reuse** an existing logo (name the file). Accept
short answers such as "3, 5, 8 generate; 12 reuse logo".

**Stop** for the user's list.

## 3. Styles

Read `references/styles.md` and show its menu (ID, name, one-line look). Ask
which styles to generate: the same set for every repository, or per repository.
Suggest two or three to keep the review page manageable.

**Stop** for the user's choice.

## 4. Recap and confirm

Before generating anything, write a plan:

- Each repository with its subject idea (one line, from its description and
  README) and the styles to generate, or the logo file to reuse.
- Total number of images, the generator and model, quality, and an estimated
  cost if the generator documents pricing.
- Where files go: a new working directory outside every repository that
  survives a reboot, such as `~/.cache/repo-icons/<date>/` (not `/tmp`, which
  may be cleared before the user finishes reviewing paid images).
- What happens after picks: one branch and pull request per repository, adding
  `assets/icon.png` and the README title image. Nothing is merged.

**Stop**. Proceed only on an explicit yes. Apply any changes and recap again if
they are substantial.

## 5. Generate

Fill each chosen template from `references/styles.md` with the repository's
subject and generate one square image per (repository, style): at least
1024×1024, transparent PNG, medium quality, saved as
`<workdir>/out/<repo-name>-<style-id>.png`.

- Respect the generator's rate limits; run a few at a time and retry failures
  once or twice before reporting them.
- Look at every result (open a contact sheet or the images themselves). Redo an
  image that contains text, a fake checkerboard, a cut-off subject, or an opaque
  background when transparency was requested.
- For reused logos, just note the file; it appears in the gallery as "Keep
  current".

## 6. Review page

Write `<workdir>/manifest.json` as described at the top of
`scripts/gallery.py`, with one entry per repository: its candidates and, when
reusing or keeping, the existing logo as `current` (download it with
`gh api repos/OWNER/NAME/contents/PATH -H "Accept: application/vnd.github.raw" > FILE` when
it is not on disk). Then:

```bash
uv run {baseDir}/scripts/gallery.py <workdir>/manifest.json -o <workdir>/repo-icons.html
```

The page is a single self-contained file with every image embedded. Give the
user its path and open or display it however this harness allows (an HTML
preview, an artifact, or a file the user opens in a browser; if the session is
on a remote machine, say how to copy it, for example with `scp`). Explain:
pick one tile per repository, "Redo" with a note asks for new ideas, then press
**Copy picks** and paste the result here.

**Stop** for the pasted picks. They look like:

```
repo-icons picks
owner/name: pixel-16bit
owner/other: redo | note: warmer colors
owner/third: keep
```

`skip`, `undecided` (a note without a pick) and missing repositories are left
alone; for `undecided`, ask what the user wants. For `redo`, generate new
concepts using the note, rebuild the page with only those repositories, and
**Stop** again. Do not apply anything for a repository until its pick is final.

## 7. Apply and open pull requests

For each repository with a final pick, without touching any existing local
checkout of it:

1. Clone it into the working directory:
   `gh repo clone OWNER/NAME <workdir>/repos/NAME -- --depth 1`, then create a
   branch such as `chore/repo-icon`.
2. Write the icon and update the README:
   ```bash
   uv run {baseDir}/scripts/apply_icon.py --repo-dir <workdir>/repos/NAME --source <picked image or logo>
   ```
   It trims and squares raster images to 512×512 (`--size` to change),
   copies SVGs unchanged, removes a faint translucent backdrop if the model
   painted one, and changes the README's first heading to
   `<h1><img src="assets/icon.png" width="40" height="40" align="top" alt="" /> Title</h1>`.
   A title that already shows an image is left alone. Everything is checked
   before anything is written; on exit code 1 nothing was written, and the
   JSON `error` says why:
   - an existing `assets/icon.*`: ask before passing `--force`;
   - `shadowed_by` is not empty: another icon (a `t3.json` `iconPath`, or a
     favicon checked earlier) would still be shown instead. Tell the user and
     ask whether to remove or update that file, or keep it and pass
     `--allow-shadowed`;
   - an unreadable README: report it and skip the repository.
   Also report the `readme` status when it is not `updated`, so the user can
   edit an unusual title by hand.
3. Check the repository's own conventions (commit style, a Prettier or
   Markdown lint that covers `README.md`) and run any quick check that covers
   the changed files.
4. Commit, push, and open a pull request against the default branch. The
   description says what was added, where the image came from (generated, with
   the style; or the reused file), and that the README title now shows it.
   If the harness can link or track pull requests for this session, do so.

## 8. Report

Show one table: repository, icon (style or reused file), README change, pull
request link. Then mention:

- Apps that read the local checkout (T3 Code does) show the icon after the pull
  request is merged and the local checkout is updated. Offer to fast-forward
  local checkouts later, without switching branches that have work in progress.
- Where the working directory is, and that it can be deleted once the pull
  requests are merged.

## Rules

- Never commit to a default branch directly and never merge.
- Never overwrite an existing icon or rewrite a README title that already has an
  image without the user's explicit OK.
- Keep generated concepts out of the repositories; only the picked, resized icon
  is committed.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
