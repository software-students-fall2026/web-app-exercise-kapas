#!/usr/bin/env python3
"""
One-time setup for the automations in this repository.  Run it from anywhere inside the repository:
    python3 .automations/setup.py    (Mac/Linux)
    python .automations/setup.py     (Windows)

DO NOT MODIFY THIS FILE
"""

import argparse
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

AUTOMATIONS_DIR = Path(__file__).resolve().parent

# where each supported AI coding tool is usually installed, and the approval step only the student can give
HOME = Path.home()
LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
PROGRAM_FILES = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
AGENTS = [
    {
        "id": "claude-code",
        "name": "Claude Code",
        "installed_label": "command line",
        "commands": ["claude"],
        "files": [HOME / ".local" / "bin" / "claude", HOME / ".local" / "bin" / "claude.exe", HOME / ".claude" / "local" / "claude"],
        "extensions": ["anthropic.claude-code-"],
        "approval": "Start Claude Code in this folder and accept the prompt to trust it. Type /hooks to see the hooks that run.",
    },
    {
        "id": "codex",
        "name": "Codex",
        "installed_label": "command line or app",
        "commands": ["codex"],
        "files": [Path("/Applications/Codex.app"), HOME / "Applications" / "Codex.app"],
        "extensions": ["openai.chatgpt-"],
        "approval": "Start Codex in this folder, type /hooks, and approve this project's hooks.",
    },
    {
        "id": "vscode-copilot",
        "name": "VS Code / GitHub Copilot",
        "installed_label": "VS Code app",
        "commands": ["code"],
        "files": [
            Path("/Applications/Visual Studio Code.app"),
            HOME / "Applications" / "Visual Studio Code.app",
            LOCAL_APP_DATA / "Programs" / "Microsoft VS Code" / "Code.exe",
            PROGRAM_FILES / "Microsoft VS Code" / "Code.exe",
            Path("/usr/share/code/code"),
            Path("/snap/bin/code"),
        ],
        "extensions": ["github.copilot-"],
        "approval": "Open this folder and choose to trust it when asked. Agent hooks are on unless the `chat.useHooks` setting is off.",
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "installed_label": "Cursor app",
        "commands": ["cursor"],
        "files": [
            Path("/Applications/Cursor.app"),
            HOME / "Applications" / "Cursor.app",
            LOCAL_APP_DATA / "Programs" / "cursor" / "Cursor.exe",
            Path("/usr/share/cursor/cursor"),
            Path("/opt/Cursor/cursor"),
        ],
        "extensions": [],
        "approval": "Open this folder and choose to trust it when asked. Hooks load from .cursor/hooks.json.",
    },
]

# per-user extension folders of VS Code and the editors built on it
EXTENSION_DIRS = [
    ("VS Code", HOME / ".vscode" / "extensions"),
    ("VS Code Insiders", HOME / ".vscode-insiders" / "extensions"),
    ("Codespaces/remote VS Code", HOME / ".vscode-remote" / "extensions"),
    ("Codespaces/remote VS Code", HOME / ".vscode-server" / "extensions"),
    ("Cursor", HOME / ".cursor" / "extensions"),
]

def git(args, cwd=AUTOMATIONS_DIR):
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10, check=False, cwd=cwd
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def find_agent(agent):
    """Return the ways an AI coding tool appears to be installed, e.g. ["command line", "VS Code extension"]."""
    found = []
    if any(shutil.which(command) for command in agent["commands"]) or any(
        path.exists() for path in agent["files"]
    ):
        found.append(agent["installed_label"])
    for editor, folder in EXTENSION_DIRS:
        try:
            names = [d.name.lower() for d in folder.iterdir()] if folder.is_dir() else []
        except OSError:
            names = []
        if any(name.startswith(prefix) for name in names for prefix in agent["extensions"]):
            label = f"{editor} extension"
            if label not in found:
                found.append(label)
    return found


