#!/usr/bin/env python3
"""Validate all issues across the this codebase.

Checks frontmatter schemas, UUID v7 format, parent resolution, comment
conventions, and contributor email validation.

Usage:
    python3 lint.py
"""

import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

import frontmatter
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # scripts -> repo root (== CWD where the issue system lives)
CONTRIBUTORS_PATH = REPO_ROOT / "contributors.yaml"
SKIP_DIRNAMES = {".git", "worktrees"}  # never descend into these when scanning for issues

VALID_STATUSES = {"pending", "in_progress", "done", "blocked"}
VALID_PRIORITIES = {"high", "medium", "low"}

# UUID v7 regex: 8-4-4-4-12 hex, version nibble = 7, variant bits = 8/9/a/b
UUID_V7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Comment filename: YYYY-MM-DD-HH-MM-SS.md
COMMENT_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.md$")

# RFC 3339 timestamp with ms precision
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)

# Email
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_contributors() -> set[str]:
    """Load valid contributor emails from contributors.yaml."""
    if not CONTRIBUTORS_PATH.is_file():
        return set()
    try:
        with open(CONTRIBUTORS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, list):
            return set()
        return {entry["email"] for entry in data if isinstance(entry, dict) and "email" in entry}
    except Exception:
        return set()


def find_issues_dirs() -> list[Path]:
    """Find all issues/ directories in the repo."""
    result = []
    for dirpath, dirnames, _ in os.walk(REPO_ROOT):
        dirpath = Path(dirpath)
        # Never descend into these (worktrees have their own root-level system)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRNAMES]
        if dirpath.name == "issues" and dirpath != REPO_ROOT:
            # Only treat as an issues dir if it has subdirectories with task.md files
            # Skip any empty issues/ dirs
            if any((child / "task.md").is_file() for child in dirpath.iterdir() if child.is_dir()):
                result.append(dirpath)
            dirnames.clear()
    return result


def find_issue_folders(issues_dir: Path) -> list[Path]:
    """Find all issue folders inside an issues/ directory."""
    result = []
    if not issues_dir.is_dir():
        return result
    for child in sorted(issues_dir.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            result.append(child)
    return result


def relative(path: Path) -> str:
    """Return path relative to repo root."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class LintError:
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message

    def __str__(self) -> str:
        return f"  {self.path}: {self.message}"


def lint_task(issue_folder: Path, all_issue_ids: set[str], contributor_emails: set[str]) -> list[LintError]:
    """Lint a single issue's task.md."""
    errors: list[LintError] = []
    task_path = issue_folder / "task.md"
    rel_path = relative(task_path)

    # task.md must exist
    if not task_path.is_file():
        errors.append(LintError(relative(issue_folder), "Missing task.md"))
        return errors

    # Parse frontmatter
    try:
        post = frontmatter.load(str(task_path))
        meta = dict(post.metadata)
    except Exception as e:
        errors.append(LintError(rel_path, f"Failed to parse frontmatter: {e}"))
        return errors

    # Required fields
    for field in ("id", "status", "priority", "assignee", "created"):
        if field not in meta:
            errors.append(LintError(rel_path, f"Missing required field: {field}"))

    # id: must be valid UUID v7
    issue_id = str(meta.get("id", ""))
    if issue_id and not UUID_V7_RE.match(issue_id):
        errors.append(LintError(rel_path, f"Invalid UUID v7 for id: {issue_id}"))

    # status: enum check
    status = str(meta.get("status", ""))
    if status and status not in VALID_STATUSES:
        errors.append(LintError(
            rel_path,
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        ))

    # priority: enum check
    priority = str(meta.get("priority", ""))
    if priority and priority not in VALID_PRIORITIES:
        errors.append(LintError(
            rel_path,
            f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}",
        ))

    # assignee: email format + contributor check
    assignee = str(meta.get("assignee", ""))
    if assignee:
        if not EMAIL_RE.match(assignee):
            errors.append(LintError(rel_path, f"Invalid email format for assignee: {assignee}"))
        elif contributor_emails and assignee not in contributor_emails:
            errors.append(LintError(rel_path, f"Assignee not in contributors.yaml: {assignee}"))

    # created: RFC 3339 timestamp (PyYAML may parse it to a datetime object)
    created_raw = meta.get("created", "")
    if created_raw:
        if isinstance(created_raw, (datetime, date)):
            pass  # PyYAML parsed a valid timestamp — accept it
        elif isinstance(created_raw, str) and not RFC3339_RE.match(created_raw):
            errors.append(LintError(
                rel_path,
                f"Invalid timestamp for created: {created_raw}. Expected UTC RFC 3339 with ms precision.",
            ))

    # parent: must be valid UUID v7 and resolve to existing issue
    parent = meta.get("parent")
    if parent:
        parent_str = str(parent)
        if not UUID_V7_RE.match(parent_str):
            errors.append(LintError(rel_path, f"Invalid UUID v7 for parent: {parent_str}"))
        elif parent_str not in all_issue_ids:
            errors.append(LintError(rel_path, f"Parent UUID does not resolve to any issue: {parent_str}"))

    # Folder name: kebab-case check
    folder_name = issue_folder.name
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", folder_name):
        errors.append(LintError(rel_path, f"Folder name should be kebab-case: {folder_name}"))

    return errors


