---
name: github-pr-screenshots
description: Attach local screenshots, terminal captures, GIFs or video recordings (PNG, JPEG, GIF, WebP, SVG, MP4, MOV, WebM) to a GitHub pull request description or comment with the GitHub CLI's built-in --attach flag, and make a GIF with ffmpeg when one is asked for. Use when the user asks to upload, attach, add, or include screenshots, captures, GIFs, recordings or other images from testing in a PR.
compatibility: "Requires the gh CLI 2.99.0 or newer, authenticated with write access to the repository. Making a GIF from a video or frames needs ffmpeg."
---

# GitHub PR Screenshots

Use this skill after screenshots or captures exist locally (for example, from browser-based app testing or a terminal recording). Do not take screenshots unless the request calls for them. `{baseDir}` below means the directory containing this SKILL.md.

`gh` uploads each file to GitHub's user-attachments storage, the same place a file dragged into the web editor goes, and writes its URL into the PR body or comment. Nothing is committed to the repository. On a private repository only people with access can open the files; on a public one anyone with the URL can. An upload cannot be deleted from the command line, so check every file before it goes up.

## Requirements

```bash
gh pr comment --help | grep -q -- '--attach' && echo ok
```

If that prints nothing, `gh` is older than 2.99.0: report the installed version (`gh --version`) and stop. Do not fall back to an extension, to committing images, or to pushing them to a branch, ref, gist or outside host unless the user asks for that.

## Formats

`gh` accepts `.png`, `.jpg`/`.jpeg`, `.gif`, `.webp`, `.svg`, `.mp4`, `.mov` and `.webm`, and refuses anything else before uploading. Images may be up to 10 MB each. Video is limited by the account's plan (10 MB on free plans, up to 100 MB on paid ones), and the server refuses anything over.

Upload exactly the files that were created, in their original format. Do not rasterize, convert, re-encode, rename or resize them unless the user asks, or a GIF was asked for (next section).

- **SVG uploads as-is.** SVGs from a terminal recorder, such as `NAME.svg` (animated) and `NAME-still.svg`, go up unconverted. Embed the animated one when motion is the point (an interaction, a flow, a dialog opening) and the still for a static view. When unsure, embed the still, or both with a one-line caption each.
- **Previews are not deliverables.** A PNG made only to look at an SVG or a video frame is a throwaway. Never upload it in place of the original.
- **If an upload fails,** report the exact error and ask. Do not convert and retry on your own. If the user then asks for another format, say in your report what you changed it from and to.

## GIF or video

The two render differently in a PR:

- A **GIF** is an image: it plays inline on its own and loops, but it has no sound, at most 256 colours per frame, and the 10 MB image limit.
- An **MP4/MOV/WebM** renders as a video player the reader starts. It is sharper and much smaller for the same clip, and it can have sound.

Choose like this:

- **The user asks for a GIF:** deliver a GIF. If what exists is a video or a set of frames, make the GIF with ffmpeg following `{baseDir}/references/gif.md`, and say in your report that you made it and from what.
- **The user asks for a recording, clip or demo without naming a format:** a GIF when the clip is short (about 10 seconds or less), silent, and should play by itself where the reader is already looking. A video when it is longer, needs sound or fine detail, or a GIF of it would pass 10 MB. Upload the video as it was recorded.
- **A GIF over 10 MB:** re-encode it smaller as `references/gif.md` describes. If it still does not fit, ask whether to send the video instead. Never switch formats without saying so.
- **A terminal recording** is usually already an animated SVG, which plays inline like a GIF. Do not turn it into a GIF unless asked.

## Verify before uploading

Open each file once and check it before uploading: never attach a capture sight unseen. In particular:

- **Full-page captures:** `loading="lazy"` images below the fold render as blank areas unless the page was scrolled through before capturing. If the screenshot came from a browser tool's full-page capture, scroll the full page in increments first, return to the top, then capture.
- Confirm the intended page state (logged in or out, correct view or tab, no stray modals, tooltips or hover highlights) and that nothing sensitive is visible (tokens, emails, private data).
- **SVG, GIF and video:** look at a rasterized throwaway frame or two, then upload the original.
- Check sizes against the limits above (`ls -l` or `stat -c %s`).

## Upload and embed

1. Find the target PR. When it is not supplied, use the current branch's:
   ```bash
   gh pr view --json number --jq .number
   ```
   If no PR can be identified, ask the user for one.
2. Decide where the files go. If the request does not say whether they belong in the PR description or a comment, ask.
3. Write the markdown in a body file **in the same directory as the files**, referencing each one by a relative path where it should appear: `![Lobby with three phones](./lobby.png)` for an image. Put a video on a line of its own as a bare path, `./demo.mp4`. `gh` resolves paths in a `--body-file` against the file's own directory, then rewrites each reference to the uploaded URL. A file you attach but do not reference is appended at the end. Never write an upload URL by hand.
4. Run one command that uploads and writes the body, passing every file with `--attach` (repeat the flag; up to 50 files):
   - **Description:** start from the current body, so nothing in it is lost:
     ```bash
     gh pr view <PR> --json body --jq .body > <DIR>/body.md
     # append the new section, with its file references, to <DIR>/body.md
     gh pr edit <PR> --body-file <DIR>/body.md --attach <DIR>/lobby.png --attach <DIR>/demo.mp4
     ```
     To append images to the end of the description with no new text, `gh pr edit <PR> --attach <file>` alone keeps the current body.
   - **Comment** (testing evidence or a one-off update), with concise context around the images:
     ```bash
     gh pr comment <PR> --body-file <DIR>/comment.md --attach <DIR>/lobby.png
     ```
   - Alt text: write it in the body's reference, or after a `#` for an appended image (`--attach './lobby.png#Lobby with three phones'`). Video takes no alt text.
5. If some files upload and others fail, `gh` still writes the body with the ones that succeeded and exits non-zero. Report which failed and why. Do not rerun the whole command, which would upload the successful files a second time.

## Check the result

Read back what was written and confirm every file became an upload URL and no local path is left:

```bash
gh pr view <PR> --json body --jq .body | grep -n -E 'user-attachments|\./'
gh pr view <PR> --json comments --jq '.comments[-1].body'   # for a comment
```

Each image appears as `![alt](https://github.com/user-attachments/assets/<id>)` and each video as a bare `https://github.com/user-attachments/assets/<id>` line. On a private repository those URLs open only in a signed-in browser, so `curl` cannot confirm them; tell the user to open the PR to see that images render and animations play.

Report the PR number, where the files were added (description or comment), and each file's format, including any GIF you made and its source.

## When the upload is refused

- `attaching files requires write access to the repository`: the account cannot write to that repository. Report it and stop.
- An error from a sandboxed environment (for example `GitHub GraphQL is not available`, or an HTTP 415 or 403 from `uploads.github.com`): the environment's GitHub proxy or token does not allow uploads. Some GitHub App tokens are refused too. Report the exact error, say where the files are on disk, and stop.
