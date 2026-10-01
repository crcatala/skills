---
name: ralph
description: "Use Ralph for autonomous, ticket-native campaign delivery: ordered tk tickets, one PR per ticket, committed recipes and prompts, checks, merge, status, logs, and recovery."
compatibility: "Requires Node.js 22+, the ralph CLI (@crcatala/ralph-unpossible >= 1.0.0), tk, gh, git, and a pi runtime."
metadata:
  version: "3.0.0"
---

# Ralph — autonomous campaign delivery

Ralph runs an explicitly ordered list of trusted `tk` tickets. Each delivery is
one retained worktree/branch, one recipe run, and one pull request. The next
delivery starts only after Ralph proves that the previous PR merged on a
freshly fetched base branch.

The controller owns pinning, ticket closure, pushes, PR identity, required
checks, merge authority, and durable recovery. The project owns the campaign
manifest, recipe, and prompts.

- CLI/package: `ralph`, `@crcatala/ralph-unpossible`
- Requires Node.js 22+
- Default agent: Pi
- Ticket source: `tk` (`.tickets/`)

Do not guess flags or schema. Prefer `ralph <command> --help`, `ralph guide`,
and the files installed by `ralph init`.

## Pre-flight

Always verify the installed tool and project before changing or running it:

```bash
command -v ralph && ralph --version
ralph guide
ralph config show
ralph doctor
```

Require Ralph `>= 1.0.0`. If it is missing or older, stop and report an
environment mismatch rather than installing an ad hoc global copy that
bypasses your reviewed pin. Fix the environment (image, devcontainer, or
tool-version config) so it provides the reviewed Ralph pin, then verify the
command again.

Run from the repository root. `ralph doctor` must pass its required checks:
Node, Ralph home, project, complete Pi provider/model/thinking configuration,
and Pi's non-inference preflight. GitHub and `tk` checks are reported as
optional by doctor, but are required in practice for an autonomous PR
campaign.

Runtime configuration has no implicit model. Values resolve field-by-field:
CLI (where supported) → `.ralph/config.json` → `$RALPH_HOME/config.json`.
Configure all three values with the actual runtime you intend to use; do not
invent provider or model ids:

```bash
ralph config init --project --provider <actual-provider> --model <actual-model> --thinking <actual-level>
ralph config show
ralph doctor --json
```

Valid thinking levels are `off`, `minimal`, `low`, `medium`, `high`, and
`xhigh`. Use `high`/`xhigh` only when the selected model and provider support
it and cost/latency are acceptable. Credentials belong in the runtime
environment, not committed config.

## Set up a campaign

Install the editable standard recipe and prompts, then scaffold a campaign:

```bash
ralph init
ralph new my-campaign --epic <optional-tk-epic> \
  --ticket <first-ticket> --ticket <second-ticket>
```

`ralph init` is non-destructive: it installs missing files and keeps edited
ones. The project layout is:

```text
.ralph/
  config.json                         # optional project runtime config
  campaigns/<name>/campaign.yaml     # campaign manifest
  recipes/standard-pr.yaml            # editable delivery recipe
  prompts/implement.md               # editable agent prompts
  prompts/review-fix.md
  prompts/verify.md
  prompts/pr-description.md
```

A campaign manifest should look like this:

```yaml
version: 2
name: my-campaign
base_branch: main

source:
  type: tk
  epic: ru-epic                 # optional context only; never auto-closed

recipe: .ralph/recipes/standard-pr.yaml

pull_request:
  branch_template: "ralph/{{campaign}}/{{ticket}}"
  title_template: "{{ticket}}: {{ticket_title}}"
  draft: false

deliveries:                     # order is the dependency model
  - ticket: ru-first
  - ticket: ru-second
```

Only `{{campaign}}`, `{{ticket}}`, and `{{ticket_title}}` are valid template
placeholders. Delivery ticket ids must be unique and path-safe. Keep tickets
small enough for one independently reviewable PR. Ralph never infers,
decomposes, or reorders deliveries.

Before the first run, commit to the campaign `base_branch`:

- the campaign manifest;
- every delivery ticket and optional epic;
- the referenced recipe and all referenced prompts;
- `.ralph/config.json` when the project should pin the runtime selection.

The fetched base commit is the trust boundary. Local edits on a candidate
branch cannot change the active manifest, recipe, prompts, or trusted tickets.

## Recipe and prompts for autonomous delivery

The installed standard recipe provides this complete pipeline:

```text
implement (commit required)
→ open PR
→ review/fix (optional commit)
→ verify (optional commit)
→ draft PR description (no commit)
→ update PR
→ required checks
→ merge
```

Use the installed recipe as the base. For unattended runs, make these edits to
the copied `.ralph/recipes/standard-pr.yaml`:

1. Give every coding agent that may fix code (`implement`, `review-fix`, and
   `verify`) the full useful Pi tool set:

   ```yaml
   tools: [read, grep, find, ls, edit, write, bash]
   ```

   An explicit list is exact. Omitting `tools` uses the runner default and
   `tools: []` disables tools. `bash` does not grant GitHub, SSH,
   issue-tracker, or merge credentials.

2. Give implementation, review, and verification enough bounded time for the
   repository, such as `timeout: 45m` or `60m`. Keep the PR-description step
   read-only and shorter.

3. Preserve Git postconditions:

   - implementation: `git_head_advance: required`;
   - review/fix and verification: `git_head_advance: optional`;
   - PR description: `git_head_advance: forbidden`;
   - every agent/command step: `git_worktree_state: clean`.

   A code-changing agent must commit locally and leave a clean worktree. The
   PR-description step must not change HEAD.

