#!/usr/bin/env python3
"""memory.py — the only writer of the root MEMORY.md and DECISIONS.md (EMS project memory).

Subcommands:
  add         build an entry with the next ID and today's date and insert it at the TOP
              of the log, under the header (newest first; dry-run unless --commit)
  set-status  mark one entry as superseded by a later one (dry-run unless --commit)
  check       read-only lint of AGENTS.md / CLAUDE.md / MEMORY.md / DECISIONS.md
  link        print the Markdown link to one entry, as AGENTS.md must cite it

Standard library only. Format: ../references/entry-format.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[4]

RESP = "<!-- ems:responsibility:"
ANCHORS = ("rules", "map", "skills", "protocol")
AGENTS_MAX_LINES = 150

TAG_RE = re.compile(r"<[A-Za-z/!][^>]*>")  # raw HTML-like tags break Markdown rendering
ORIGIN_RE = re.compile(r"[MD]\d{3}(, ?[MD]\d{3})*")
HEAD_RE = re.compile(r"^### ([MD])(\d{3}) — (.+)$", re.M)
ID_RE = re.compile(r"\b([MD]\d{3})\b")
LINK_RE = re.compile(r"\[([MD]\d{3})\]\(([^)\s#]+)#([^)\s]+)\)")  # [D001](DECISIONS.md#anchor)

M_FIELDS = ["Date", "Type", "Trigger", "Learning", "Evidence", "Origin", "Status"]
M_REQUIRED = ["Date", "Type", "Trigger", "Learning", "Evidence", "Status"]
D_FIELDS = ["Date", "Status", "Context", "Alternatives considered", "Decision", "Rationale", "Active rule"]
D_REQUIRED = ["Date", "Status", "Context", "Alternatives considered", "Decision", "Rationale"]

M_ONLY = {"Type": "entry-type", "Trigger": "trigger", "Learning": "learning",
          "Evidence": "evidence", "Origin": "origin"}
D_ONLY = {"Context": "context", "Alternatives considered": "alternatives", "Decision": "decision",
          "Rationale": "rationale", "Active rule": "active-rule"}

TYPES = {"correction", "failure", "preference", "finding"}
M_STATUS_RE = re.compile(r"^(active|superseded by M\d{3})$")
D_STATUS_RE = re.compile(r"^(accepted|superseded by D\d{3})$")
PLACEHOLDER = "{{FILL:"


# ---------------------------------------------------------------- parsing
class Entry:
    def __init__(self, kind: str, num: int, title: str, fields: dict[str, str], log: str,
                 problems: list[str] | None = None):
        self.kind, self.num, self.title, self.fields, self.log = kind, num, title, fields, log
        self.problems = problems or []

    @property
    def id(self) -> str:
        return f"{self.kind}{self.num:03d}"

    @property
    def date(self) -> str:
        return self.fields.get("Date", "")

    def ids_in(self, field: str) -> list[str]:
        return ID_RE.findall(self.fields.get(field, ""))


FIELD_RE = re.compile(r"^- ([A-Za-z ]+): (.*)$")


def parse_entries(text: str, log: str) -> list[Entry]:
    """Parse every `### ` block. Field problems are kept on the entry for `check`."""
    entries = []
    heads = list(HEAD_RE.finditer(text))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        kind = h.group(1)
        allowed = M_FIELDS if kind == "M" else D_FIELDS
        fields, problems = {}, []
        for line in text[h.end():end].splitlines():
            if not line.strip():
                continue
            m = FIELD_RE.match(line)
            if not m:
                problems.append(f"malformed line '{line[:60]}'")
                continue
            name, value = m.group(1), m.group(2).strip()
            if name not in allowed:
                problems.append(f"unknown field '{name}'")
            elif name in fields:
                problems.append(f"duplicate field '{name}'")
            else:
                fields[name] = value
        entries.append(Entry(kind, int(h.group(2)), h.group(3), fields, log, problems))
    return entries


def stray_headings(text: str) -> list[str]:
    """`###` lines that are not valid entry headings (they would be invisible to the parser)."""
    return [l for l in text.splitlines() if l.startswith("###") and not HEAD_RE.match(l)]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def log_path(root: Path, kind: str) -> Path:
    return root / ("MEMORY.md" if kind == "M" else "DECISIONS.md")


# ---------------------------------------------------------------- add
def insert_newest_first(text: str, entry: str) -> str:
    """Put `entry` right after the header, before the first existing entry."""
    first = HEAD_RE.search(text)
    if first is None:
        head = text.rstrip("\n")
        return f"{head}\n\n{entry}" if head else entry
    head = text[:first.start()].rstrip("\n")
    return f"{head}\n\n{entry}\n{text[first.start():]}"


def raw_tags(value: str) -> list[str]:
    """HTML-like tags outside `backticks`."""
    outside = re.sub(r"`[^`]*`", "", value)
    return TAG_RE.findall(outside)


def valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def non_english_outside_quotes(value: str) -> list[str]:
    """Non-ASCII letters (or ¿ ¡) outside «quotes» and `backticks`: entries are written in English,
    and the user's own words go verbatim inside «…» in their language."""
    outside = re.sub(r"«[^»]*»|`[^`]*`", "", value)
    return [c for c in outside if (ord(c) > 127 and c.isalpha()) or c in "¿¡"]


