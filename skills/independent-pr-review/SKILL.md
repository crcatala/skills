---
name: independent-pr-review
description: "Get an independent review of this branch's PR from one or more other agents (codex, claude or pi, run in parallel without a UI with a configured model and effort), then assess their triaged findings yourself: which are valid and worth addressing."
compatibility: "Requires git, jq, the gh CLI (authenticated), and the CLI of each configured reviewer harness (codex, claude or pi). Reviewers run with full permissions and need network access."
disable-model-invocation: true
argument-hint: "[all | reviewer,... | harness:model[:effort]] [focus notes]"
---

Get an independent review of the PR for the current branch, then judge the
findings as the author. In the commands below, `{baseDir}` is the directory
containing this `SKILL.md`.

The reviewers are separate agent processes started by a bundled script. Each
one reads the PR in full, writes a Good/Bad/Ugly review, then triages its own
Bad and Ugly findings in a second turn of the same session. Only the triage
reply comes back to you. You never write the reviewer's prompt, so the review
is not shaped by your view of the work.

## Requirements

Check: `command -v git jq gh` plus the CLI for each reviewer harness (`codex`,
`claude` or `pi`); `gh auth status` must pass. If something is missing, tell
the user what to install and stop.

## Configuration

`${XDG_CONFIG_HOME:-~/.config}/independent-pr-review/config.json`, or the path
in `INDEPENDENT_PR_REVIEW_CONFIG`. Without a file, one built-in reviewer runs:
codex, `gpt-6.1-sol`, medium effort. See `{baseDir}/config.example.json`:

- `reviewers`: named reviewers, each `{harness, model, effort}`. `model` and
  `effort` are optional and passed as-is to the harness (codex
  `model_reasoning_effort`, claude `--effort`, pi `--thinking`).
- `default`: reviewer names used when none are requested. One is recommended.
- `timeout_minutes`: limit per turn (default 30).
- `keep_runs`: runs kept per branch; older ones are deleted after each run
  (default 10, `0` keeps all).

Results go to `<git common dir>/independent-pr-review/<branch>/<timestamp>/`:
inside `.git`, so they are never committed, shared by all worktrees, and out of
the reviewers' sight. Set `INDEPENDENT_PR_REVIEW_OUTPUT_DIR` to keep them
elsewhere instead (as `<dir>/<repo>/<branch>/<timestamp>/`).

`bash {baseDir}/scripts/run-review.sh --list` shows what is configured.

## Steps

1. **Pick reviewers from the invocation text.**
   - Nothing about reviewers: the configured default (no flag).
   - `all`, "all reviewers", "every reviewer": `--all`.
   - Configured names: `--reviewers name1,name2`.
   - Ad-hoc `harness:model[:effort]` (e.g. `codex:gpt-6.1-sol:high`): pass it
     in `--reviewers` too; it can be mixed with names.
   - A PR number or URL: `--pr <it>`. Otherwise the reviewer finds the PR for
     the current branch.
   - Any remaining text (focus areas, concerns): `--note "<text>"`. Do not add
     your own notes or opinions about the change.

   If a name is not configured, run `--list`, tell the user, and stop.

2. **Run the reviewers.** From the repository root, with the PR branch checked out:

   ```bash
   bash {baseDir}/scripts/run-review.sh [--all | --reviewers a,b] [--pr N] [--note "..."]
   ```

   Reviews usually take 5–20 minutes. Run it in the background if your harness
   can and wait for it to finish; otherwise run it in the foreground with a
   long command timeout (at least `timeout_minutes` × 2). Tell the user which
   reviewers started. Do not start other work on the branch while they run.
   Do not run reviewers yourself or replace a failed one with your own review.

3. **Read the results.** The script prints, per reviewer, either the paths of
   its `triage.md` and `review.md` and a resume command, or why it failed.
   Read every `triage.md`. Open `review.md` only when a triage item needs more
   detail. Report any failed reviewer with its reason and continue with the
   rest; if all failed, show the reasons and the log paths and stop.

4. **Show the triage.** Give the user the reviewers' action items, briefly. With
   several reviewers, merge duplicates and note which reviewers raised each.
   Do not wait for a reply; continue to the assessment.

5. **Assess as the author.** For each action item, check it against the code
   and what you know about the change. Is it real? Is it worth addressing now?
   Agreement between reviewers raises the priority of a finding but does not
   prove it; one reviewer can still be right alone. Give each item a verdict
   — fix, defer or skip — with a one-line reason, ordered by priority. Say
   where you disagree with a reviewer and why.

6. **Stop and recommend.** Do not change code unless the invocation text asked
   you to (for example "and fix what's worth fixing"). End with the list of
   output paths and resume commands so the user can inspect any reviewer's
   session.

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it as described in step 1.
