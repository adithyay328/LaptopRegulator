---
name: manage-issues
description: Use when you need to update issue status, add comments, change assignments, or manage existing issues in the this codebase.
---

# Manage Issues Skill

Use this skill to update, comment on, or manage existing issues.

## Working an Issue (spin-off to a worktree)

Working an issue **always** happens in a git worktree — mandatory, never optional.
The root metadata (`task.md` + hierarchy) is the shared, declarative layer on
`develop`; the running work log is internal context that lives in the worktree
until merge. **One agent works one issue (optionally its sub-issues) — never two
sibling issues.**

1. **Spin-off marker, on `develop`.** For the issue and *each* sub-issue in scope:
   - Add a comment: `Currently worked on in branch <top-uuid> (worktrees/<top-uuid>/).`
   - Set `status: in_progress` in `task.md`.
   Commit all of it as a **single commit on `develop`**. `<top-uuid>` is the UUID v7
   of the top issue of the subtree; sub-issues only point to it.
2. **Create the worktree and move in:**
   ```bash
   git worktree add -b <top-uuid> worktrees/<top-uuid>
   cd worktrees/<top-uuid>
   ```
3. **Work inside the worktree**, logging progress as comments (decisions, blockers,
   checkpoints) on the issue. These stay on the branch until merge.
4. **When finishing:** add a summary comment, set `status: done`, and commit on the
   `<top-uuid>` branch.
5. **Stop. Do NOT merge.** Leave the worktree in place. The user merges back to
   `develop` manually unless they explicitly ask you to do it.

## Updating an Issue

To update an issue, edit the YAML frontmatter in its `task.md` file.

### Change Status

Edit the `status` field. Valid values: `pending`, `in_progress`, `done`, `blocked`.

```yaml
---
id: 01967a3b-1234-7000-8000-000000000000
status: in_progress    # <-- changed from pending
priority: high
assignee: alice.smith@example.com
created: 2026-05-29T14:30:00.000Z
---
```

### Change Assignee

Update the `assignee` field to a valid email from `contributors.yaml`:

```yaml
assignee: bob.chen@example.com
```

### Change Priority

Update the `priority` field. Valid values: `high`, `medium`, `low`.

### Add a Parent Link

Set the `parent` field to the UUID v7 of the parent issue:

```yaml
parent: 01967a3c-5678-7000-8000-000000000000
```

### Add Arbitrary Metadata

You can add any extra keys to the frontmatter:

```yaml
---
id: 01967a3b-1234-7000-8000-000000000000
status: in_progress
priority: high
assignee: alice.smith@example.com
created: 2026-05-29T14:30:00.000Z
estimate_hours: 4
labels: [backend, scanning]
---
```

Extra keys are stored in the SQLite cache as a JSON blob in `extra_frontmatter`.

## Adding a Comment

Comments are separate markdown files inside a `comments/` subdirectory of the issue folder.

### Steps

1. Create the `comments/` directory if it does not exist:

```bash
mkdir -p initiatives/mvp2/issues/implement-scan-flow/comments
```

2. Create a comment file named with the current UTC timestamp:

**Filename format:** `YYYY-MM-DD-HH-MM-SS.md`

**Example:** `2026-05-29-14-30-00.md`

Generate the filename:

```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
print(now.strftime("%Y-%m-%d-%H-%M-%S") + ".md")
```

3. Write the comment with YAML frontmatter:

```markdown
---
author: alice.smith@example.com
created: 2026-05-29T14:30:00.000Z
---

Comment body in freeform markdown.

This addresses @bob.chen@example.com's question about the scan flow.
```

#### Comment Frontmatter

| Field | Required | Notes |
|---|---|---|
| `author` | yes | Email of the person writing the comment |
| `created` | yes | UTC RFC 3339 with ms precision |

### Mentions

Use `@email` in the comment body to mention someone:

```markdown
@alice.smith@example.com please review the validation agent changes.
```

Mentions are detected by `rebuild_cache.py` and tracked in the `mentions` table with a `handled` boolean.

## After Making Changes

After modifying issues or adding comments, validate first, then refresh the cache.
Lint is the gate; the cache is the derived artifact you only want built from valid
data. Both are stateless rebuilds of the current repo state — run them anytime.

```bash
python3 scripts/lint.py
python3 scripts/rebuild_cache.py
```

## Marking Items as Handled

Use `mark_handled.py` to acknowledge issues, comments, or mentions:

```bash
# Mark an issue as seen
python3 scripts/mark_handled.py --email you@example.com issue <uuid>

# Mark a comment as seen
python3 scripts/mark_handled.py --email you@example.com comment <comment-filename>

# Mark a mention as seen
python3 scripts/mark_handled.py --email you@example.com mention <mention-id>
```

Authorization rules:
- **Issues**: only the `assignee` can mark as handled
- **Comments**: only the `assignee` of the parent issue can mark as handled
- **Mentions**: only the `mentioned_email` can mark as handled

## Multimedia

To attach images, screenshots, or other binary files:

1. Upload the file to the GCP bucket `<your-bucket-name>` with an appropriate path prefix.
2. Reference it in the task.md or comment body as a standard markdown link:

```markdown
![screenshot](https://storage.googleapis.com/<your-bucket-name>/mvp2/screenshot-2026-05-29.png)
```

Do not commit binary files to git.

## Contributor Lookup

Valid emails are in `contributors.yaml` (at the repo root). Read this file to resolve names or nicknames to email addresses. Use fuzzy matching (edit distance) when a name does not exactly match.
