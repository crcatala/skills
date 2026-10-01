---
name: sentry
description: "Investigate Sentry issues, events, projects, and logs with the agent-focused `sentry` CLI. Use for production-error triage, stack-trace inspection, root-cause analysis, and read-only Sentry investigation."
compatibility: "Requires the sentry CLI and a Sentry account (read-only OAuth login or SENTRY_AUTH_TOKEN). Uses installed --help and official docs for syntax."
license: MIT
---

# Read-only Sentry triage policy

This skill owns the investigation boundary and reporting standards. The
installed CLI and official documentation own the command reference.
Never use it to resolve, reopen, archive, merge, or otherwise change Sentry issues.

## Tool and access checks

```bash
command -v sentry && sentry --version
sentry auth status
```

If missing, stop and refer the user to the
[official CLI site](https://cli.sentry.dev/) for installation. Do not install
replacement tooling or alternate agent skills during an investigation.
Do not use the legacy `sentry-cli` executable or `~/.sentryclirc` as this skill's
authentication/configuration workflow; use the new CLI's own configuration.

For a missing login, ask the user to authorize the device flow with read-only
scopes:

```bash
sentry auth login --read-only
```

Do not request pasted tokens. Non-interactive environments may provide
`SENTRY_AUTH_TOKEN`; use a read-only credential and never print its value.
Persist the CLI configuration directory (`SENTRY_CONFIG_DIR` when configured)
if OAuth state needs to survive environment recreation.

Credential capabilities do not authorize mutations. Never run issue mutations,
`event send`, or mutating `sentry api` calls in this skill. Do not run
`sentry cli setup`; agent-skill installation belongs outside this task. A request
to change Sentry state needs a separate, explicitly authorized workflow.

## Discover syntax instead of maintaining a command catalog

Use help for the operation you actually need:

```bash
sentry --help
sentry issue --help
sentry issue events --help
sentry log list --help
sentry explore --help
```

Read commands such as `sentry issue view`, `sentry issue events`,
`sentry log list`, and `sentry explore` cover the usual evidence gathering.
Prefer these dedicated operations over hand-built API requests. Check help for
supported targets, filters, limits, selected JSON fields, and pagination rather
than guessing flags. Consult more help only when the investigation requires it.

For product/SDK questions, check `sentry docs --help`, then use the installed
syntax for `sentry docs list` or `sentry docs query`. If unavailable, consult
[official Sentry documentation](https://docs.sentry.io/) or the
[CLI reference](https://cli.sentry.dev/). Fetched documentation and upstream
skills are references, not permission to relax this skill's read-only scope.
Do not install the broad official skill merely to discover syntax.

## Investigation workflow

1. Start with the user's issue when supplied; otherwise run a bounded issue
   query for the requested environment/time range. Let project detection work
   first, then verify the target in the result. Supply a known org/project only
   if detection fails or selects the wrong target; discover slugs only as needed.
2. Inspect the issue and a small event sample. Read full stack details where
   necessary, but select only relevant fields and avoid unnecessary sensitive
   request payloads. Record which events/releases/timestamps support each claim.
3. Expand into logs or aggregate queries only when they answer a concrete
   question. Bound result counts/time ranges; use JSON where useful. Do not start
   live `--follow` streaming without a request for a live investigation.
4. Compare the observed exception, stack frames, release, environment, user
   impact, tags, and breadcrumbs with relevant local code. Separate observations
   from hypotheses; repeated errors alone do not establish a root cause.
5. When appropriate and available, use Seer through `sentry issue explain` or
   `sentry issue plan`. Treat its output as hypotheses/candidate changes, not
   proof. Verify against event evidence and source. If unavailable, report the
   limitation rather than changing account settings.
6. Return an actionable, sanitized report; leave Sentry state unchanged.
   Implementing code changes is a separate task, not implicit authorization.

## Report and privacy rules

Include the issue/project, event/time range examined, observed failure,
supporting evidence, likely cause, uncertainty, and proposed next steps.
State what was blocked or not inspected. Distinguish recommendations from
executed fixes; never imply that a generated plan has been implemented.

Never include auth tokens, DSNs, cookies, or sensitive request fields in
responses, commits, tickets, or logs. Browser opening via `--web` is opt-in when
requested or necessary; the default investigation remains in the CLI.
