# AGENTS.md — Git-Native Issue & Initiative System (Template)

This repository is a **reusable, agents-only template** for tracking work directly
in git. There is no JIRA, no external tracker, and no human-facing README — the
interface is agents reading and writing this filesystem. Every product you build
forks this template and evolves it; generalizable practices get merged back here
into the core.

This file is the single canonical specification. It covers two things:

1. **The Issue Tracking System** — how work items are represented, validated, and worked.
2. **Initiatives** — isolated workspaces for experiments, research, and building systems.

Read this file in full before interacting with issues or initiatives.

---

## Git-Native Issue Tracking System

Git is the source of truth for all work items. Any folder in the codebase can
contain an `issues/` subdirectory. Inside that directory, each issue is a folder
with a standardized `task.md` file. The folder name is the human-readable issue
name (kebab-case). The `task.md` contains YAML frontmatter (the structured,
validated layer) and a freeform markdown body (description, context, notes).

Issues can have comments (separate markdown files) and can reference parent issues
via UUID links. There are no "epics" — an epic is just an issue that other issues
point to via `parent`.

### The `develop` Branch: Live on Head

The trunk is **`develop`**, and it always represents the latest piece of code that
is safe to push — the "live on head" model. Live-on-head is only dangerous if your
code practices are dangerous. Here they are not, because:

- **The linter is the gate.** `develop` is always kept in a green, lint-passing
  state. `scripts/lint.py` is what makes "always pushable" true. You never refresh
  the cache from invalid data: lint first, then rebuild.
- **You do not merge directly into `develop`.** Work happens on per-issue worktree
  branches and a human re-reads the change before it lands. The one exception is
  the lightweight **spin-off marker** (below), which is trivial and must be visible
  immediately, so it commits straight to `develop`.

### Declarative Root vs. Worktree Working Context

There are two layers to the system, and keeping them distinct is the whole point:

- **The root (on `develop`) is declarative.** The `task.md` frontmatter + body and
  the parent/child hierarchy describe *what* we are working on and *how the work
  decomposes*. This is the shared, everyone-sees-it layer. Issues are created and
  the hierarchy is wired up here, on `develop`.
- **The worktree owns the working context.** Once an issue is broken off into a
  worktree to be worked, the running narrative of *how the work is going* —
  decisions, blockers, progress checkpoints — is internal state that lives on the
  issue's branch and only lands back on `develop` when you merge. The worktree
  subagent is responsible for that context; other people do not need it in real
  time.

A single short **spin-off marker** comment is the one piece that crosses back
immediately (committed to `develop`) so that anyone can see *where* an issue is
being worked. Everything else the worker writes stays in the worktree until merge.

References between issues are always by **`id` (UUID v7)**, never by path. Issue
folders are immutable once created — do not rename or move them. To resolve a
UID to its location, query the cache (`SELECT folder_path FROM issues WHERE id=?`)
or fall back to ripgrep.

### File Structure

The issue system lives at the **repo root** — the same directory as the rest of
the codebase (the current working directory). It is not nested inside an `issues/`
folder. "Issues" is always assumed to be rooted at the CWD.

```
# Repo root (== CWD; the issue system shares this directory with the codebase)
AGENTS.md                            <- you are here (canonical spec)
contributors.yaml                    <- team members (name, nicknames, email)
.gitignore                           <- ignores .issuescache.sqlite, __pycache__/
.issuescache.sqlite                  <- derived SQLite cache (gitignored, at repo root)
scripts/
  requirements.txt
  rebuild_cache.py                   <- build/update cache from filesystem
  lint.py                            <- validate all issues across codebase
  mark_handled.py                    <- mark issues/comments/mentions as handled
skills/
  query-issues/SKILL.md              <- agent skill: search and query issues
  create-issue/SKILL.md              <- agent skill: create new issues
  manage-issues/SKILL.md             <- agent skill: update, comment, assign
worktrees/                           <- per-issue git worktrees (gitignored)
  .gitignore                         <- ignores everything in here except itself
  <issue-uuid-v7>/                   <- a worktree checkout for one issue

# Work-item issues live in `issues/` directories anywhere in the codebase
initiatives/
  example-initiative/
    AGENTS.md            # Initiative summary + structure + conventions
    issues/
      some-issue-name/
        task.md
        comments/
          2026-05-29-14-30-00.md
```

### task.md Frontmatter Schema

Every `task.md` must have YAML frontmatter delimited by `---` with these required fields:

