---
name: github-pr-screenshots
description: Upload local screenshots to a GitHub pull request with gh-attach and embed the returned image markdown in the requested PR description or comment. Use when the user asks to upload, attach, add, or include screenshots from app testing in a PR.
compatibility: "Requires the gh CLI (authenticated) with the gh-attach extension."
---

# GitHub PR Screenshots

Use this skill after screenshots have been created locally (for example, during browser-based app testing). Do not take screenshots unless the request calls for them.

## Verify before uploading

Open each screenshot once and check it before uploading — never attach a capture sight unseen. In particular:

- **Full-page captures:** `loading="lazy"` images below the fold render as blank areas unless the page was scrolled through before capturing. If the screenshot came from `agent-browser screenshot --full`, follow the scroll-through-then-capture recipe in the `agent-browser` skill (scroll the full page in increments, return to top, then capture).
- Confirm the intended page state (logged in vs. out, correct view/tab, no stray modals, tooltips, or hover highlights).

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
4. Upload the actual local file or files and capture the markdown emitted by the command:
   ```bash
   gh attach <PR_NUMBER> /path/to/screenshot.png
   gh attach <PR_NUMBER> /path/to/screenshot-1.png /path/to/screenshot-2.png
   ```

Use the exact markdown returned by `gh attach`; never construct image URLs or markdown manually.

## Add the screenshots to the PR

Put the returned markdown in the location the user requested:

- To update the PR description, retrieve the current body with `gh pr view <PR_NUMBER> --json body --jq .body`, append the relevant explanatory text and screenshot markdown, then update that same PR with `gh pr edit <PR_NUMBER> --body-file <FILE>`.
- To add testing evidence or a one-off update, post a comment on that same PR with `gh pr comment <PR_NUMBER> --body-file <FILE>`, including concise context and the screenshot markdown.
- If the request only says to upload a screenshot and does not name a destination, ask whether it should go in the PR description or a comment.

Report the PR number and where the screenshot was added. Keep the source screenshot file available until the upload succeeds.
