---
name: query-issues
description: Use when you need to search, query, or list issues. Covers status lookups, assignment queries, blocked items, issue trees, unread mentions, and completion rollups.
---

# Query Issues Skill

Use this skill to find and query issues across the codebase.

## Prerequisites

The SQLite cache at `.issuescache.sqlite` (repo root) must exist. If it does not, or if it might be stale, rebuild it first:

```bash
python3 scripts/rebuild_cache.py
```

Inside a git worktree the cache lives at that worktree's own root (`.issuescache.sqlite`), since the issue system is always rooted at the CWD.

If the cache is unavailable, fall back to filesystem grep (see Fallback section below).

## Querying the Cache

Open the cache with any SQLite client or via Python:

```python
import sqlite3
conn = sqlite3.connect(".issuescache.sqlite")
```

All paths in the database are relative to the repo root.

### Common Queries

**My unhandled issues:**
```sql
SELECT id, folder_path, status, priority, created
FROM issues
WHERE assignee = 'alice.smith@example.com' AND handled = 0
ORDER BY created DESC;
```

**All issues by status:**
```sql
SELECT id, folder_path, status, priority, assignee
FROM issues
WHERE status = 'blocked'
ORDER BY created DESC;
```

**All issues assigned to someone:**
```sql
SELECT id, folder_path, status, priority, created
FROM issues
WHERE assignee = ?
ORDER BY created DESC;
```

**Issue tree (all descendants of a parent):**
```sql
WITH RECURSIVE subtree AS (
    SELECT * FROM issues WHERE id = ?
    UNION ALL
    SELECT i.* FROM issues i JOIN subtree s ON i.parent_id = s.id
)
SELECT id, folder_path, status, priority FROM subtree;
```

**Completion rollup for a parent issue:**
```sql
SELECT
    parent_id,
    COUNT(*) AS total,
    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
    SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked
FROM issues
WHERE parent_id = ?
GROUP BY parent_id;
```

**Unread comments on my issues:**
```sql
SELECT c.file_path, c.author, c.created, i.folder_path
FROM comments c
JOIN issues i ON c.issue_id = i.id
WHERE i.assignee = ? AND c.handled = 0
ORDER BY c.created DESC;
```

**My unhandled mentions:**
```sql
SELECT m.id, m.issue_id, m.comment_file_path, i.folder_path
FROM mentions m
JOIN issues i ON m.issue_id = i.id
WHERE m.mentioned_email = ? AND m.handled = 0
ORDER BY m.id DESC;
```

**All issues in a specific directory:**
```sql
SELECT id, folder_path, status, priority, assignee
FROM issues
WHERE folder_path LIKE 'initiatives/mvp2/issues/%'
ORDER BY created DESC;
```

## Reading Issue Details

After finding an issue via the cache, read the full `task.md` for the description and context:

```
Read {repo_root}/{folder_path}/task.md
```

To see comments, list the `comments/` subdirectory inside the issue folder.

## Resolve an Issue by UID → Location

Issues are always referenced by their **`id` (UUID v7)**, never by path, and issue
folders never move. To turn a UID into its on-disk location, query the cache:

```sql
SELECT folder_path FROM issues WHERE id = ?;
```

If the cache is unavailable, fall back to ripgrep:

```bash
rg -l --glob 'task.md' '^id: <uuid>'
```

## Find Where an Issue Is Being Worked

When an issue is broken off into a worktree, the spin-off agent leaves a
**spin-off marker** comment on `develop`: `Currently worked on in branch <uuid>
(worktrees/<uuid>/).` To locate live work and resume from where it left off:

```bash
# Find the marker (and thus the branch / worktree) for an issue
rg -n 'Currently worked on in branch' <issue-folder>/comments/

# Then inspect the running work log inside that worktree
ls worktrees/<uuid>/
```

The full work log (decisions, blockers, checkpoints) lives on the `<uuid>` branch
in the worktree and only lands on `develop` when the branch is merged.

## Fallback: Filesystem Search

If the cache is unavailable, you can find issues by searching the filesystem:

1. Find all `issues/` directories:
   ```bash
   find . -type d -name issues -not -path './.git/*' -not -path './worktrees/*'
   ```

2. List issue folders in a specific issues/ directory:
   ```bash
   ls -d initiatives/mvp2/issues/*/
   ```

3. Search frontmatter across all issues:
   ```bash
   grep -r 'status: blocked' --include='task.md' */issues/
   ```

4. Find all issues assigned to someone:
   ```bash
   grep -rl 'assignee: alice.smith@example.com' --include='task.md' */issues/
   ```

The filesystem approach is slower but always works. Prefer the cache for complex queries (tree traversal, rollups, joins).