```yaml
---
id: 01967a3b-1234-7000-8000-000000000000   # UUID v7 (required, globally unique)
status: pending                              # required: pending | in_progress | done | blocked
priority: high                               # required: high | medium | low
assignee: you@example.com                    # required: email address
created: 2026-05-29T14:30:00.000Z           # required: UTC RFC 3339 with ms precision
parent: 01967a3c-5678-7000-8000-000000000000 # optional: UUID v7 of parent issue
---

Freeform markdown description of the issue.

Can include @you@example.com mentions and GCP links for multimedia.
```

#### Field Details

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID v7 | yes | Time-sortable unique identifier. Generated once at creation. |
| `status` | enum | yes | One of: `pending`, `in_progress`, `done`, `blocked` |
| `priority` | enum | yes | One of: `high`, `medium`, `low` |
| `assignee` | email | yes | Email address of the person responsible |
| `created` | timestamp | yes | UTC RFC 3339 with ms precision (global convention) |
| `parent` | UUID v7 | no | Links to another issue anywhere in the codebase |

Arbitrary extra keys are allowed in frontmatter. The linter only validates the required fields.

#### UUID v7

Issue IDs use **UUID v7**, not v4. UUID v7 is time-sortable — the timestamp is
encoded in the first 48 bits, so issues benefit from chronological ordering.

The `uuid6` Python package provides `uuid6.uuid7()` for generation.

#### Parent Links

The `parent` field references another issue by its UUID v7. The parent can be in
any `issues/` directory in the codebase — it is not restricted to the same
directory. This allows cross-cutting hierarchy (e.g., a nested work-item can have
a parent in an initiative-level issue).

Convention: do not nest more than 2-3 levels deep. Keep the hierarchy shallow.

### Comment Convention

Comments live in a `comments/` subdirectory inside an issue folder. Each comment
is a separate markdown file.

#### Comment Filename

```
YYYY-MM-DD-HH-MM-SS.md
```

UTC time, matching the global timestamp convention but formatted for filesystem
compatibility. Example: `2026-05-29-14-30-00.md`

#### Comment Frontmatter

