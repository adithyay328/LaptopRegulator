---
name: create-issue
description: Use when you need to create a new issue. Handles folder creation, UUID v7 generation, task.md with proper frontmatter, and cache rebuild.
---

# Create Issue Skill

Use this skill to create a new issue in this codebase.

Issue creation is **declarative** and happens on the `develop` branch (the root,
shared layer): you are describing *what* needs doing and how it fits the hierarchy.
No worktree is needed to create an issue or to wire up parent/child links — that is
the declarative root. Worktrees come later, only when an issue is actually *worked*
(see the `manage-issues` skill).

## Steps

### 1. Determine Location

Issues live in `issues/` subdirectories throughout the codebase. Choose the right one:

- `initiatives/mvp2/issues/` — for work items within a given initiative

If the `issues/` directory does not exist in the target location, create it.

### 2. Generate UUID v7

Each issue needs a UUID v7 identifier. Generate one using Python:

```python
import uuid6
print(uuid6.uuid7())
```

Or via bash:

```bash
python3 -c "import uuid6; print(uuid6.uuid7())"
```

Make sure `uuid6` is installed: `pip install uuid6`

### 3. Create the Issue Folder

The folder name should be a **kebab-case slug** describing the issue:

```bash
mkdir -p initiatives/mvp2/issues/implement-scan-flow
```

Naming conventions:
- All lowercase
- Words separated by hyphens
- Descriptive but concise
- Examples: `build-drizzle-schema`, `fix-vectra-indexing`, `add-cookie-auth`

### 4. Write task.md

Create `task.md` inside the issue folder with YAML frontmatter and a markdown body:

```markdown
---
id: <generated-uuid-v7>
status: pending
priority: high
assignee: alice.smith@example.com
created: <current-utc-timestamp>
---

# Issue Title

Description of what needs to be done.

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
```

#### Frontmatter Fields

| Field | Required | Values |
|---|---|---|
| `id` | yes | UUID v7 (generated in step 2) |
| `status` | yes | `pending`, `in_progress`, `done`, `blocked` |
| `priority` | yes | `high`, `medium`, `low` |
| `assignee` | yes | Email address from `contributors.yaml` |
| `created` | yes | Current UTC time in RFC 3339 format: `YYYY-MM-DDTHH:MM:SS.sssZ` |
| `parent` | no | UUID v7 of parent issue (if this is a subtask) |

Extra arbitrary keys are allowed.

#### Timestamp Generation

```python
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z")
```

Or use the current time formatted as: `2026-05-29T14:30:00.000Z`

### 5. Validate, then Rebuild the Cache

Lint first (it is the gate), then refresh the cache from the now-valid data. Both
are stateless rebuilds of the current repo state — run them anytime.

```bash
python3 scripts/lint.py
python3 scripts/rebuild_cache.py
```

## Full Example

Creating a new issue for implementing the scan flow:

```bash
# Generate UUID
python3 -c "import uuid6; print(uuid6.uuid7())"
# Output: 01967a3b-1234-7000-8000-000000000000

# Create folder
mkdir -p initiatives/mvp2/issues/implement-scan-flow

# Write task.md (use your editor or agent Write tool)
# ... with the generated UUID, status: pending, etc.

# Validate, then rebuild cache
python3 scripts/lint.py
python3 scripts/rebuild_cache.py
```

## Creating a Subtask

To create a subtask, set the `parent` field to the UUID of the parent issue:

```yaml
---
id: 01967a3c-5678-7000-8000-000000000000
status: pending
priority: medium
assignee: alice.smith@example.com
created: 2026-05-29T15:00:00.000Z
parent: 01967a3b-1234-7000-8000-000000000000
---
```

The parent can be in any `issues/` directory — not restricted to the same folder. Convention: keep parent-child nesting to 2-3 levels max.

## Contributor Lookup

Valid assignee emails are listed in `contributors.yaml` (at the repo root). Read this file to find the right email for an assignee. If given a name or nickname, fuzzy match against the entries to find the corresponding email.
