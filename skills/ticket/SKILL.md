---
name: ticket
description: "Usage for the tk CLI (ticket system) — a git-backed, file-based issue tracker that stores tickets as markdown files with YAML frontmatter in a .tickets/ directory. Use when the user mentions filing tickets, epics, subtasks, or when a repo has a .tickets/ directory. Run `tk help` for the latest commands."
compatibility: "Requires git and the tk CLI (https://github.com/wedow/ticket)."
license: MIT
metadata:
  version: "1.0.0"
---

# Ticket (`tk`) — File-Based Issue Tracker

Ticket is a fast, portable issue tracker that stores tickets as markdown files
with YAML frontmatter in a `.tickets/` directory inside the repository.
Tickets are git-tracked alongside code, so branches carry their own work
history without needing an external API.

**Source:** <https://github.com/wedow/ticket>  
**CLI name:** `tk`

The command reference draws on the upstream MIT-licensed documentation; its
copyright and permission notice travel with this skill in
[THIRD_PARTY_NOTICE.md](THIRD_PARTY_NOTICE.md). Run `tk help` when the installed
version's commands differ from this reference.

---

## Installation Check

Before using `tk`, verify it's available:

```bash
command -v tk && tk --help >/dev/null
```

### If Not Installed

Install from source at a pinned, audited commit:
```bash
# Pinned to audited commit for supply-chain safety (do not change this hash):
TICKET_COMMIT=194b71a8bbc3771da1ce9f579395937c976bbddc
mkdir -p ~/.local/src \
  && git clone https://github.com/wedow/ticket.git ~/.local/src/ticket \
  && git -C ~/.local/src/ticket checkout --detach "$TICKET_COMMIT" \
  && ln -sf ~/.local/src/ticket/ticket ~/.local/bin/tk
```

You can also install via Homebrew or AUR — see
<https://github.com/wedow/ticket> for details.

---

## Workflow

### 1. Find work

```bash
tk ready                 # Open tickets with resolved dependencies
tk blocked               # Open tickets blocked by pending deps
tk ls                    # All tickets
tk show <id>             # Full detail (supports partial-ID matching)
```

### 2. Claim a ticket

```bash
tk start <id>            # Mark as in_progress
```

### 3. Make progress

```bash
tk add-note <id> "note text"   # Timestamped log entry (pipe via stdin too)
```

### 4. Complete

```bash
tk close <id>            # Mark as closed
```

### Commit convention

Always stage `.tickets/` alongside your code changes and reference the ticket
ID in the commit message when relevant:

```bash
git add .tickets/   # ship ticket state with code
git commit -m "feat: implement widget (closes nw-5c46)"
```

---

## All Commands

| Command | Description |
|---------|-------------|
| `tk create "Title"` | Create ticket (see options below) |
| `tk start <id>` | Set status to `in_progress` |
| `tk close <id>` | Set status to `closed` |
| `tk reopen <id>` | Set status to `open` |
| `tk status <id> <status>` | Set any status (`open`/`in_progress`/`closed`) |
| `tk show <id>` | Print ticket to stdout |
| `tk ls` | List all tickets |
| `tk ready` | Open tickets whose deps are all closed |
| `tk blocked` | Open tickets with unresolved deps |
| `tk closed [--limit=N]` | Recently closed (default 20, by mtime) |
| `tk add-note <id> [text]` | Append a timestamped note |
| `tk dep <id> <dep-id>` | Mark `<id>` as depending on `<dep-id>` |
| `tk dep tree [--full] <id>` | View dependency tree |
| `tk dep cycle` | Find dependency cycles in open tickets |
| `tk undep <id> <dep-id>` | Remove a dependency |
| `tk link <id> <id> [id...]` | Symmetric link between tickets |
| `tk unlink <id> <target-id>` | Remove a link |
| `tk super <cmd>` | Run a built-in command, bypassing plugins |

### `tk create` Options

| Flag | Description |
|------|-------------|
| `-d, --description` | Description text |
| `--design` | Design notes |
| `--acceptance` | Acceptance criteria |
| `-t, --type` | Type: `bug`, `feature`, `task`, `epic`, `chore` (default: `task`) |
| `-p, --priority` | Priority 0–4, 0=critical, 4=backlog (default: 2) |
| `-a, --assignee` | Assignee name (default: git user.name) |
| `--parent` | Parent ticket ID (for subtasks under an epic) |
| `--tags` | Comma-separated tags (e.g. `--tags ui,backend,urgent`) |
| `--external-ref` | External reference (e.g. `gh-123`, `JIRA-456`) |

---

## Ticket Format

Tickets are stored as `.tickets/<id>.md` with YAML frontmatter:

```yaml
---
id: nw-5c46
status: open
type: feature
priority: 2
created: 2026-01-15T10:00:00Z
assignee: Your Name
tags:
  - ui
dependencies: []
links: []
---
```

The body of the markdown file holds the description, design notes, acceptance
criteria, and timestamped notes appended via `tk add-note`.

---

## Project Integration

### With Ralph

Ralph 1.0.0 is campaign-only and ticket-native. Put the ordered delivery IDs
in the campaign's `deliveries` list with `source.type: tk`; do not use the old
`issue_tracker`/`prd.yaml` loop integration. Ralph's controller closes each
delivery ticket on its branch immediately before the first push, so an
implementation agent must not modify `.tickets/`.

### File Rules

- **For ordinary ticket work, stage `.tickets/` with related code changes.**
- **For Ralph campaign deliveries, do not modify or stage `.tickets/`; ticket
  closure is controller-owned.**
- Ticket IDs use a repo-specific prefix + 4-char random suffix
  (e.g., `nw-5c46`). Most commands support partial-ID matching
  so `tk show 5c46` works.
- Do **not** use a separate external tracker — tickets live in the repo.