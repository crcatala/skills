---
name: qa-verify-pr
description: "Plan and run QA verification of a PR's behavior against the locally running app using agent-browser, then record results and screenshots on the PR."
compatibility: "Requires the agent-browser and github-pr-screenshots skills and the gh CLI (authenticated)."
disable-model-invocation: true
---

We have the app running locally (if it's not, you can start it on your own in tmux so we can background and inspect it. look up docs for the appropriate script(s) to start the app locally). Now, I was wanting to see if we could do some QA verification steps with agent-browser to verify some of the behavior introduced in this PR.

First try to understand the scope of PR in detail (understand code changes as the PR description could be out of date).

Then come up with a plan on which high-value areas are worth doing a QA verification, then perform the testing. If it helps and applicable, we can also take screenshots (you can store in a temp location).

If all verification scenarios pass, update the PR description with the QA verification scenarios performed and results. Include screenshot markdown inline under the relevant scenario(s) when useful.

If some verification scenarios did NOT pass, post a comment on the PR with QA verification scenarios performed, results, and recommendations. Include screenshot markdown for failing evidence when useful.

When screenshots are needed, load and follow the `github-pr-screenshots` skill to upload and embed them.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
