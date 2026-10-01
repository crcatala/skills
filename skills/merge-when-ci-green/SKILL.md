---
name: merge-when-ci-green
description: "Check CI for the PR branch, fix failures and re-push until it is green, then merge with a merge commit via the GitHub CLI."
compatibility: "Requires git and the gh CLI (authenticated). Pushes fixes and merges the PR."
disable-model-invocation: true
---

For the PR branch we're on, we're pretty much done and i'd like to ensure CI is passing first before we consider merging.

Please check the CI status, and if it's green go ahead merge the PR (use merge commit strategy with github CLI).

If it is not yet green, please investigate, and and your best to fix/address any issues. Push fixes to branch and monitor CI until it is green. If needed do several cycles of this until it is actual green. Only then should you go ahead and proceed and merge the PR.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
