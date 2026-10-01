---
name: triage-review-findings
description: "Decide which Bad and Ugly findings from a review are worth addressing (fix, defer or skip, with rationale, ordered by priority). Recommends only; edits no code."
disable-model-invocation: true
---

Of the bad & ugly issues, which are worth addressing?

Focus only on the Bad and Ugly sections of the review; ignore the Questions/Assumptions and Change summary sections.

For each issue, give a verdict — fix, defer, or skip — with a one-line rationale, ordered by priority. Weigh user-visible impact, security, missing test coverage, fix cost vs. risk, and whether it blocks the PR's intent. Recommend only; do not edit code.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
