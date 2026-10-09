#!/usr/bin/env python3
"""
DO NOT MODIFY THIS FILE
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
import argparse

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# names of file-editing tools across Claude Code, Codex, and VS Code; some editors ignore hook matchers, so we filter here
EDIT_TOOLS = {
    name.lower()
    for name in [
        "Edit",
        "Write",
        "MultiEdit",
        "NotebookEdit",
        "apply_patch",
        "create_file",
        "replace_string_in_file",
        "multi_replace_string_in_file",
        "insert_edit_into_file",
        "edit_notebook_file",
        "create_new_jupyter_notebook",
        "editFiles",
        "createFile",
        "create",
        "str_replace_editor",
        "str_replace_based_edit_tool",
    ]
}


def read_hook_input():
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def is_file_edit(hook_input):
    # editors that report a tool name only count file-editing tools; others (e.g. Cursor afterFileEdit) only fire on edits
    tool_name = hook_input.get("tool_name") or hook_input.get("toolName")
    if not tool_name:
        return True
    return str(tool_name).lower() in EDIT_TOOLS


def git(args, cwd=None, stdin=None):
    try:
        out = subprocess.run(
            ["git", *args],
            input=stdin,
            capture_output=True,
            timeout=10,
            check=False,
            cwd=cwd,
        )
        return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None
    except Exception:
        return None


def repo_root(hook_input):
    cwd = hook_input.get("cwd")
    out = git(["rev-parse", "--show-toplevel"], cwd=cwd if cwd and os.path.isdir(cwd) else None)
    return Path(out.strip()) if out else None


def head_commit(root):
    out = git(["rev-parse", "--verify", "-q", "HEAD"], cwd=root)
    return out.strip() if out else None


def dirty_paths(root):
    """Paths of tracked files with uncommitted changes, plus untracked files that aren't gitignored."""
    out = git(["ls-files", "-z", "--modified", "--others", "--exclude-standard"], cwd=root)
    return None if out is None else {p for p in out.split("\0") if p}


def blob_ids(root, paths):
    """git blob ids of the files' current contents; None for files that no longer exist."""
    existing = [p for p in sorted(paths) if (root / p).is_file()]
    out = git(["hash-object", "--stdin-paths"], cwd=root, stdin="\n".join(existing).encode("utf-8")) if existing else ""
    ids = dict(zip(existing, (out or "").split()))
    return {p: ids.get(p) for p in paths}


def tree_blob_ids(root, commit, paths):
    """git blob ids of the files as of a commit; None for files not in it."""
    ids = {}
    if commit and paths:
        out = git(["ls-tree", "-r", "-z", commit, "--", *sorted(paths)], cwd=root) or ""
        for entry in out.split("\0"):
            if "\t" in entry:
                meta, path = entry.split("\t", 1)
                ids[path] = meta.split()[2]
    return {p: ids.get(p) for p in paths}


def snapshot_path(root, hook_input):
    git_dir = git(["rev-parse", "--absolute-git-dir"], cwd=root)
    if not git_dir:
        return None
    key = "|".join(
        str(hook_input.get(k) or "")
        for k in ("session_id", "sessionId", "tool_use_id", "toolUseId", "turn_id")
    )
    snapshot_dir = Path(git_dir.strip()) / "ai-tracking"
    snapshot_dir.mkdir(exist_ok=True)
    return snapshot_dir / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")


def save_terminal_snapshot(hook_input):
    """Before a shell command runs, record the contents of every uncommitted file so we can tell what the command changed."""
    try:
        root = repo_root(hook_input)
        path = snapshot_path(root, hook_input) if root else None
        paths = dirty_paths(root) if path else None
        if paths is None:
            return
        for old in path.parent.glob("*.json"):  # clear out snapshots whose commands never reported back
            if time.time() - old.stat().st_mtime > 24 * 60 * 60:
                old.unlink()
        snapshot = {"time": time.time(), "head": head_commit(root), "files": blob_ids(root, paths)}
        path.write_text(json.dumps(snapshot), encoding="utf-8")
    except Exception:
        pass


