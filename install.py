#!/usr/bin/env python3
"""install.py — installs the ems-bootstrap skill for one harness, from a downloaded copy of this repository.

Usage: python3 install.py --harness opencode|codex|claude [--dest DIR] [--replace]
Copies only what the skill needs (SKILL.md, references/, scripts/, assets/) into the harness's user-level
skills folder; never tests/, README.md or .git/. Exit 0 installed · 2 already installed (pass --replace only
after the user agreed) · 3 the destination could not be written. Standard library only.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PARTS = ("SKILL.md", "references", "scripts", "assets")
DESTS = {"opencode": "~/.agents/skills/ems-bootstrap", "codex": "~/.agents/skills/ems-bootstrap",
         "claude": "~/.claude/skills/ems-bootstrap"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--harness", required=True, choices=sorted(DESTS))
    p.add_argument("--dest", help="install somewhere else (default: the harness's user-level skills folder)")
    p.add_argument("--replace", action="store_true", help="replace an existing installation (ask the user first)")
    a = p.parse_args(argv)
    dest = Path(a.dest or DESTS[a.harness]).expanduser()
    if dest.resolve() == HERE:
        print(f"error: {dest} is this downloaded copy; download the repository to a temporary folder first")
        return 3
    if (dest.exists() or dest.is_symlink()) and not a.replace:
        print(f"already installed: {dest} exists; ask the user, then run again with --replace")
        return 2
    staging = dest.with_name(dest.name + ".new")
    try:
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for part in PARTS:  # copy aside first, so a failed copy never destroys an existing installation
            src = HERE / part
            if src.is_dir():
                shutil.copytree(src, staging / part, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            else:
                shutil.copy2(src, staging / part)
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        staging.rename(dest)
    except OSError as e:
        shutil.rmtree(staging, ignore_errors=True)
        print(f"error: cannot write {dest} ({e}); tell the user to copy {', '.join(PARTS)} from {HERE} into {dest}")
        return 3
    print(f"installed: {dest} ({', '.join(sorted(c.name for c in dest.iterdir()))})")
    print("tell the user: open a new session in a new, empty folder and say «set up the project memory» "
          "(in Spanish: «monta el sistema de memoria»)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
