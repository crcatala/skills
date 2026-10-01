---
name: update-pr-description
description: "Rewrite the PR description for this branch with a concise layman's summary, the why, the impact, and a representative example command or config with its output."
compatibility: "Requires git and the gh CLI (authenticated)."
disable-model-invocation: true
---

For the PR branch we're on, try to understand it's scope and intent in detail and what has been built.

Then in layman's terms, i'd like to know what's the concise summary of the work we've done so far, the why, and impact going forward and/or what it unlocks/enables?

Then i'm also curious if there any representative command(s) and/or configuration(s) that we built that would be worth sharing as example in the PR description summary somewhere (and it's example output) so we have an idea what was built?

Then, Let's go ahead update the PR description something similar to what you shared. You can replace most of the existing PR description, particularly the summary. If there are technical details or other information already in the PR descripiton you think are worth keeping, you can leave that as-is (though i'd like things to be fairly concise and not overwhelm with too many details).

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