def terminal_changed_files(hook_input, fallback_seconds=120):
    """
    After a shell command runs, return True if it appears to have created, changed, or deleted any files.
    Errs on the side of True: a duplicate log is better than a missed one.
    """
    try:
        root = repo_root(hook_input)
        if not root:
            return True
        path = snapshot_path(root, hook_input)
        snapshot = None
        if path and path.is_file():
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            path.unlink()
        now_dirty = dirty_paths(root) or set()
        if not snapshot:
            # no record of the files before the command; count any uncommitted file modified in the last couple of minutes
            return any(
                time.time() - (root / p).stat().st_mtime < fallback_seconds
                for p in now_dirty
                if (root / p).exists()
            )
        old_head, new_head = snapshot.get("head"), head_commit(root)
        candidates = set(snapshot["files"]) | now_dirty
        if old_head != new_head:  # the command committed, checked out, pulled, etc.
            diff = git(["diff", "--name-only", "-z", old_head or "", new_head or ""], cwd=root) if old_head and new_head else None
            candidates |= {p for p in (diff or "").split("\0") if p}
        before = tree_blob_ids(root, old_head, candidates - set(snapshot["files"]))
        before.update(snapshot["files"])
        after = blob_ids(root, candidates)
        changed = {p for p in candidates if after[p] != before.get(p)}
        if changed and old_head != new_head:
            # ignore files that merely match a commit that existed before the command (checkout, pull, reset)
            committed = git(["log", "-1", "--format=%ct", new_head], cwd=root) if new_head else None
            if committed and int(committed.strip()) < snapshot["time"] - 1:
                at_head = tree_blob_ids(root, new_head, changed)
                changed = {p for p in changed if after[p] != at_head[p]}
        return bool(changed)
    except Exception:
        return True


def git_config(key):
    try:
        out = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return (
            (out.stdout or "").strip().replace("\r", "") if out.returncode == 0 else ""
        )
    except Exception:
        return ""


def git_identity():
    """
    The name and email git would put on a commit.
    Environment variables take precedence over git config, as they do in git; GitHub Codespaces sets identity this way.
    """
    env = os.environ
    name = env.get("GIT_AUTHOR_NAME") or env.get("GIT_COMMITTER_NAME") or git_config("user.name")
    email = env.get("GIT_AUTHOR_EMAIL") or env.get("GIT_COMMITTER_EMAIL") or git_config("user.email")
    return name, email


def detect_environment():
    """Where this script is running: on a student's own computer, or on one of GitHub's servers."""
    env = os.environ
    if env.get("COPILOT_AGENT_JOB_ID") or env.get("COPILOT_AGENT_SESSION_ID"):
        return "copilot-coding-agent"
    if env.get("CODESPACES") == "true":
        return "codespaces"
    if env.get("GITHUB_ACTIONS") == "true":
        return "github-actions"
    return "local"


def send_event(event_type):
    """Post one event to the instructor's log; return True if it was received."""
    repository_url = git_config("remote.origin.url")
    author_name, author_email = git_identity()
    now = datetime.now()
    if sys.platform == "win32":
        current_date = now.strftime("%#m/%#d/%Y %H:%M:%S")
    else:
        try:
            current_date = now.strftime("%-m/%-d/%Y %H:%M:%S")
        except ValueError:
            current_date = now.strftime("%m/%d/%Y %H:%M:%S")
    payload = [
        {
            "repository_url": repository_url,
            "event_type": event_type,
            "author_name": author_name,
            "author_email": author_email,
            "date": current_date,
        }
    ]
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    url = config["url"]
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        urlopen(req, timeout=10)
        return True
    except (URLError, OSError):
        return False


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--event", default="agent", help="Event type (default: agent)")
    parser.add_argument(
        "--terminal",
        choices=["before", "after"],
        help="Track files changed by an agent's shell command: snapshot before it runs, compare after",
    )
    args = parser.parse_args()
    event_type = args.event

    hook_input = read_hook_input()
    if args.terminal == "before":
        save_terminal_snapshot(hook_input)
        print("{}")
        return
    if args.terminal == "after":
        if not terminal_changed_files(hook_input):
            print("{}")
            return
    elif not is_file_edit(hook_input):
        print("{}")
        return
    # Cursor can also run Claude Code's hooks; label those edits as Cursor's (an edit may be logged by both hooks)
    if event_type.startswith("claude") and os.environ.get("CURSOR_VERSION"):
        event_type = "cursor" + event_type[len("claude"):]
    send_event(event_type)
    print("{}")


if __name__ == "__main__":
    main()
    sys.exit(0)