def lint_comments(issue_folder: Path, contributor_emails: set[str]) -> list[LintError]:
    """Lint all comments in an issue's comments/ directory."""
    errors: list[LintError] = []
    comments_dir = issue_folder / "comments"

    if not comments_dir.is_dir():
        return errors

    for item in sorted(comments_dir.iterdir()):
        if not item.is_file():
            continue

        rel_path = relative(item)

        # Filename convention
        if not COMMENT_FILENAME_RE.match(item.name):
            errors.append(LintError(
                rel_path,
                f"Comment filename must match YYYY-MM-DD-HH-MM-SS.md, got: {item.name}",
            ))

        # Only lint .md files
        if item.suffix != ".md":
            continue

        # Parse frontmatter
        try:
            post = frontmatter.load(str(item))
            meta = dict(post.metadata)
        except Exception as e:
            errors.append(LintError(rel_path, f"Failed to parse frontmatter: {e}"))
            continue

        # Required fields
        for field in ("author", "created"):
            if field not in meta:
                errors.append(LintError(rel_path, f"Missing required field: {field}"))

        # author: email format + contributor check
        author = str(meta.get("author", ""))
        if author:
            if not EMAIL_RE.match(author):
                errors.append(LintError(rel_path, f"Invalid email format for author: {author}"))
            elif contributor_emails and author not in contributor_emails:
                errors.append(LintError(rel_path, f"Author not in contributors.yaml: {author}"))

        # created: RFC 3339 timestamp (PyYAML may parse it to a datetime object)
        created_raw = meta.get("created", "")
        if created_raw:
            if isinstance(created_raw, (datetime, date)):
                pass  # PyYAML parsed a valid timestamp — accept it
            elif isinstance(created_raw, str) and not RFC3339_RE.match(created_raw):
                errors.append(LintError(
                    rel_path,
                    f"Invalid timestamp for created: {created_raw}. Expected UTC RFC 3339 with ms precision.",
                ))

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print(f"Linting issues across: {REPO_ROOT}")
    print()

    contributor_emails = load_contributors()
    if not contributor_emails:
        print("Warning: No contributors found in contributors.yaml")
        print()

    # First pass: collect all issue IDs for parent resolution
    all_issue_ids: set[str] = set()
    issues_dirs = find_issues_dirs()
    all_issue_folders: list[Path] = []

    for issues_dir in issues_dirs:
        for issue_folder in find_issue_folders(issues_dir):
            all_issue_folders.append(issue_folder)
            task_path = issue_folder / "task.md"
            if task_path.is_file():
                try:
                    post = frontmatter.load(str(task_path))
                    issue_id = str(post.metadata.get("id", ""))
                    if issue_id:
                        all_issue_ids.add(issue_id)
                except Exception:
                    pass

    # Second pass: lint everything
    all_errors: list[LintError] = []

    for issue_folder in all_issue_folders:
        all_errors.extend(lint_task(issue_folder, all_issue_ids, contributor_emails))
        all_errors.extend(lint_comments(issue_folder, contributor_emails))

    # Report
    if not all_issue_folders:
        print("No issues found.")
        print()

    if all_errors:
        print(f"Found {len(all_errors)} error(s):")
        print()
        for error in all_errors:
            print(error)
        print()
        sys.exit(1)
    else:
        print(f"All clear. {len(all_issue_folders)} issue(s) validated, 0 errors.")
        sys.exit(0)


if __name__ == "__main__":
    main()
