#!/usr/bin/env python3
"""setup.py — renders the EMS project memory into a new project. Called by the ems-bootstrap skill.

Order: the gate (gate.py) → validate every answer → render the templates → write D001 through the
memory.py → link the skill for Claude Code → memory.py check. Nothing is written if the gate or the
validation fails; if D001 or the check fails, everything this run created is removed.

Usage (from anywhere):
  python3 setup.py --root DIR --project-name "…" --project "…" --how "…" --language Spanish \\
      --harness opencode,claude,codex [--planner-model-opencode P/M] [--executor-model-opencode P/M] \\
      [--planner-model-claude opus] [--executor-model-claude sonnet] \\
      [--planner-model-codex ID] [--executor-model-codex ID] [--triggers "«…», «…»"]

All texts are English except --triggers (phrases in the user's language, each inside «…»).
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.dont_write_bytecode = True  # leave no __pycache__ in the skill's folder
sys.path.insert(0, str(HERE))
import gate  # noqa: E402

HARNESSES = ("opencode", "claude", "codex")
LABELS = {"opencode": "OpenCode", "claude": "Claude Code", "codex": "Codex"}
AGENT_FILES = {"opencode": (".opencode/agents", "md"), "claude": (".claude/agents", "md"), "codex": (".codex/agents", "toml")}
D001_TITLE = "Adopt the EMS project memory system"
# Harness sandboxes forbid scripts to write in their own folders: Claude Code in .claude/agents and
# .claude/skills (and under any other .claude segment), Codex in .agents and .codex once they exist.
# What cannot be written there goes to PENDING, for the agent to create with its own file tool.
PROTECTED = (".claude/", ".agents/", ".codex/")
PENDING = ".ems-pending"
MAX_DESCRIPTION = 1024  # skill description limit of the harnesses
DEFAULT_TRIGGER = "«remember this»"


def staged_path(root: Path, rel: str) -> Path:
    """Where a blocked file is staged: without the leading dot, since the sandbox also blocks any path that
    contains the protected folder's name as a segment."""
    return root / PENDING / rel[1:]


def ascii_only(name: str, value: str) -> str | None:
    """Non-English letters outside «quotes» and `backticks`, where proper names may keep their spelling."""
    outside = re.sub(r"«[^»]*»|`[^`]*`", "", value)
    bad = [c for c in outside if ord(c) > 127 and c.isalpha()]
    return (f"--{name} must be written in English; keep a proper name inside «…» (found '{bad[0]}')"
            if bad else None)


def validate(a: argparse.Namespace) -> list[str]:
    errors = []
    harness = [h.strip() for h in a.harness.split(",") if h.strip()]
    if not harness or any(h not in HARNESSES for h in harness):
        errors.append(f"--harness must be a comma-separated subset of {', '.join(HARNESSES)}")
    for name in ("project_name", "project", "how", "language"):
        value = getattr(a, name)
        if not value or not value.strip():
            errors.append(f"--{name.replace('_', '-')} is required")
        elif "{{FILL:" in value:
            errors.append(f"--{name.replace('_', '-')} contains a template placeholder")
    models = [f"{role}_model_{h}" for h in HARNESSES for role in ("planner", "executor")]
    for name in ("project", "how", "language", *models):
        e = ascii_only(name.replace("_", "-"), getattr(a, name) or "")
        if e:
            errors.append(e)
    for name in models:
        value = getattr(a, name) or ""
        if value and not re.fullmatch(r"[A-Za-z0-9._:/@-]+", value):
            errors.append(f"--{name.replace('_', '-')} must be a single model ID without spaces")
    for name in ("planner_model_opencode", "executor_model_opencode"):
        value = getattr(a, name) or ""
        if value and "/" not in value:
            errors.append(f"--{name.replace('_', '-')} must be provider/model-id, as `opencode models` lists it")
    if a.triggers and ('"' in a.triggers or "\n" in a.triggers):
        errors.append("--triggers must be one line without double quotes (it goes inside the skill's YAML description)")
    tmpl = (ASSETS / "skill/project-memory/SKILL.md.tmpl").read_text(encoding="utf-8")
    desc = re.search(r'^description: "(.*)"$', tmpl, re.M).group(1)
    length = len(desc.replace("{{FILL:triggers}}", a.triggers.strip() or DEFAULT_TRIGGER))
    if length > MAX_DESCRIPTION:
        errors.append(f"--triggers is too long: the skill description would have {length} characters "
                      f"(at most {MAX_DESCRIPTION}); use fewer or shorter phrases")
    return errors


def fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{FILL:" + key + "}}", value)
    return text


def model_line(model: str | None, harness: str) -> str:
    if not model:
        return ""
    return f'model = "{model}"\n' if harness == "codex" else f"model: {model}\n"


def write(root: Path, rel: str, text: str, created: list[str], pending: list[str]) -> None:
    path = root / rel
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        created.append(rel)
    except PermissionError:
        if not rel.startswith(PROTECTED):
            raise
        staged = staged_path(root, rel)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(text, encoding="utf-8")
        pending.append(rel)


def agents_rows(harness: list[str]) -> str:
    def paths(name: str) -> str:
        return " · ".join(f"`{AGENT_FILES[h][0]}/{name}.{AGENT_FILES[h][1]}`" for h in HARNESSES if h in harness)
    return (f"| project-planner (agent) | {paths('project-planner')} | plan a change that touches several files "
            "or whose approach is not obvious, before anything is edited |\n"
            f"| project-plan-executor (agent) | {paths('project-plan-executor')} | carry out a plan the user approved |")


def d001(a: argparse.Namespace, harness: list[str]) -> list[str]:
    models = []
    for h in harness:
        pm = getattr(a, f"planner_model_{h}") or "the session's model"
        em = getattr(a, f"executor_model_{h}") or "the session's model"
        models.append(f"{LABELS[h]}: planner {pm}, executor {em}")
    names = ", ".join(LABELS[h] for h in harness)
    return [
        "--type", "D", "--title", D001_TITLE,
        "--context", f"New project set up with ems-bootstrap for {names}; without a system the agent's context "
                     "is repeated by hand in every conversation and goes stale as the project moves",
        "--alternatives", "No memory system, repeating the context in every conversation: rejected, it is never the same "
                          "and it is lost; a single instructions file without dated history: rejected, it goes stale "
                          "because nobody knows when or why each line was written",
        "--decision", "AGENTS.md (imported by CLAUDE.md) holds the current state, with five working rules (only the "
                      "script writes the logs; ask instead of assuming; say so when an idea has a problem instead of "
                      "agreeing by default; plan before a complex change; a rule changes only after its decision) and is rewritten when it changes; "
                      "MEMORY.md (lessons, loaded every session) and DECISIONS.md (decisions, read on demand) are dated "
                      "append-only history written only by the project-memory skill; lessons and decisions are recorded "
                      "the moment they happen and every task is closed by checking AGENTS.md; complex changes are planned "
                      f"by project-planner and carried out by project-plan-executor ({'; '.join(models)}); harness files "
                      f"in English, the project's own files in {a.language}",
        "--rationale", "Keeps what the agent knows true over time: lessons change every task, so they are always loaded; "
                       "decisions explain why, so they are read only when that why is touched; planning with a deep model "
                       "and executing an approved plan with a cheaper one keeps the cost where the thinking is",
        "--active-rule", "AGENTS.md rules 1, 2, 3, 4 and 5",
        "--commit",
    ]


def link_skill_for_claude(root: Path, files: dict[str, str], created: list[str], pending: list[str]) -> str:
    """`files` maps each file of the skill, relative to its folder, to its content."""
    source = root / ".agents" / "skills" / "project-memory"
    target = root / ".claude" / "skills" / "project-memory"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(Path("..") / ".." / ".agents" / "skills" / "project-memory", target_is_directory=True)
        created.append(".claude/skills/project-memory (link to .agents/skills/project-memory)")
        return "link"
    except PermissionError:
        pass  # sandbox: stage a copy below
    except OSError:
        try:
            shutil.copytree(source, target)
            created.append(".claude/skills/project-memory (copy: this system does not allow symlinks)")
            return "copy"
        except PermissionError:
            pass
    for name, text in files.items():
        rel = f".claude/skills/project-memory/{name}"
        staged = staged_path(root, rel)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text(text, encoding="utf-8")
        pending.append(rel)
    return "pending"