4. Keep `github.required-checks` before the terminal merge step. For unattended
   delivery, configure the merge step as:

   ```yaml
   - id: merge
     uses: github.merge
     policy: auto
     method: merge
     require_up_to_date: true
   ```

   `policy: auto` requests a normal GitHub merge only when GitHub says the PR
   is ready. It never bypasses branch protection, required reviews, checks, or
   repository merge rules. Keep `pull_request.draft: false` for this path.

5. Keep review, verification, and PR-description as separate steps. A review
   or verification no-op is valid; do not manufacture commits. The starter
   verification prompt permits a minimal fix, so its tool allowlist must
   include `edit` and `write` if autonomous repair is wanted. Do not give the
   PR-description step mutation tools.

Customize prompts only with repository-specific build/test commands, coding
conventions, or scope constraints. Preserve these rules in every prompt:

- Acceptance Criteria are the source of truth; do not expand scope.
- Work only in the current delivery worktree.
- Commit code changes, but never push.
- Never edit `.tickets/`; ticket closure is controller-owned.
- Run focused and appropriate broader tests; leave a clean, forward-only HEAD.
- Report blockers honestly rather than asking a human to replay unknown work.

## Run procedure

Commit the campaign inputs on `base_branch`, then validate and inspect the
compiled plan before running:

```bash
ralph config show
ralph doctor
ralph validate my-campaign
ralph plan my-campaign
```

`validate` checks the manifest, recipe, prompts, tickets, and local
prerequisites. `plan` compiles the pinned delivery and recipe plan and may
fetch the base. Resolve every validation error and inspect the delivery order
and merge policy. A green doctor or validate does not prove GitHub can merge.

### Auto-merge preflight

Before an auto campaign run, verify GitHub authentication and required checks
on the configured campaign base branch:

```bash
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef
owner_repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
base_branch="<base_branch from campaign.yaml>"
gh api "repos/${owner_repo}/branches/${base_branch}/protection" \
  --jq '.required_status_checks.contexts[]?'
```

Inspect repository rulesets when classic branch protection returns 404. The
base branch must have the CI checks the recipe waits for. A required-check
step with zero GitHub-required checks is a no-gate; it does not create CI or
make auto-merge safe. Ensure automation can create/push PRs and repository
required approvals are satisfiable without a human-only step. Never bypass
protections or use an administrative merge. If this preflight fails, use
`policy: manual` and explain why.

After all inputs are committed and the preflight passes:

```bash
ralph run my-campaign
ralph status my-campaign --format json
```

Use `ralph plan` for planning; do not invent run flags. Configure runtime
selection through project/global config or a valid `runtime` block on each
agent recipe step.

`run` and `resume` use durable state. A healthy external wait returns success;
inspect status rather than relying on the exit code alone. For asynchronous CI,
merge queue, or GitHub mergeability:

```bash
ralph status my-campaign
ralph resume my-campaign
```

Resume after the external condition changes. Do not start a second `run` for a
campaign with existing durable state.

## Commands and machine-readable output

| Command | Purpose |
|---|---|
| `ralph init` | Install standard recipe, prompts, and campaign directories without overwriting edits |
| `ralph new <campaign>` | Scaffold a campaign (`--epic`, repeated `--ticket`, `--base-branch`) |
| `ralph validate <campaign>` | Validate manifest, recipe, prompts, tickets, and local prerequisites |
| `ralph plan <campaign>` | Compile and display the pinned delivery/recipe plan |
| `ralph run <campaign>` | Start a campaign, fetch/pin base, and execute deliveries in order |
| `ralph resume <campaign>` | Reconcile and continue durable state |
| `ralph status <campaign>` | Show merged count, active ticket/step, PR, last event, and next action |
| `ralph logs <campaign>` | Show/follow the append-only event ledger |
| `ralph abort <campaign>` | Stop while preserving retained work for inspection |
| `ralph config show/init` | Inspect or create provider/model/thinking configuration |
| `ralph doctor [--json]` | Read-only readiness diagnostics |

For automation, use `--format json` on `new`, `validate`, `plan`, `run`,
`resume`, `status`, and `abort`, plus `doctor --json`. Use
`ralph logs <campaign> --format jsonl --no-follow` for a stable event stream;
`logs` follows by default. Diagnostics go to stderr.

## Status, recovery, and evidence

Top-level states are:

- `waiting`: healthy external wait, such as CI, merge queue, or mergeability;
- `attention`: preserved partial/unknown-effect work or judgment is needed;
- `blocked`: Ralph proved an identity or safety invariant prevents progress;
- `aborted`: operator stopped the campaign; preserved work remains;
- `completed`: campaign finished.

On a non-completed run:

```bash
ralph status my-campaign --format json
ralph logs my-campaign --no-follow --verbose
ralph resume my-campaign
```

For `waiting`, resolve the external condition and resume. For `attention`,
inspect the retained worktree, last event, and verbose evidence; fix only what
is safe, commit/clean the worktree, then resume. For `blocked`, do not blindly
retry—read the diagnostic and correct the identity, repository, or policy
problem. `abort` preserves work but does not delete it.

Do not delete `state.json`, manually edit runtime state, or reset retained
worktrees. Runtime state, retained worktrees, transcripts, and attempt
artifacts live under `$RALPH_HOME` (normally `~/.ralph/`), not in the repository.
`state.json` is the resume authority and `events.jsonl` is the canonical history.

Ralph will not duplicate PR creation, merge requests, ticket closure, or
advance past an unproven merge. If a one-shot implementation leaves partial
work, Ralph enters `attention` rather than inventing another task iteration.
