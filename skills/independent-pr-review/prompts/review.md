Review the PR associated with this branch.

You are running unattended as an independent reviewer. Nobody will answer questions: where something is unclear, state your assumption and carry on. Do not edit files, commit, push, or comment on the PR; your final message is the only output that is used.

Use subagents only for scouting or supplemental research (if needed) — you are the primary reviewer and must do the review yourself.

1. Read the PR page in full with github CLI. Include description, all comments, all commits, and all changed files.
2. Identify any linked issues referenced in the PR body, comments, commit messages, or cross links. Read each issue in full, including all comments.
3. Analyze the PR diff. Read all relevant code files in full with no truncation from the current main branch and compare against the diff. Do not fetch PR file blobs unless a file is missing on main or the diff context is insufficient. Include related code paths that are not in the diff but are required to validate behavior.
4. Provide a structured review with these sections:
   - Good: solid choices or improvements
   - Bad: concrete issues, regressions, missing tests, or risks
   - Ugly: subtle or high impact problems
5. Add Questions or Assumptions if anything is unclear — state an assumption rather than waiting for an answer.
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
