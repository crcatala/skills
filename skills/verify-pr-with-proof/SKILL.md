---
name: verify-pr-with-proof
description: "Identify verification steps for the PR, comment them on the PR split into agent-safe and human-run, run the safe ones, fix any issues, and update the comment with results."
compatibility: "Requires git and the gh CLI (authenticated). Commits and pushes to the PR branch if fixes are needed."
disable-model-invocation: true
---

For the PR branch we're on, try to understand it's scope and intent in detail and what has been built.

Now, i'd like you to identify some manual steps and/or commands one could run through verify behavior of the work in in PR as proof. Don't run any of these steps just yet.

First, of the steps you identified, categorize them as either:
- safe / low-risk for an agent to help run on their own
- Recommend human run the step/command.

Post this assessment and list of verifcation steps as a comment on PR

Then only after that, you can go ahead with the safe / low-risk verification steps identified (if any), and help do those locally on this machine and report back findings. If any issues surface, try your best to address and fix them such that verification succeeds. After all steps confirmed verified behavior as expected, commit and push changes to PR branch (if this was needed at all).

Also update your PR comment from earlier with the status of those steps you tested.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
