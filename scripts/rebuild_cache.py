#!/usr/bin/env python3
"""Rebuild or incrementally update the issues SQLite cache from the filesystem.

Usage:
    python3 rebuild_cache.py          # incremental update
    python3 rebuild_cache.py --full   # full rebuild (drops and recreates)
"""

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, date
from pathlib import Path

import frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # scripts -> repo root (== CWD where the issue system lives)
CACHE_PATH = REPO_ROOT / ".issuescache.sqlite"  # derived cache, at the root of the repo (or worktree)
SKIP_DIRNAMES = {".git", "worktrees"}  # never descend into these when scanning for issues
EMAIL_RE = re.compile(r"(?<!\S)@([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
COMMENT_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.md$")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS issues (
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

CREATE TABLE IF NOT EXISTS comments (
    issue_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    author TEXT NOT NULL,
    created TEXT NOT NULL,
    handled INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (issue_id) REFERENCES issues(id)
);

CREATE TABLE IF NOT EXISTS mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id TEXT NOT NULL,
    comment_file_path TEXT,
    mentioned_email TEXT NOT NULL,
    handled INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (issue_id) REFERENCES issues(id)
);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_issues_dirs(repo_root: Path) -> list[Path]:
    """Find all `issues/` work-item directories anywhere in the repo.

    Skips `.git` and `worktrees/` (nested worktree checkouts have their own
    root-level cache and must not be ingested into this tree's cache).
    """
    result = []
    for dirpath, dirnames, _ in os.walk(repo_root):
        dirpath = Path(dirpath)

        # Never descend into these
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRNAMES]

        if dirpath.name == "issues" and dirpath != repo_root:
            result.append(dirpath)
            # Don't recurse into issues/ dirs (issues are flat, not nested)
            dirnames.clear()

    return result