def rollback(root: Path, before: set[Path]) -> None:
    """Remove every path this run created, deepest first, so the gate passes again on a retry."""
    for path in sorted(set(root.rglob("*")) - before, key=lambda p: len(p.parts), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=".")
    p.add_argument("--project-name", required=True)
    p.add_argument("--project", required=True, help="what the project is, 1-3 sentences, English")
    p.add_argument("--how", required=True, help="how it is worked on (commands, conventions), English; or 'Not defined yet.'")
    p.add_argument("--language", required=True, help="language of the project's own files, English name (e.g. Spanish)")
    p.add_argument("--harness", required=True, help="comma-separated subset of opencode, claude, codex")
    for h in HARNESSES:
        p.add_argument(f"--planner-model-{h}")
        p.add_argument(f"--executor-model-{h}")
    p.add_argument("--triggers", default="", help="extra trigger phrases in the user's language, each inside «…»")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()

    blocked = gate.reasons(root) if root.is_dir() else [f"not a directory: {root}"]
    if blocked:
        print("not a new project: " + "; ".join(blocked))
        print("nothing written")
        return 1
    errors = validate(a)
    if errors:
        for e in errors:
            print(f"error: {e}")
        print("nothing written")
        return 2
    harness = [h.strip() for h in a.harness.split(",") if h.strip()]

    created: list[str] = []
    pending: list[str] = []
    before = set(root.rglob("*"))
    values = {"project_name": a.project_name.strip(), "project": a.project.strip(), "how": a.how.strip(),
              "language": a.language.strip(), "agents_rows": agents_rows(harness),
              "triggers": a.triggers.strip() or DEFAULT_TRIGGER}
    for name in ("AGENTS.md", "CLAUDE.md", "MEMORY.md", "DECISIONS.md"):
        write(root, name, fill((ASSETS / f"{name}.tmpl").read_text(encoding="utf-8"), values), created, pending)
    skill = ".agents/skills/project-memory"
    src = ASSETS / "skill/project-memory"
    skill_files = {"SKILL.md": fill((src / "SKILL.md.tmpl").read_text(encoding="utf-8"), values),
                   "references/entry-format.md": (src / "references/entry-format.md").read_text(encoding="utf-8"),
                   "scripts/memory.py": (src / "scripts/memory.py").read_text(encoding="utf-8")}
    for name, text in skill_files.items():
        write(root, f"{skill}/{name}", text, created, pending)
    if "opencode" in harness:
        write(root, "opencode.json", (ASSETS / "opencode.json.tmpl").read_text(encoding="utf-8"), created, pending)
    for h in HARNESSES:
        if h not in harness:
            continue
        folder, ext = AGENT_FILES[h]
        for agent, role in (("project-planner", "planner"), ("project-plan-executor", "executor")):
            tmpl = (ASSETS / "agents" / h / f"{agent}.{ext}.tmpl").read_text(encoding="utf-8")
            write(root, f"{folder}/{agent}.{ext}",
                  fill(tmpl, {"model_line": model_line(getattr(a, f"{role}_model_{h}"), h)}), created, pending)
    if "claude" in harness:
        link_skill_for_claude(root, skill_files, created, pending)

    # The package's own copy of memory.py: the project's copy may be staged if the sandbox blocked .agents/.
    mem = [sys.executable, str(src / "scripts" / "memory.py"), "--root", str(root)]
    r = subprocess.run(mem + ["add", *d001(a, harness)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        rollback(root, before)
        print("error: D001 could not be written; everything this run created was removed, so the folder is as before")
        return 3
    created.append("DECISIONS.md: D001 — " + D001_TITLE)
    r = subprocess.run(mem + ["check"], capture_output=True, text=True)
    # A skill that is only staged is expected to be missing until the agent creates it.
    expected = {f"skill path not found: {rel}" for rel in pending}
    errors = [l for l in r.stdout.splitlines() if l.strip() and l != "OK" and not l.startswith("FAILED:")]
    problems = [l for l in errors if l not in expected]
    if r.returncode != 0 and not errors:
        problems = [r.stdout.strip() or "memory.py check failed without a message"]
    print("created:")
    for c in created:
        print(f"  {c}")
    print("check: " + ("OK" if not problems else r.stdout.strip()))
    if problems:
        rollback(root, before)
        print("error: the check failed; everything this run created was removed, so the folder is as before")
        return 4
    if pending:
        print("pending: the harness sandbox did not let this script write these files; create each file on the left "
              f"with the content of the staged file on the right, using your own file-writing tool, then delete {PENDING}/ "
              "and run python3 .agents/skills/project-memory/scripts/memory.py check:")
        for rel in pending:
            print(f"  {rel} <- {staged_path(root, rel).relative_to(root).as_posix()}")
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
