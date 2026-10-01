---
name: review-branch-github
description: "Review all changes on the current branch against main and post the review as a comment on the associated GitHub PR."
compatibility: "Requires git and the gh CLI (authenticated)."
disable-model-invocation: true
---

If your harness provides a code-review subagent, delegate this task to it; otherwise do it yourself:

Review all changes on the current branch compared to main using `git diff main...HEAD`. Then post the review as a comment on the associated GitHub PR using `gh pr comment --body "..."`.

Important: Don't use `#` for numbered references in the comment as that links to GitHub issues. Use backticks instead (e.g., `` `2` ``).

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