```yaml
---
author: you@example.com
created: 2026-05-29T14:30:00.000Z
---

Comment body in freeform markdown.

Can include @teammate@example.com mentions and GCP links.
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `author` | email | yes | Who wrote the comment |
| `created` | timestamp | yes | UTC RFC 3339 with ms precision |

### Mentions

Use `@email` syntax in markdown bodies (task descriptions or comments) to mention someone:

```markdown
@you@example.com the scan flow is ready for review.
```

The Python scripts detect `@email` patterns and track them in the SQLite cache.
Mentions are tracked in the `mentions` table with a `handled` boolean.

### Multimedia

Binary files (images, photos, documents) are stored in a GCP bucket and referenced
as standard markdown links:

```markdown
![screenshot](https://storage.googleapis.com/<your-bucket-name>/<project>/screenshot-2026-05-29.png)
```

- **Bucket**: `<your-bucket-name>` (single org-wide bucket)
- **Path prefix**: organized by initiative/project (e.g., `<your-bucket-name>/<project>/...`)
- Do not commit binary files to git. Always use GCP links.

### SQLite Cache

The file `.issuescache.sqlite` at the **repo root** is a **derived read cache**
built from the filesystem. It is gitignored. Each developer or agent rebuilds it
locally using `scripts/rebuild_cache.py`. Inside a git worktree the cache lives at
that worktree's own root (`<worktree>/.issuescache.sqlite`), since the issue system
is always rooted at the CWD.

The cache enables fast queries (parent-child traversal, assignment lookup, mention
tracking) without walking the filesystem.

#### Cache Schema

```sql
CREATE TABLE issues (
  id TEXT PRIMARY KEY,
  folder_path TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  assignee TEXT,
  parent_id TEXT,
  created TEXT NOT NULL,
  folder_mtime REAL NOT NULL,
  extra_frontmatter TEXT,
  handled INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (parent_id) REFERENCES issues(id)
);

CREATE TABLE comments (
  issue_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  author TEXT NOT NULL,
  created TEXT NOT NULL,
  handled INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (issue_id) REFERENCES issues(id)
);

CREATE TABLE mentions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_id TEXT NOT NULL,
  comment_file_path TEXT,
  mentioned_email TEXT NOT NULL,
  handled INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (issue_id) REFERENCES issues(id)
);
```

#### Handled Semantics

| Table | `handled` relative to | Meaning |
|---|---|---|
| `issues` | The `assignee` | Has the assignee seen/acknowledged this issue? |
| `comments` | The issue's `assignee` | Has the assignee seen this comment on their issue? |
| `mentions` | The `mentioned_email` | Has the mentioned person seen this mention? |

`handled` defaults to `0` (false). Use `scripts/mark_handled.py` to flip it to `1`.

#### Incremental Updates

`rebuild_cache.py` compares each `task.md` file's mtime against `folder_mtime` in
the cache. Only changed files are re-parsed. `handled` state is preserved for
existing entries. Use `--full` to force a complete rebuild.

### Scripts

All scripts are in `scripts/` (at the repo root) and require Python 3.10+. Install dependencies:

```bash
pip install -r scripts/requirements.txt
```

#### rebuild_cache.py

Builds or incrementally updates `.issuescache.sqlite` from the filesystem.

```bash
python3 scripts/rebuild_cache.py                # incremental update
python3 scripts/rebuild_cache.py --full          # full rebuild
```

#### lint.py

Validates all issues across the codebase. Exits 0 on success, 1 on errors.

```bash
python3 scripts/lint.py
```

Checks:
- Every issue folder has a `task.md`
- Required frontmatter fields present with valid types/values
- `id` is valid UUID v7
- `parent` UUID resolves to an existing issue
- Comment filenames match `YYYY-MM-DD-HH-MM-SS.md`
- Comment frontmatter has required fields
- Assignee/author emails exist in `contributors.yaml`

#### mark_handled.py

Marks an issue, comment, or mention as handled. Requires your email for authorization.

```bash
python3 scripts/mark_handled.py --email you@example.com issue <uuid>
python3 scripts/mark_handled.py --email you@example.com comment <comment-filename>
python3 scripts/mark_handled.py --email you@example.com mention <mention-id>
```

Errors out if you are not the assignee (issues/comments) or the mentioned person (mentions).

### Skills

Agent skills for interacting with the issue system are in `skills/` (at the repo
root). These are loaded on demand, not in main context.

- **`query-issues`** — Search and query issues using the SQLite cache or filesystem fallback.
- **`create-issue`** — Create a new issue with proper folder structure and frontmatter.
- **`manage-issues`** — Update issue status, add comments, change assignment.

### Contributors

The file `contributors.yaml` in this directory lists all team members with their
name, nicknames, and email. Agents should use this file for:

- Resolving nicknames/names to email addresses (fuzzy match by edit distance)
- Validating assignee and author fields

### For Agents

When working with issues:

1. Read this file first for the full system specification.
2. Load the appropriate skill from `skills/` for the operation you need.
3. After any change to issues, run `python3 scripts/lint.py` to validate, then
   `python3 scripts/rebuild_cache.py` to refresh the cache. Lint is the gate;
   the cache is the derived artifact you only want built from valid data. Both
   are stateless rebuilds of the current repo state — run them anytime.
4. To resolve a person's name to their email, read `contributors.yaml` and fuzzy match.

### Working an Issue

Working an issue **always** happens in a git worktree — this is mandatory, never
optional. The point is isolation: every change for an issue is confined to one
branch, and anyone can `cd worktrees/<uuid>/` to see exactly what is going on.

**One agent works one issue (optionally its sub-issues) — never two sibling
issues.** A spin-off is scoped to a single subtree of the hierarchy.

The procedure:

1. **Spin-off marker (on `develop`).** For the issue and *each* of its sub-issues
   in scope:
   - Add a short comment: `Currently worked on in branch <top-uuid> (worktrees/<top-uuid>/).`
   - Set `status` to `in_progress` in `task.md`.
   Commit all of this as a **single commit on `develop`**. The branch/worktree is
   named after the **top issue's UUID v7** of the subtree; sub-issues just point
   to it. This marker is the one bit of working context that crosses back
   immediately, so others know where the work lives.
2. **Create the worktree and move in:**
   ```bash
   git worktree add -b <top-uuid> worktrees/<top-uuid>
   cd worktrees/<top-uuid>
   ```
3. **Work inside the worktree.** Use the issue's `comments/` directory as a running
   work log — this is internal working context that stays on the branch until
   merge:
   - Decisions made and the reasoning behind them.
   - Blockers encountered and how you resolved (or didn't resolve) them.
   - Progress checkpoints — what's done so far.

   **Comment early and often.** Everything an agent learns in its context window is
   tribal knowledge that needs to be stored in comments so that someone else can
   find it later. Context windows are ephemeral; disk space is cheap. When in doubt,
   write it down in a comment. Others should be able to pick up the work solely
   from the issue's comments — not from your context window.
4. **When finishing:** add a comment summarizing what was completed, what remains,
   and any context the next agent (or your future self) will need. Set `status` to
   `done`. Commit on the `<top-uuid>` branch.
5. **Stop and hand off. Do NOT merge.** Leave the worktree in place for inspection.
   The user merges the branch back to `develop` manually — unless they explicitly
   ask you to perform the merge. Only after a merge does `develop`'s cache reflect
   the work (rebuild it then).

This practice ensures:
- Another agent can find live work via the spin-off marker, then resume from the
  worktree's comments where you left off.
- A supervisor can understand exactly what happened without asking.
- The issue itself becomes a complete record of the work, not just a description
  of what was requested.

### Spin-off Sub-agents Through the Issue System

When you need to delegate work to a sub-agent, prefer going through the issue system:

1. **Spin off a sub-issue** for the delegated work. Write a clear `task.md` describing
   what needs to be done and why.
2. **Point the sub-agent at that issue** and instruct it to spin off its own worktree
   and work the issue. The sub-agent should follow the same procedure: spin-off marker,
   worktree, comments, etc.
3. The sub-agent's progress and decisions get captured in that sub-issue's comments,
   keeping everything inside the issue system where it can be found later.

**Only use ad hoc sub-agents for very specific, self-contained tasks where spinning
up a full issue/worktree cycle would be disproportionate.** For anything that involves
meaningful decisions, research, or follow-up work, go through the issue system.

This keeps all tribal knowledge in the shared record and lets any agent (or human)
pick up any piece of work by reading the relevant issue comments.

### Git Worktrees

Parallel work on individual issues happens in git worktrees. The convention:

- Worktrees live **inside this repo**, in the `worktrees/` directory, as
  `worktrees/<issue-uuid-v7>/`. They are **not** siblings of the repo.
- Both the worktree folder name and its **branch name** are the issue's UUID v7.
- The `worktrees/` directory is gitignored (`worktrees/.gitignore` ignores
  everything except itself), so worktree checkouts never get committed into the
  main tree and the main repo's cache never ingests them.
- **The issue system is always rooted at the CWD — including inside a worktree.**
  A worktree is a full checkout, so it has its own `scripts/`, `skills/`,
  `contributors.yaml`, and its own root-level `.issuescache.sqlite`. Run the
  scripts from within the worktree; they operate on that worktree's checkout.
- Create one with:
  ```bash
  git worktree add -b <issue-uuid-v7> worktrees/<issue-uuid-v7>
  ```
- When working in a worktree, still log progress as comments on the issue — the
  issue files are part of the repo and visible in the worktree.
- **Do not merge automatically.** When the work is committed on the `<issue-uuid-v7>`
  branch, stop and leave the worktree in place. The user merges back to `develop`
  manually unless they explicitly ask you to do it. After a merge, remove the
  worktree (`git worktree remove worktrees/<issue-uuid-v7>`) and run
  `python3 scripts/rebuild_cache.py` on the main checkout to update the cache.

---

## Initiatives

Each initiative is an **independent piece of work** — a workspace for experiments,
research, or building out systems that may or may not end up in the final project.
The name is literal: an initiative is an endeavor you want to isolate, iterate on,
and capture tribal knowledge from.

### Why Isolated Workspaces?

Most projects involve work where:

- You don't know the answer upfront (research-oriented)
- You want to experiment freely without polluting the main codebase
- The end result might be thrown away or need a complete rewrite
- Code quality doesn't matter — learning matters

Initiatives solve this by providing **isolated codebases** where you can:

- Write messy, experimental code
- Capture decisions, blockers, and progress as comments
- Break work down into issues within the initiative
- Eventually **compose** successful work into the main system

Examples:
- *"Hey, this might be cool to explore"* → spin up an initiative
- A design or hardware experiment
- A message bus prototype
- Pre-integration research
- Any exploratory work that might not pan out

### Structure

Every initiative lives at:

```
initiatives/<kebab-name>/
  AGENTS.md              # Summary + structure + conventions for this initiative
  issues/                # (optional) Issues specific to this initiative
  ...                    # Whatever code, docs, or files the initiative needs
```

Each initiative's `AGENTS.md` should contain:

- **What it is** — one-paragraph summary of the initiative's purpose
- **Where everything is** — links to key files/folders in the initiative
- **Structure** — how the initiative is organized
- **Conventions** — any special conventions or patterns used within this initiative

### For Agents

To understand an initiative quickly, spin off a sub-agent:

> Go read `initiatives/<name>/AGENTS.md` and the overall structure, then report back
> with a summary of what this initiative is, what's been done, and what's left to do.

The sub-agent can be given context about what piece of the codebase to look at
alongside the AGENTS.md.