def load_tracker():
    spec = importlib.util.spec_from_file_location(
        "give_student_credit", AUTOMATIONS_DIR / "give-student-credit.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def activate_git_hooks(root):
    """Point git at the .githooks directory and make sure the hooks are executable."""
    if git(["config", "core.hooksPath", ".githooks"], cwd=root) is None:
        return False
    if sys.platform != "win32":  # Windows runs git hooks through Git Bash without needing this
        for hook in (root / ".githooks").iterdir():
            if hook.is_file() and not hook.suffix:
                hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--from-commit-hook",
        action="store_true",
        help="Run by the commit-msg hook the first time it fires",
    )
    args = parser.parse_args()

    root = git(["rev-parse", "--show-toplevel"])
    git_dir = git(["rev-parse", "--absolute-git-dir"])
    if not root or not git_dir:
        print("Could not find the git repository. Run this from inside your clone of the repository.")
        return 1
    root, marker = Path(root), Path(git_dir) / "ai-tracking" / "setup-done"

    print("Setting up the automations in this repository...\n")
    problems, notes = [], []
    tracker = load_tracker()

    environment = tracker.detect_environment()
    if environment == "codespaces":
        print(f"[ok] running in GitHub Codespaces ({os.environ.get('CODESPACE_NAME', 'unnamed codespace')})")
        notes.append(
            "Each codespace is a separate copy of the repository, so run this setup again in every new codespace."
        )
    elif environment in ("copilot-coding-agent", "github-actions"):
        problems.append(
            "This is running on GitHub's servers (Copilot coding agent or GitHub Actions), not on your computer.\n"
            "         Records sent from here are credited to the git identity set up there, usually a bot, not to you."
        )
    else:
        print("[ok] running on your own computer")

    if activate_git_hooks(root):
        print("[ok] git commit hook is active")
    else:
        problems.append("Could not activate the git commit hook. Run: git config core.hooksPath .githooks")

    name, email = tracker.git_identity()
    if name and email:
        print(f"[ok] git identity: {name} <{email}>")
    else:
        problems.append(
            "Your git name and/or email are not set, so your work can't be credited to you. Run:\n"
            '         git config --global user.name "Your Name"\n'
            '         git config --global user.email "the-email-you-use-on-github@example.com"'
        )

    if git(["config", "remote.origin.url"], cwd=root):
        print("[ok] repository remote is set")
    else:
        problems.append("This clone has no 'origin' remote. Clone your team's repository from GitHub.")

    installed = {agent["id"]: find_agent(agent) for agent in AGENTS}
    if any(installed.values()):
        print("[ok] AI coding tools found")
    try:
        # e.g. "setup:claude-code,vscode-copilot", or "setup-clean" when no supported tool was found
        found_ids = [agent["id"] for agent in AGENTS if installed[agent["id"]]]
        delivered = tracker.send_event("setup:" + ",".join(found_ids) if found_ids else "setup-clean")
    except Exception:
        delivered = False
    if delivered:
        print("[ok] setup data sent to your instructor")
        marker.parent.mkdir(exist_ok=True)
        marker.write_text("ok\n", encoding="utf-8")
    else:
        problems.append(
            "Could not send setup data to your instructor (are you offline?). Run this setup again when connected."
        )

    print("\nAny use of AI to edit code in this repository is tracked.")
    if any(installed.values()):
        print("You are required to approve the hooks in each AI tool you have in this environment (each asks you once):")
    else:
        print("Approve the hooks in each AI tool you have in this environment (each asks you once):")
    for agent in AGENTS:
        print(f"  - {agent['name']}: {agent['approval']}")
    print(
        "  Editors that run entirely in the web browser (vscode.dev, and github.dev opened with the . key on GitHub)\n"
        "  can't run these hooks, so AI use in them is not recorded. Use an editor on your computer or a Codespace."
    )
    print()

    for note in notes:
        print(f"Note: {note}")
    if problems:
        print("Problems to fix:")
        for problem in problems:
            print(f"  [!] {problem}")
    else:
        print("Setup complete.")
    if args.from_commit_hook:
        print("(This setup ran automatically during your first commit; your commit was not affected.)\n")
    return 0 if args.from_commit_hook or not problems else 1


if __name__ == "__main__":
    sys.exit(main())
