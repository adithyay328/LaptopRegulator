#!/usr/bin/env python3
"""Mark an issue, comment, or mention as handled in the SQLite cache.

Usage:
    python3 mark_handled.py --email you@example.com issue <uuid>
    python3 mark_handled.py --email you@example.com comment <comment-filename>
    python3 mark_handled.py --email you@example.com mention <mention-id>
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_PATH = Path(__file__).resolve().parent.parent / ".issuescache.sqlite"  # scripts -> repo root -> .issuescache.sqlite

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_cache() -> sqlite3.Connection:
    """Open the cache database, or exit if it doesn't exist."""
    if not CACHE_PATH.is_file():
        print(f"Error: Cache not found at {CACHE_PATH}")
        print("Run rebuild_cache.py first.")
        sys.exit(1)
    return sqlite3.connect(str(CACHE_PATH))


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_issue(conn: sqlite3.Connection, email: str, uuid: str) -> None:
    """Mark an issue as handled."""
    row = conn.execute(
        "SELECT assignee, handled, folder_path FROM issues WHERE id = ?", (uuid,)
    ).fetchone()

    if row is None:
        print(f"Error: No issue found with id: {uuid}")
        sys.exit(1)

    assignee, handled, folder_path = row

    if assignee != email:
        print(f"Error: You ({email}) are not the assignee ({assignee}) of issue {uuid}")
        print(f"  Location: {folder_path}")
        sys.exit(1)

    if handled:
        print(f"Issue {uuid} is already marked as handled.")
        return

    conn.execute("UPDATE issues SET handled = 1 WHERE id = ?", (uuid,))
    conn.commit()
    print(f"Marked issue as handled: {uuid}")
    print(f"  Location: {folder_path}")


def handle_comment(conn: sqlite3.Connection, email: str, comment_filename: str) -> None:
    """Mark a comment as handled."""
    # Find the comment by filename (should be globally unique due to timestamp)
    row = conn.execute(
        """SELECT c.issue_id, c.file_path, c.handled, i.assignee
           FROM comments c
           JOIN issues i ON c.issue_id = i.id
           WHERE c.file_path LIKE ?""",
        (f"%/{comment_filename}",),
    ).fetchone()

    if row is None:
        # Try exact match
        row = conn.execute(
            """SELECT c.issue_id, c.file_path, c.handled, i.assignee
               FROM comments c
               JOIN issues i ON c.issue_id = i.id
               WHERE c.file_path = ?""",
            (comment_filename,),
        ).fetchone()

    if row is None:
        print(f"Error: No comment found matching: {comment_filename}")
        sys.exit(1)

    issue_id, file_path, handled, assignee = row

    if assignee != email:
        print(f"Error: You ({email}) are not the assignee ({assignee}) of the parent issue")
        print(f"  Comment: {file_path}")
        sys.exit(1)

    if handled:
        print(f"Comment is already marked as handled: {file_path}")
        return

    conn.execute(
        "UPDATE comments SET handled = 1 WHERE issue_id = ? AND file_path = ?",
        (issue_id, file_path),
    )
    conn.commit()
    print(f"Marked comment as handled: {file_path}")


def handle_mention(conn: sqlite3.Connection, email: str, mention_id: str) -> None:
    """Mark a mention as handled."""
    try:
        mid = int(mention_id)
    except ValueError:
        print(f"Error: mention-id must be an integer, got: {mention_id}")
        sys.exit(1)

    row = conn.execute(
        "SELECT issue_id, comment_file_path, mentioned_email, handled FROM mentions WHERE id = ?",
        (mid,),
    ).fetchone()

    if row is None:
        print(f"Error: No mention found with id: {mid}")
        sys.exit(1)

    issue_id, comment_file_path, mentioned_email, handled = row

    if mentioned_email != email:
        print(f"Error: You ({email}) are not the mentioned person ({mentioned_email})")
        sys.exit(1)

    if handled:
        print(f"Mention {mid} is already marked as handled.")
        return

    conn.execute("UPDATE mentions SET handled = 1 WHERE id = ?", (mid,))
    conn.commit()

    location = comment_file_path or f"issue {issue_id} (task.md body)"
    print(f"Marked mention as handled: id={mid}")
    print(f"  In: {location}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mark an issue, comment, or mention as handled."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Your email address (for authorization).",
    )

    subparsers = parser.add_subparsers(dest="type", required=True)

    issue_parser = subparsers.add_parser("issue", help="Mark an issue as handled")
    issue_parser.add_argument("uuid", help="UUID v7 of the issue")

    comment_parser = subparsers.add_parser("comment", help="Mark a comment as handled")
    comment_parser.add_argument("filename", help="Comment filename (e.g., 2026-05-29-14-30-00.md)")

    mention_parser = subparsers.add_parser("mention", help="Mark a mention as handled")
    mention_parser.add_argument("mention_id", help="Mention ID (integer from mentions table)")

    args = parser.parse_args()
    conn = ensure_cache()

    if args.type == "issue":
        handle_issue(conn, args.email, args.uuid)
    elif args.type == "comment":
        handle_comment(conn, args.email, args.filename)
    elif args.type == "mention":
        handle_mention(conn, args.email, args.mention_id)

    conn.close()


if __name__ == "__main__":
    main()
