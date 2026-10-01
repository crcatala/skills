---
name: review-branch
description: "Review all changes on the current branch against main for quality, security and maintainability, and print the review without posting it anywhere."
disable-model-invocation: true
---

If your harness provides a code-review subagent, delegate this task to it; otherwise do it yourself:

Review all changes on the current branch compared to main. Use `git diff main...HEAD` to get the diff. Focus on code quality, security, and maintainability. Do NOT post to GitHub, just output the review.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