def find_issue_folders(issues_dir: Path) -> list[Path]:
    """Find all issue folders inside an issues/ directory (direct children with task.md)."""
    result = []
    if not issues_dir.is_dir():
        return result
    for child in sorted(issues_dir.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            task_file = child / "task.md"
            if task_file.is_file():
                result.append(child)
    return result


def parse_task(task_path: Path) -> dict | None:
    """Parse a task.md file and return frontmatter dict, or None on failure."""
    try:
        post = frontmatter.load(str(task_path))
        return dict(post.metadata)
    except Exception:
        return None


def parse_comment(comment_path: Path) -> dict | None:
    """Parse a comment markdown file and return frontmatter dict, or None on failure."""
    try:
        post = frontmatter.load(str(comment_path))
        return dict(post.metadata)
    except Exception:
        return None


def extract_mentions(text: str) -> list[str]:
    """Extract all @email mentions from text."""
    return EMAIL_RE.findall(text)


def get_task_content(task_path: Path) -> str:
    """Read the full content of a task.md file."""
    try:
        return task_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def get_relative_path(path: Path) -> str:
    """Get the path relative to the repo root."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def get_folder_mtime(folder: Path) -> float:
    """Get the most recent mtime across task.md and comments/ in a folder."""
    mtime = 0.0
    task_file = folder / "task.md"
    if task_file.exists():
        mtime = max(mtime, task_file.stat().st_mtime)
    comments_dir = folder / "comments"
    if comments_dir.is_dir():
        for f in comments_dir.iterdir():
            if f.is_file() and f.suffix == ".md":
                mtime = max(mtime, f.stat().st_mtime)
    return mtime


# ---------------------------------------------------------------------------
# Required frontmatter fields
# ---------------------------------------------------------------------------

REQUIRED_TASK_FIELDS = {"id", "status", "priority", "assignee", "created"}
KNOWN_TASK_FIELDS = REQUIRED_TASK_FIELDS | {"parent"}


def normalize_timestamp(value) -> str:
    """Convert a value to an RFC 3339 string. PyYAML may parse timestamps to datetime objects."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"
    if isinstance(value, date):
        return f"{value.isoformat()}T00:00:00.000Z"
    return str(value)


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def drop_all(conn: sqlite3.Connection) -> None:
    """Drop all tables for a full rebuild."""
    conn.executescript("""
        DROP TABLE IF EXISTS mentions;
        DROP TABLE IF EXISTS comments;
        DROP TABLE IF EXISTS issues;
    """)
    conn.commit()


def get_cached_mtime(conn: sqlite3.Connection, issue_id: str) -> float | None:
    """Get the cached mtime for an issue, or None if not cached."""
    row = conn.execute(
        "SELECT folder_mtime FROM issues WHERE id = ?", (issue_id,)
    ).fetchone()
    return row[0] if row else None


def get_cached_issue_ids(conn: sqlite3.Connection) -> set[str]:
    """Get all issue IDs currently in the cache."""
    rows = conn.execute("SELECT id FROM issues").fetchall()
    return {row[0] for row in rows}


def get_handled_states(conn: sqlite3.Connection) -> dict:
    """Get all handled states for preservation during updates."""
    states = {
        "issues": {},
        "comments": {},
        "mentions": {},
    }
    for row in conn.execute("SELECT id, handled FROM issues").fetchall():
        states["issues"][row[0]] = row[1]
    for row in conn.execute("SELECT issue_id, file_path, handled FROM comments").fetchall():
        states["comments"][(row[0], row[1])] = row[2]
    for row in conn.execute(
        "SELECT issue_id, comment_file_path, mentioned_email, handled FROM mentions"
    ).fetchall():
        states["mentions"][(row[0], row[1], row[2])] = row[3]
    return states


def upsert_issue(
    conn: sqlite3.Connection,
    issue_id: str,
    folder_path: str,
    status: str,
    priority: str,
    assignee: str,
    parent_id: str | None,
    created: str,
    folder_mtime: float,
    extra_frontmatter: str | None,
    handled: int = 0,
) -> None:
    """Insert or replace an issue in the cache."""
    conn.execute(
        """INSERT OR REPLACE INTO issues
           (id, folder_path, status, priority, assignee, parent_id, created,
            folder_mtime, extra_frontmatter, handled)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (issue_id, folder_path, status, priority, assignee, parent_id,
         created, folder_mtime, extra_frontmatter, handled),
    )


def delete_issue(conn: sqlite3.Connection, issue_id: str) -> None:
    """Delete an issue and its comments/mentions from the cache."""
    conn.execute("DELETE FROM mentions WHERE issue_id = ?", (issue_id,))
    conn.execute("DELETE FROM comments WHERE issue_id = ?", (issue_id,))
    conn.execute("DELETE FROM issues WHERE id = ?", (issue_id,))


def upsert_comment(
    conn: sqlite3.Connection,
    issue_id: str,
    file_path: str,
    author: str,
    created: str,
    handled: int = 0,
) -> None:
    """Insert a comment into the cache."""
    conn.execute(
        """INSERT INTO comments (issue_id, file_path, author, created, handled)
           VALUES (?, ?, ?, ?, ?)""",
        (issue_id, file_path, author, created, handled),
    )


def upsert_mention(
    conn: sqlite3.Connection,
    issue_id: str,
    comment_file_path: str | None,
    mentioned_email: str,
    handled: int = 0,
) -> None:
    """Insert a mention into the cache."""
    conn.execute(
        """INSERT INTO mentions (issue_id, comment_file_path, mentioned_email, handled)
           VALUES (?, ?, ?, ?)""",
        (issue_id, comment_file_path, mentioned_email, handled),
    )


# ---------------------------------------------------------------------------
# Core rebuild logic
# ---------------------------------------------------------------------------


def process_issue(
    conn: sqlite3.Connection,
    issue_folder: Path,
    handled_states: dict,
) -> bool:
    """Process a single issue folder. Returns True if processed, False if skipped."""
    task_path = issue_folder / "task.md"
    meta = parse_task(task_path)
    if meta is None:
        return False

    issue_id = str(meta.get("id", ""))
    if not issue_id:
        return False

    folder_path = get_relative_path(issue_folder)
    folder_mtime = get_folder_mtime(issue_folder)

    # Check if we can skip (incremental mode)
    cached_mtime = get_cached_mtime(conn, issue_id)
    if cached_mtime is not None and folder_mtime <= cached_mtime:
        return False

    # Extract fields
    status = str(meta.get("status", "pending"))
    priority = str(meta.get("priority", "medium"))
    assignee = str(meta.get("assignee", ""))
    parent_id = str(meta.get("parent", "")) or None
    created = normalize_timestamp(meta.get("created", ""))

    # Extra frontmatter (keys beyond the known set)
    extra = {k: v for k, v in meta.items() if k not in KNOWN_TASK_FIELDS}
    extra_json = json.dumps(extra) if extra else None

    # Preserve handled state
    issue_handled = handled_states["issues"].get(issue_id, 0)

    # Delete existing data for this issue (will re-insert)
    delete_issue(conn, issue_id)

    # Insert issue
    upsert_issue(
        conn, issue_id, folder_path, status, priority, assignee,
        parent_id, created, folder_mtime, extra_json, issue_handled,
    )

    # Process mentions in task.md body
    task_content = get_task_content(task_path)
    for email in extract_mentions(task_content):
        mention_key = (issue_id, None, email)
        mention_handled = handled_states["mentions"].get(mention_key, 0)
        upsert_mention(conn, issue_id, None, email, mention_handled)

    # Process comments
    comments_dir = issue_folder / "comments"
    if comments_dir.is_dir():
        for comment_file in sorted(comments_dir.iterdir()):
            if not comment_file.is_file() or comment_file.suffix != ".md":
                continue

            comment_meta = parse_comment(comment_file)
            if comment_meta is None:
                continue

            comment_path = get_relative_path(comment_file)
            comment_author = str(comment_meta.get("author", ""))
            comment_created = normalize_timestamp(comment_meta.get("created", ""))

            # Preserve comment handled state
            comment_key = (issue_id, comment_path)
            comment_handled = handled_states["comments"].get(comment_key, 0)

            upsert_comment(
                conn, issue_id, comment_path, comment_author,
                comment_created, comment_handled,
            )

            # Process mentions in comment body
            comment_content = comment_file.read_text(encoding="utf-8")
            for email in extract_mentions(comment_content):
                mention_key = (issue_id, comment_path, email)
                mention_handled = handled_states["mentions"].get(mention_key, 0)
                upsert_mention(
                    conn, issue_id, comment_path, email, mention_handled,
                )

    return True


def rebuild(full: bool = False) -> None:
    """Main rebuild entry point."""
    conn = sqlite3.connect(str(CACHE_PATH))

    if full:
        print("Full rebuild: dropping all tables...")
        drop_all(conn)

    init_db(conn)

    # Save handled states before rebuild
    handled_states = get_handled_states(conn) if not full else {
        "issues": {}, "comments": {}, "mentions": {},
    }

    # Find all issues/ directories
    issues_dirs = find_issues_dirs(REPO_ROOT)

    # Track which issue IDs we see (for pruning deleted issues)
    seen_ids: set[str] = set()
    processed = 0
    skipped = 0

    for issues_dir in issues_dirs:
        for issue_folder in find_issue_folders(issues_dir):
            task_path = issue_folder / "task.md"
            meta = parse_task(task_path)
            if meta and meta.get("id"):
                seen_ids.add(str(meta["id"]))

            if process_issue(conn, issue_folder, handled_states):
                processed += 1
            else:
                skipped += 1

    # Prune deleted issues (in cache but no longer on disk)
    cached_ids = get_cached_issue_ids(conn)
    deleted_ids = cached_ids - seen_ids
    for deleted_id in deleted_ids:
        delete_issue(conn, deleted_id)

    conn.commit()

    # Summary
    total_issues = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    total_comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    total_mentions = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()[0]

    print(f"Cache updated: {CACHE_PATH}")
    print(f"  Issues:   {total_issues} total ({processed} updated, {skipped} unchanged, {len(deleted_ids)} pruned)")
    print(f"  Comments: {total_comments}")
    print(f"  Mentions: {total_mentions}")

    conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild the issues SQLite cache from the filesystem."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full rebuild (drop and recreate all tables).",
    )
    args = parser.parse_args()
    rebuild(full=args.full)


if __name__ == "__main__":
    main()
