#!/usr/bin/env python3
"""
Sync todo.txt tasks and git commit history to the project Trello board.

Usage:
    export TRELLO_API_KEY=<your_key>
    export TRELLO_TOKEN=<your_token>
    python3 helper/trello/sync_trello.py

What it does:
  - Reads todo.txt and creates cards in "Backlog"
  - Reads git log and creates backdated cards in "Done"

Duplicate protection: skips cards whose name already exists in the target list.
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import requests

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("TRELLO_API_KEY")
TOKEN   = os.environ.get("TRELLO_TOKEN")

LIST_BACKLOG = "6976367ecf3955d7ab485529"  # Backlog
LIST_DONE    = "6969e6fef5eddf8f9e10eea2"  # Done

BASE_URL = "https://api.trello.com/1"
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
TODO_PATH = os.path.join(REPO_ROOT, "todo.txt")

# ── Helpers ───────────────────────────────────────────────────────────────────
def auth():
    return {"key": API_KEY, "token": TOKEN}


def get_existing_card_names(list_id: str) -> set[str]:
    r = requests.get(f"{BASE_URL}/lists/{list_id}/cards", params=auth())
    r.raise_for_status()
    return {c["name"].strip() for c in r.json()}


def create_card(list_id: str, name: str, desc: str = "", due: str | None = None):
    payload = {**auth(), "idList": list_id, "name": name, "desc": desc}
    if due:
        payload["due"] = due
    r = requests.post(f"{BASE_URL}/cards", params=payload)
    r.raise_for_status()
    print(f"  [+] {name}")


# ── 1. todo.txt → Backlog ─────────────────────────────────────────────────────
def sync_todo(existing: set[str]):
    print("\n── todo.txt → Backlog ──")
    with open(TODO_PATH) as f:
        lines = f.read().splitlines()

    # Group lines: a non-indented line is a task title; indented lines are desc
    tasks: list[tuple[str, str]] = []
    current_title = None
    current_desc_lines: list[str] = []

    for line in lines:
        if not line.strip():
            continue
        if line.startswith(" ") or line.startswith("\t"):
            current_desc_lines.append(line.strip().lstrip("- "))
        else:
            if current_title:
                tasks.append((current_title, "\n".join(current_desc_lines)))
            current_title = line.strip().lstrip("0123456789. ")
            current_desc_lines = []
    if current_title:
        tasks.append((current_title, "\n".join(current_desc_lines)))

    added = 0
    for title, desc in tasks:
        if title in existing:
            print(f"  [skip] {title}")
            continue
        create_card(LIST_BACKLOG, title, desc)
        added += 1
    print(f"  {added} card(s) created.")


# ── 2. Git history → Done ─────────────────────────────────────────────────────
# Commits to skip (merge commits, trivial)
SKIP_PATTERNS = re.compile(
    r"^(Merge pull request|Merge branch|initial commit|wip|tweak|noted?\.?$)",
    re.IGNORECASE,
)

def parse_git_log() -> list[dict]:
    """Return list of {title, body, date_iso} from git log."""
    sep = "|||GIT_SEP|||"
    fmt = f"%s{sep}%b{sep}%aI"
    result = subprocess.run(
        ["git", "log", "--no-merges", f"--pretty=format:{fmt}"],
        capture_output=True, text=True,
        cwd=REPO_ROOT,
    )
    entries = []
    for block in result.stdout.strip().split("\n"):
        parts = block.split(sep)
        if len(parts) != 3:
            continue
        subject, body, date = parts
        subject = subject.strip()
        if not subject or SKIP_PATTERNS.match(subject):
            continue
        # Clean up conventional commit prefix for card title
        title = re.sub(r"^(feat|fix|chore|docs|refactor|test|style)\([^)]*\):\s*", "", subject, flags=re.IGNORECASE)
        title = title.strip().capitalize()
        entries.append({"title": title, "body": body.strip(), "date": date.strip()})
    return entries


def sync_git(existing: set[str]):
    print("\n── Git history → Done ──")
    commits = parse_git_log()
    added = 0
    for c in commits:
        if c["title"] in existing:
            print(f"  [skip] {c['title']}")
            continue
        desc = c["body"] if c["body"] else ""
        create_card(LIST_DONE, c["title"], desc, due=c["date"])
        added += 1
    print(f"  {added} card(s) created.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not API_KEY or not TOKEN:
        print("ERROR: set TRELLO_API_KEY and TRELLO_TOKEN environment variables.")
        sys.exit(1)

    print("Fetching existing cards...")
    backlog_existing = get_existing_card_names(LIST_BACKLOG)
    done_existing    = get_existing_card_names(LIST_DONE)

    sync_todo(backlog_existing)
    sync_git(done_existing)
    print("\nDone!")


if __name__ == "__main__":
    main()
