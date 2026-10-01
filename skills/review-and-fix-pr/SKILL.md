---
name: review-and-fix-pr
description: "Review the PR for this branch (Good/Bad/Ugly), comment the assessment on the PR, fix the issues worth addressing, then commit and push."
compatibility: "Requires git and the gh CLI (authenticated). Commits and pushes to the PR branch."
disable-model-invocation: true
---

Review the PR associated with this branch.

Use subagents only for scouting or supplemental research (if needed) — you are the primary reviewer and must do the review yourself.

1. Read the PR page in full with github CLI. Include description, all comments, all commits, and all changed files.
2. Identify any linked issues referenced in the PR body, comments, commit messages, or cross links. Read each issue in full, including all comments.
3. Analyze the PR diff. Read all relevant code files in full with no truncation from the current main branch and compare against the diff. Do not fetch PR file blobs unless a file is missing on main or the diff context is insufficient. Include related code paths that are not in the diff but are required to validate behavior.
4. Provide a structured review with these sections:
   - Good: solid choices or improvements
   - Bad: concrete issues, regressions, missing tests, or risks
   - Ugly: subtle or high impact problems
5. Add Questions or Assumptions if anything is unclear — ask only what blocks the review; otherwise state an assumption.
6. Add Change summary.

Output format per PR:
PR: <url>
Good:
- ...
Bad:
- ...
Ugly:
- ...
Questions or Assumptions:
- ...
Change summary:
- ...

If no issues are found, say so under Bad and Ugly.

Then of the bad & ugly issues (if any), give a verdict — fix, defer, or skip — with a one-line rationale, ordered by priority. Weigh user-visible impact, security, missing test coverage, fix cost vs. risk, and whether it blocks the PR's intent. Comment on the PR with this assessment.

Next, of the bad & ugly issues which you deem are worth addressing, go ahead and address these to best of your ability. When all done commit and push to branch.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
