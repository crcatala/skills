---
name: review-pr-overengineering
description: "Assess whether the PR for this branch is overcomplicated, post classified findings as a PR comment, simplify the critical and worthwhile medium items, push, then update the comment."
compatibility: "Requires git and the gh CLI (authenticated). Commits and pushes to the PR branch."
disable-model-invocation: true
---

Review the PR associated with this branch. Try to understand it's scope and intent (read any associated tickets, planning docs if needed)

Now, I'd like you check if anything seems overly complex / overengineered in it's approach. Trying to see if there's any opportunities to simplify, if it's for sake of maintenance going forward. It could very well be the code architecture is justified/warranted to achieve it's intent/goal.

To be clear, we're not trying make merely MVP or spike, this is intended to be very usable going forward - so any simplifications suggested should have clear benefits (eg. for maintainability, avoid footguns and potential hard-to-debug bug scenarios, etc), not just reduce lines of code for the sake of it, nor creating even more abstractions, nor should you just be merely agreeing with my push to simplify. Really think through this and give honest assessment.

Give a breakdown of areas any aspects you found could may consider complex / overengineered, then label each with classification like "low", "medium", "critical" (like wtf is this this complex slop). If truly none are found, that's perfectly fine, just say so. Create a comment on the github PR with this assessment/breakdown first (comment even if there were none found, we're reporting our assessment for documentation purposes)

Then only after that assessment, if there happened to any critical aspects, go ahead and address those in the best way you can, making sure we are still preserving original intent of the PR. Similarly with medium issues found, use your best judgement to see which ones are actually worth addressing in this PR, then go ahead and make those changes as well. When done, you can commit and push to branch, then update the PR comment you made earlier with what was done (keep the asssessment in comment, just append notes of what you actually addressed, if any)

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