def build_entry(kind: str, num: int, title: str, values: dict[str, str]) -> str:
    fields = M_FIELDS if kind == "M" else D_FIELDS
    lines = [f"### {kind}{num:03d} — {title}"]
    for f in fields:
        if values.get(f):
            lines.append(f"- {f}: {values[f]}")
    return "\n".join(lines) + "\n"


def cmd_add(a: argparse.Namespace) -> int:
    root = Path(a.root)
    kind = a.type
    values = {
        "Date": _dt.date.today().isoformat(),
        "Type": a.entry_type, "Trigger": a.trigger, "Learning": a.learning,
        "Evidence": a.evidence, "Origin": a.origin,
        "Context": a.context, "Alternatives considered": a.alternatives, "Decision": a.decision,
        "Rationale": a.rationale, "Active rule": a.active_rule,
        "Status": "active" if kind == "M" else "accepted",
    }
    foreign = D_ONLY if kind == "M" else M_ONLY
    stray = [f"--{flag}" for flag in foreign.values() if getattr(a, flag.replace("-", "_")) is not None]
    if stray:
        print(f"error: {', '.join(stray)} not valid for --type {kind}", file=sys.stderr)
        return 2
    multiline = [f"--{flag}" for flag in ["title", *M_ONLY.values(), *D_ONLY.values()]
                 if any(c in (getattr(a, flag.replace("-", "_")) or "") for c in "\r\n")]
    if multiline:
        print(f"error: {', '.join(multiline)} must be a single line", file=sys.stderr)
        return 2
    required = M_REQUIRED if kind == "M" else D_REQUIRED
    missing = [f for f in required if not values.get(f)]
    if not a.title:
        missing.insert(0, "title")
    if missing:
        flags = {"title": "--title", **{k: f"--{v}" for k, v in {**M_ONLY, **D_ONLY}.items()}}
        print(f"error: missing required field(s) for {kind}: "
              + ", ".join(f"{f} ({flags[f]})" if f in flags else f for f in missing), file=sys.stderr)
        return 2
    if kind == "M":
        if values["Type"] not in TYPES:
            print(f"error: Type must be one of {sorted(TYPES)}", file=sys.stderr); return 2
    status_re = M_STATUS_RE if kind == "M" else D_STATUS_RE
    if not status_re.match(values["Status"]):
        print(f"error: invalid status '{values['Status']}'", file=sys.stderr); return 2

    path = log_path(root, kind)
    if not path.exists():
        print(f"error: {path.name} not found in {root}", file=sys.stderr); return 2
    text = read(path)
    nums = [int(n) for k, n, _ in HEAD_RE.findall(text) if k == kind]
    num = (max(nums) if nums else 0) + 1
    entry = build_entry(kind, num, a.title, values)
    new_text = insert_newest_first(text, entry)
    problems = [e for e in run_check(root, {path.name: new_text}) if e.startswith(f"{kind}{num:03d}:")]
    if problems:
        for e in problems:
            print(f"error: {e}", file=sys.stderr)
        print("nothing written", file=sys.stderr)
        return 2
    if not a.commit:
        print(entry, end="")
        print("link: " + entry_link(Entry(kind, num, a.title, {}, path.name)))
        print(f"(dry-run: nothing written; re-run with --commit to add {kind}{num:03d} at the top of {path.name})")
        return 0
    path.write_text(new_text, encoding="utf-8")
    print(f"written: {kind}{num:03d} — {a.title} -> top of {path.name}")
    return 0


