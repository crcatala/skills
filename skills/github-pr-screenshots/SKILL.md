---
name: github-pr-screenshots
description: Upload local screenshots or captures (PNG, SVG, other image files) to a GitHub pull request with gh-attach and embed the returned markdown in the requested PR description or comment. Use when the user asks to upload, attach, add, or include screenshots, terminal captures or other images from testing in a PR.
compatibility: "Requires the gh CLI (authenticated) with the gh-attach extension."
---

# GitHub PR Screenshots

Use this skill after screenshots or captures have been created locally (for example, during browser-based app testing or a terminal recording). Do not take screenshots unless the request calls for them.

## Upload the files as produced

Upload exactly the files that were created, in their original format. Do not rasterize, convert, re-encode, rename or resize them unless the user asks.

- **SVG uploads as-is.** `gh attach` accepted `.svg` files and stored them unchanged (verified with gh-attach v0.6.0 on a private repo). SVGs from a terminal recorder, such as `NAME.svg` (animated) and `NAME-still.svg`, go in unconverted. Do not assume GitHub rejects a format; try it.
- **Previews are not deliverables.** A PNG you made only to look at an SVG (for example to check a frame) is a throwaway. Never upload it in place of the SVG.
- **Which SVG to embed:** the animated one when motion is the point (an interaction, a flow, a dialog opening); the still for a static view. When unsure, embed the still, or both with a one-line caption each.
- **If an upload fails,** report the exact error and ask. Do not convert and retry on your own. If the user does ask for a different format, say in your report that you changed it, and from what.

## Verify before uploading

Open each screenshot once and check it before uploading — never attach a capture sight unseen. In particular:

- **Full-page captures:** `loading="lazy"` images below the fold render as blank areas unless the page was scrolled through before capturing. If the screenshot came from a browser tool's full-page capture, scroll the full page in increments first, return to top, then capture.
- Confirm the intended page state (logged in vs. out, correct view/tab, no stray modals, tooltips, or hover highlights).
- **SVGs:** look at a rasterized throwaway copy (or open the file), then upload the original SVG, not the copy.

## Upload

1. Determine the target PR number. When it is not supplied, use the PR for the current branch:
   ```bash
   gh pr view --json number --jq .number
   ```
   If no PR can be identified, ask the user for one.
2. Verify that the expected GitHub CLI extension and pinned version are installed. If not, force-install the expected version:
   ```bash
   if ! gh extension list | awk -F '\t' '$1 == "gh attach" && $2 == "enthus-appdev/gh-attach" && $3 == "v0.6.0" { found = 1 } END { exit !found }'; then
     gh extension install enthus-appdev/gh-attach --pin v0.6.0 --force
   fi
   ```
3. Upload the actual local file or files and capture the markdown emitted by the command:
   ```bash
   gh attach <PR_NUMBER> /path/to/screenshot.png
   gh attach <PR_NUMBER> /path/to/demo.svg /path/to/demo-still.svg
   gh attach <PR_NUMBER> /path/to/screenshot-1.png /path/to/capture.svg
   ```

Use the exact markdown returned by `gh attach`; never construct image URLs or markdown manually.

## Add the screenshots to the PR

Put the returned markdown in the location the user requested:

- To update the PR description, retrieve the current body with `gh pr view <PR_NUMBER> --json body --jq .body`, append the relevant explanatory text and screenshot markdown, then update that same PR with `gh pr edit <PR_NUMBER> --body-file <FILE>`.
- To add testing evidence or a one-off update, post a comment on that same PR with `gh pr comment <PR_NUMBER> --body-file <FILE>`, including concise context and the screenshot markdown.
- If the request only says to upload a screenshot and does not name a destination, ask whether it should go in the PR description or a comment.

Report the PR number, where the files were added, and the format of each file uploaded. Keep the source files available until the upload succeeds.

## Check that the files were stored

On a private repo you cannot confirm an embed with `curl`: anonymous requests to the `github.com/<owner>/<repo>/blob/<sha>/<file>?raw=true` URLs return 404, and even an authenticated `curl` fails because those web URLs need a browser session. Check storage through the API instead, taking OWNER, REPO, SHA and FILE from the URL in the returned markdown:

```bash
gh api "repos/OWNER/REPO/contents/FILE?ref=SHA" --jq '{path, type, size}'
```

A result means the file is stored, not that it renders. For an animated SVG, tell the user to open the PR to confirm the image shows and animates.
