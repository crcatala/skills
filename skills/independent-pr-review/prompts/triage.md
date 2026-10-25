Of the bad & ugly issues, which are worth addressing?

Focus only on the Bad and Ugly sections of your review; ignore the Questions/Assumptions and Change summary sections.

For each issue, give a verdict — fix, defer, or skip — with a one-line rationale, ordered by priority. Weigh user-visible impact, security, missing test coverage, fix cost vs. risk, and whether it blocks the PR's intent. Recommend only; do not edit code.

Your reply is handed as-is to the agent that wrote the PR, which has not seen your review. Make it self-contained and concise:

PR: <url>
Action items:
1. [fix|defer|skip] <file:line or area> — <what is wrong, in one or two sentences> — <rationale>
2. ...

If there are no Bad or Ugly issues, say so in one line.