# ---------------------------------------------------------------- set-status
def cmd_set_status(a: argparse.Namespace) -> int:
    if "\r" in a.status or "\n" in a.status:
        print("error: status must be a single line", file=sys.stderr); return 2
    root = Path(a.root)
    m = re.fullmatch(r"([MD])(\d{3})", a.id)
    if not m:
        print(f"error: invalid ID '{a.id}'", file=sys.stderr); return 2
    kind = m.group(1)
    if not re.fullmatch(rf"superseded by {kind}\d{{3}}", a.status):
        print(f"error: the only status change is 'superseded by {kind}0XX' (a later entry of the same log); "
              "a correction is a new entry that supersedes the old one", file=sys.stderr); return 2
    path = log_path(root, kind)
    text = read(path)
    heads = list(HEAD_RE.finditer(text))
    for i, h in enumerate(heads):
        if f"{h.group(1)}{h.group(2)}" != a.id:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[h.start():end]
        cur = re.search(r"^- Status: (.*)$", block, re.M)
        if cur and cur.group(1).startswith("superseded by ") and not a.force:
            print(f"error: {a.id} is already '{cur.group(1)}'; a change of mind is a new entry. "
                  "--force only re-points an already superseded entry at a different later entry", file=sys.stderr)
            return 2
        new_block, n = re.subn(r"^- Status: .*$", f"- Status: {a.status}", block, count=1, flags=re.M)
        if n != 1:
            print(f"error: {a.id} has no Status line", file=sys.stderr); return 2
        new_text = text[:h.start()] + new_block + text[end:]
        problems = [e for e in run_check(root, {path.name: new_text}) if e.startswith(f"{a.id}:")]
        if problems:
            for e in problems:
                print(f"error: {e}", file=sys.stderr)
            print("nothing written", file=sys.stderr)
            return 2
        if not a.commit:
            print(f"(dry-run) {a.id}: Status -> {a.status}; re-run with --commit to write")
            return 0
        path.write_text(new_text, encoding="utf-8")
        print(f"written: {a.id} Status -> {a.status}")
        return 0
    print(f"error: {a.id} not found in {path.name}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------- check
def anchor_block(text: str, name: str) -> str | None:
    m = re.search(rf"<!-- ems:{name} -->(.*?)<!-- /ems:{name} -->", text, re.S)
    return m.group(1) if m else None


def agents_rules(agents: str) -> dict[int, str]:
    """Numbered rules inside the ems:rules anchor, keyed by their own number."""
    block = anchor_block(agents, "rules") or ""
    out = {}
    for line in block.splitlines():
        m = re.match(r"^(\d+)\. ", line)
        if m:
            out[int(m.group(1))] = line
    return out


def rule_origin(line: str) -> str:
    m = re.search(r"\(origin: (.+)\)\s*$", line)
    return m.group(1) if m else ""


def slug(heading: str) -> str:
    """GitHub-style anchor of a Markdown heading (what Markdown renderers link to)."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def entry_link(e: Entry) -> str:
    return f"[{e.id}]({e.log}#{slug(f'{e.id} — {e.title}')})"


def run_check(root: Path, override: dict[str, str] | None = None) -> list[str]:
    """Lint. `override` replaces the text of AGENTS.md / MEMORY.md / DECISIONS.md (pre-commit validation)."""
    errors: list[str] = []
    override = override or {}
    agents, memory, decisions = (override.get(n, read(root / n)) for n in ("AGENTS.md", "MEMORY.md", "DECISIONS.md"))
    for name, text in (("AGENTS.md", agents), ("MEMORY.md", memory), ("DECISIONS.md", decisions)):
        if not text:
            errors.append(f"{name}: file not found"); continue
        if not text.lstrip().startswith(RESP):
            errors.append(f"{name}: missing ems:responsibility header")
    claude = override.get("CLAUDE.md", read(root / "CLAUDE.md"))
    if claude and "@AGENTS.md" not in claude:
        errors.append("CLAUDE.md: must import @AGENTS.md (Claude Code reads CLAUDE.md instead of AGENTS.md)")
    for name, text in (("AGENTS.md", agents), ("CLAUDE.md", claude), ("MEMORY.md", memory), ("DECISIONS.md", decisions)):
        if PLACEHOLDER in text:
            hole = text[text.index(PLACEHOLDER):].split("}}")[0] + "}}"
            errors.append(f"{name}: unfilled placeholder {hole}")
    if agents:
        n = len(agents.splitlines())
        if n > AGENTS_MAX_LINES:
            errors.append(f"AGENTS.md: {n} lines > {AGENTS_MAX_LINES}; move what is not needed in every session "
                          "to a referenced file loaded only when it applies")
        for a in ANCHORS:
            o, c = agents.count(f"<!-- ems:{a} -->"), agents.count(f"<!-- /ems:{a} -->")
            if o != 1 or c != 1 or anchor_block(agents, a) is None:
                errors.append(f"AGENTS.md: anchor ems:{a} must be opened and closed exactly once")

    for name, text in (("MEMORY.md", memory), ("DECISIONS.md", decisions)):
        for line in stray_headings(text):
            errors.append(f"{name}: unrecognised heading '{line[:60]}'")
        nums = [int(n) for _, n, _ in HEAD_RE.findall(text)]
        if nums != sorted(nums, reverse=True):
            errors.append(f"{name}: entries must be newest first (descending IDs)")
    entries = parse_entries(memory, "MEMORY.md") + parse_entries(decisions, "DECISIONS.md")
    ids = [e.id for e in entries]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate ID: {dup}")
    known = set(ids)
    for e in entries:
        expected_log = "MEMORY.md" if e.kind == "M" else "DECISIONS.md"
        if e.log != expected_log:
            errors.append(f"{e.id}: {e.kind} entry found in {e.log} (belongs in {expected_log})")
        for problem in e.problems:
            errors.append(f"{e.id}: {problem}")
        for field, value in [("title", e.title), *e.fields.items()]:
            tags = raw_tags(value)
            if tags:
                errors.append(f"{e.id}: raw tag {tags[0]} in {field} breaks Markdown rendering; wrap it in `backticks`")
            bad = non_english_outside_quotes(value) if field != "Date" else []
            if bad:
                errors.append(f"{e.id}: non-English character '{bad[0]}' in {field} outside «quotes» or `backticks`; write it in English or quote the user verbatim inside «…»")
        required = M_REQUIRED if e.kind == "M" else D_REQUIRED
        for f in required:
            if not e.fields.get(f):
                errors.append(f"{e.id}: missing field '{f}'")
        if e.date and not valid_date(e.date):
            errors.append(f"{e.id}: invalid Date '{e.date}'")
        st = e.fields.get("Status", "")
        if st and not (M_STATUS_RE if e.kind == "M" else D_STATUS_RE).match(st):
            errors.append(f"{e.id}: invalid status '{st}'")
        if e.kind == "M":
            if e.fields.get("Type") and e.fields["Type"] not in TYPES:
                errors.append(f"{e.id}: invalid Type '{e.fields['Type']}'")
        origin = e.fields.get("Origin", "")
        if origin and not ORIGIN_RE.fullmatch(origin):
            errors.append(f"{e.id}: Origin must be a comma-separated list of M/D IDs")
        if len(set(e.ids_in("Origin"))) != len(e.ids_in("Origin")):
            errors.append(f"{e.id}: Origin repeats an ID")
        for ref in e.ids_in("Origin"):
            if ref not in known:
                errors.append(f"{e.id}: Origin {ref} not found")
            elif ref == e.id:
                errors.append(f"{e.id}: Origin cites itself")
        active_rule = e.fields.get("Active rule", "")
        if e.kind == "D" and active_rule:
            ar = re.match(r"^AGENTS\.md (?:rule (\d+)|rules (\d+(?:(?:, | and )\d+)+))\b", active_rule)
            if not ar:
                errors.append(f"{e.id}: Active rule must start with 'AGENTS.md rule N' or 'AGENTS.md rules N and M'")
            else:
                rules = agents_rules(agents)
                for num in re.findall(r"\d+", ar.group(1) or ar.group(2)):
                    rule = rules.get(int(num))
                    if st != "accepted":
                        continue  # superseded: the rule may be gone or belong to a newer D
                    if rule is None:
                        errors.append(f"{e.id}: Active rule AGENTS.md rule {num} not found")
                    elif e.id not in ID_RE.findall(rule_origin(rule)):
                        errors.append(f"{e.id}: AGENTS.md rule {num} does not cite (origin: {e.id})")
        sup = re.fullmatch(r"superseded by ([MD]\d{3})", st)
        if sup:
            tgt = sup.group(1)
            if tgt not in known:
                errors.append(f"{e.id}: superseded by {tgt} not found")
            elif tgt[0] != e.kind or int(tgt[1:]) <= e.num:
                errors.append(f"{e.id}: superseded by {tgt} must be a later entry of the same log")

    for n, line in agents_rules(agents).items():
        origin = rule_origin(line)
        if not origin:
            errors.append(f"AGENTS.md rule {n}: missing (origin: …)"); continue
        for ref in ID_RE.findall(origin):
            if ref not in known:
                errors.append(f"AGENTS.md rule {n}: origin {ref} not found")
    by_id = {e.id: e for e in entries}
    for m in LINK_RE.finditer(agents or ""):
        e = by_id.get(m.group(1))
        if e is None:
            errors.append(f"AGENTS.md: link to {m.group(1)}, which is not found")
        elif m.group(0) != entry_link(e):
            errors.append(f"AGENTS.md: link to {e.id} must be {entry_link(e)}")
    for ref in ID_RE.findall(LINK_RE.sub("", agents or "")):
        errors.append(f"AGENTS.md: {ref} is not a link to its entry (get it with: memory.py link {ref})")
    skills = anchor_block(agents, "skills") or ""
    for path in re.findall(r"`(\.agents/skills/[^`]+/SKILL\.md)`", skills):
        if not (root / path).exists():
            errors.append(f"skill path not found: {path}")

    return errors


def cmd_check(a: argparse.Namespace) -> int:
    errors = run_check(Path(a.root))
    if errors:
        for e in errors:
            print(e)
        print(f"FAILED: {len(errors)} error(s)")
        return 1
    print("OK")
    return 0


def cmd_link(a: argparse.Namespace) -> int:
    root = Path(a.root)
    entries = parse_entries(read(root / "MEMORY.md"), "MEMORY.md") + \
        parse_entries(read(root / "DECISIONS.md"), "DECISIONS.md")
    for e in entries:
        if e.id == a.id:
            print(entry_link(e))
            return 0
    print(f"{a.id}: not found", file=sys.stderr)
    return 1


# ---------------------------------------------------------------- cli
def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # titles and quotes are UTF-8 even where the console is not (Windows)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=str(DEFAULT_ROOT), help="project root (default: inferred)")
    sub = p.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add", help="append a new entry (dry-run unless --commit)")
    ad.add_argument("--type", choices=["M", "D"], required=True)
    ad.add_argument("--title", required=True)
    ad.add_argument("--entry-type"); ad.add_argument("--trigger")
    ad.add_argument("--learning"); ad.add_argument("--evidence"); ad.add_argument("--origin")
    ad.add_argument("--context"); ad.add_argument("--alternatives")
    ad.add_argument("--decision"); ad.add_argument("--rationale"); ad.add_argument("--active-rule")
    ad.add_argument("--commit", action="store_true")
    ad.set_defaults(func=cmd_add)

    ss = sub.add_parser("set-status", help="mark one entry 'superseded by <later ID>' (dry-run unless --commit)")
    ss.add_argument("id"); ss.add_argument("status")
    ss.add_argument("--commit", action="store_true")
    ss.add_argument("--force", action="store_true", help="re-point an already superseded entry at a different later entry")
    ss.set_defaults(func=cmd_set_status)

    sub.add_parser("check", help="read-only lint").set_defaults(func=cmd_check)
    lk = sub.add_parser("link", help="print the Markdown link to one entry (as AGENTS.md cites it)")
    lk.add_argument("id")
    lk.set_defaults(func=cmd_link)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
