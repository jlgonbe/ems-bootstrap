#!/usr/bin/env python3
"""gate.py — is this a new project? Read-only; writes nothing.

Usage: python3 gate.py [--root DIR]
Exit 0 and «new project» when none of the instruction or memory files exists and git history
has at most one commit (or there is no git). Exit 1 and the reason otherwise.
Standard library only.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Instruction and memory files of the three supported harnesses: their presence means the project already
# has a context that someone would have to rescue, which is not what ems-bootstrap does.
OFFENDING = ("AGENTS.md", "CLAUDE.md", "MEMORY.md", "DECISIONS.md", "opencode.json",
             ".agents", ".claude", ".codex", ".opencode")
MAX_COMMITS = 1
# What a harness writes by itself when a session starts in the folder, before any skill runs
# (Claude Code creates .claude/.cc-writes/; OpenCode adds .gitignore and its plugin dependencies).
# A harness folder holding only these has no context to rescue.
HOUSEKEEPING = {
    ".claude": (".cc-writes", "settings.local.json"),
    ".opencode": (".gitignore", "node_modules", "package.json", "package-lock.json", "bun.lock"),
}


SELF = "ems-bootstrap"  # this skill, if the reader installed it inside the project


def has_context(path: Path) -> bool:
    if not path.is_dir() or path.is_symlink():
        return True
    allowed = HOUSEKEEPING.get(path.name, ())
    for child in path.iterdir():
        if child.name in allowed:
            continue
        if child.name == "skills" and child.is_dir() and {c.name for c in child.iterdir()} <= {SELF}:
            continue
        return True
    return False


def reasons(root: Path) -> list[str]:
    found = [name for name in OFFENDING
             if ((root / name).exists() or (root / name).is_symlink()) and has_context(root / name)]
    out = [f"{name} already exists" for name in found]
    if (root / ".git").exists():
        try:
            r = subprocess.run(["git", "-C", str(root), "rev-list", "--count", "HEAD"],
                               capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            out.append("there is a .git folder but git could not be run to count its commits")
            return out
        if r.returncode == 0:
            commits = int(r.stdout.strip() or "0")
            if commits > MAX_COMMITS:
                out.append(f"git history has {commits} commits (at most {MAX_COMMITS} for a new project)")
        # a repository with no commit yet makes rev-list fail: that is a new project
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".", help="project root (default: current directory)")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 1
    found = reasons(root)
    if found:
        print("not a new project: " + "; ".join(found))
        return 1
    print("new project")
    return 0


if __name__ == "__main__":
    sys.exit(main())
