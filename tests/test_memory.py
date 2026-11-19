"""Tests for the memory.py that ems-bootstrap copies into a project (stdlib unittest). Run from the package:
python3 -B -m unittest discover -s tests -v
"""
import datetime as dt
import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets/skill/project-memory/scripts"))
import memory  # noqa: E402

AGENTS_OK = """<!-- ems:responsibility: current context -->
# AGENTS
<!-- ems:rules -->
1. Do the thing. (origin: [D001](DECISIONS.md#d001--adopt))
<!-- /ems:rules -->
<!-- ems:map -->
map
<!-- /ems:map -->
<!-- ems:skills -->
| `.agents/skills/project-memory/SKILL.md` |
<!-- /ems:skills -->
<!-- ems:protocol -->
protocol
<!-- /ems:protocol -->
"""
MEM_HEAD = "<!-- ems:responsibility: learnings -->\n# MEMORY\n"
DEC_HEAD = "<!-- ems:responsibility: decisions -->\n# DECISIONS\n"
D001 = """
### D001 — Adopt
- Date: 2026-01-01
- Status: accepted
- Context: c
- Alternatives considered: none
- Decision: d
- Rationale: r
"""


def m_entry(num, date="2026-01-01", status="active", extra=""):
    return (f"\n### M{num:03d} — t{num}\n- Date: {date}\n- Type: finding\n"
            f"- Trigger: tr\n- Learning: le\n- Evidence: ev\n{extra}- Status: {status}\n")


def d_entry(num, date, extra=""):
    return (f"\n### D{num:03d} — d{num}\n- Date: {date}\n- Status: accepted\n- Context: c\n"
            f"- Alternatives considered: none\n- Decision: d\n- Rationale: r\n{extra}")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".agents/skills/project-memory").mkdir(parents=True)
        (self.root / ".agents/skills/project-memory/SKILL.md").write_text("x", encoding="utf-8")
        self.write("AGENTS.md", AGENTS_OK)
        self.write("MEMORY.md", MEM_HEAD)
        self.write("DECISIONS.md", DEC_HEAD + D001)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def text(self, name):
        return (self.root / name).read_text(encoding="utf-8")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = memory.main(["--root", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def add_m(self, *extra, commit=True):
        args = ["add", "--type", "M", "--title", "Title", "--entry-type", "correction",
                "--trigger", "When reading `Revisión 2026.md`", "--learning", "The structured file wins", "--evidence", "User: «manda el fichero, ñandú»",
                *extra]
        return self.run_cli(*args, *(["--commit"] if commit else []))


class TestAdd(Base):
    def test_next_id_does_not_fill_gaps(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1) + m_entry(3))
        code, out, _ = self.add_m()
        self.assertEqual(code, 0)
        self.assertIn("### M004 — Title", self.text("MEMORY.md"))
        self.assertNotIn("M002", self.text("MEMORY.md"))

    def test_empty_file_gives_m001(self):
        self.add_m()
        self.assertIn("### M001 — Title", self.text("MEMORY.md"))

    def test_date_is_today(self):
        self.add_m()
        self.assertIn(f"- Date: {dt.date.today().isoformat()}", self.text("MEMORY.md"))

    def test_english_labels_spanish_content(self):
        self.add_m()
        t = self.text("MEMORY.md")
        for label in ("- Type: correction", "- Trigger: When reading `Revisión 2026.md`",
                      "- Learning: The structured file wins", "- Evidence: User: «manda el fichero, ñandú»", "- Status: active"):
            self.assertIn(label, t)

    def test_dry_run_leaves_file_identical(self):
        before = hashlib.sha256(self.text("MEMORY.md").encode()).hexdigest()
        code, out, _ = self.add_m(commit=False)
        self.assertEqual(code, 0)
        self.assertIn("dry-run", out)
        self.assertEqual(before, hashlib.sha256(self.text("MEMORY.md").encode()).hexdigest())

    def test_dry_run_prints_the_link_agents_md_will_need(self):
        code, out, _ = self.run_cli("add", "--type", "D", "--title", "New rule: dates", "--context", "c",
                                    "--alternatives", "none", "--decision", "d", "--rationale", "r")
        self.assertEqual(code, 0)
        self.assertIn("link: [D002](DECISIONS.md#d002--new-rule-dates)", out)

    def test_commit_inserts_newest_first(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(2) + m_entry(1))
        old_entries = self.text("MEMORY.md")[len(MEM_HEAD):].lstrip("\n")
        self.add_m()
        t = self.text("MEMORY.md")
        self.assertTrue(t.startswith(MEM_HEAD.rstrip("\n")))
        self.assertLess(t.index("### M003"), t.index("### M002"))
        self.assertTrue(t.endswith(old_entries))

    def test_raw_tag_rejected_before_writing(self):
        before = self.text("DECISIONS.md")
        code, _, err = self.run_cli("add", "--type", "D", "--title", "x", "--context", "path a/<reason>/b",
                                    "--alternatives", "none", "--decision", "d", "--rationale", "r", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("raw tag <reason>", err)
        self.assertEqual(before, self.text("DECISIONS.md"))

    def test_tag_inside_backticks_is_fine(self):
        code, _, _ = self.run_cli("add", "--type", "D", "--title", "x", "--context", "path `a/<reason>/b`",
                                  "--alternatives", "none", "--decision", "d", "--rationale", "r", "--commit")
        self.assertEqual(code, 0)

    def test_missing_required_field(self):
        before = self.text("DECISIONS.md")
        code, _, err = self.run_cli("add", "--type", "D", "--title", "x", "--context", "c",
                                    "--decision", "d", "--rationale", "r", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("Alternatives considered", err)
        self.assertEqual(before, self.text("DECISIONS.md"))

    def test_add_rejects_bad_reference_before_writing(self):
        before = self.text("MEMORY.md")
        code, _, err = self.add_m("--origin", "M099")
        self.assertNotEqual(code, 0)
        self.assertIn("Origin M099 not found", err)
        self.assertEqual(before, self.text("MEMORY.md"))

    def test_flag_of_the_other_type_rejected(self):
        before = self.text("DECISIONS.md")
        code, _, err = self.run_cli("add", "--type", "D", "--title", "x", "--context", "c",
                                    "--alternatives", "none", "--decision", "d", "--rationale", "r",
                                    "--entry-type", "finding", "--learning", "l")
        self.assertNotEqual(code, 0)
        self.assertIn("--entry-type, --learning not valid for --type D", err)
        self.assertEqual(before, self.text("DECISIONS.md"))

    def test_context_on_an_m_rejected(self):
        before = self.text("MEMORY.md")
        code, _, err = self.add_m("--context", "c")
        self.assertNotEqual(code, 0)
        self.assertIn("--context not valid for --type M", err)
        self.assertEqual(before, self.text("MEMORY.md"))

    def test_empty_foreign_flag_rejected(self):
        before = self.text("MEMORY.md")
        code, _, err = self.add_m("--context", "")
        self.assertNotEqual(code, 0)
        self.assertIn("--context not valid for --type M", err)
        self.assertEqual(before, self.text("MEMORY.md"))

    def test_multiline_value_rejected(self):
        before = self.text("MEMORY.md")
        code, _, err = self.run_cli("add", "--type", "M", "--title", "x",
                                    "--entry-type", "finding", "--trigger", "t",
                                    "--learning", "line one\n### M099 — fake", "--evidence", "e", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("--learning must be a single line", err)
        self.assertEqual(before, self.text("MEMORY.md"))

    def test_origin_rejected_for_d(self):
        before = self.text("DECISIONS.md")
        code, _, err = self.run_cli("add", "--type", "D", "--title", "x", "--context", "c",
                                    "--alternatives", "none", "--decision", "d", "--rationale", "r",
                                    "--origin", "D001")
        self.assertNotEqual(code, 0)
        self.assertIn("--origin not valid for --type D", err)
        self.assertEqual(before, self.text("DECISIONS.md"))

    def test_invalid_type_rejected(self):
        code, _, err = self.run_cli("add", "--type", "M", "--title", "x",
                                    "--entry-type", "rule", "--trigger", "t", "--learning", "l",
                                    "--evidence", "e")
        self.assertNotEqual(code, 0)
        self.assertIn("Type must be one of", err)

    def test_d_with_active_rule_that_does_not_exist_rejected(self):
        before = self.text("DECISIONS.md")
        code, _, err = self.run_cli("add", "--type", "D", "--title", "x", "--context", "c",
                                    "--alternatives", "none", "--decision", "d", "--rationale", "r",
                                    "--active-rule", "AGENTS.md rule 99", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("Active rule AGENTS.md rule 99 not found", err)
        self.assertEqual(before, self.text("DECISIONS.md"))

    def test_spanish_outside_quotes_rejected(self):
        code, _, err = self.add_m("--origin", "D001")  # an English entry with quoted Spanish is valid
        self.assertEqual(code, 0, err)
        code, _, err = self.run_cli("add", "--type", "M", "--title", "x",
                                    "--entry-type", "finding", "--trigger", "t",
                                    "--learning", "Siempre confirmar después", "--evidence", "e", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("non-English character 'é' in Learning", err)
        self.assertNotIn("### M002", self.text("MEMORY.md"))

    def test_d_with_new_rule_workflow(self):
        dec = ["add", "--type", "D", "--title", "New rule", "--context", "c", "--alternatives", "none",
               "--decision", "d", "--rationale", "r"]
        code, _, _ = self.run_cli(*dec, "--active-rule", "AGENTS.md rule 2")
        self.assertNotEqual(code, 0)  # (a) the flag only passes after the rule exists
        code, out, _ = self.run_cli(*dec)
        self.assertEqual(code, 0)
        self.assertIn("### D002 — New rule", out)  # (a) dry-run without the flag shows ID and title
        self.write("AGENTS.md", AGENTS_OK.replace(
            "<!-- /ems:rules -->", "2. New. (origin: [D002](DECISIONS.md#d002--new-rule))\n<!-- /ems:rules -->"))  # (b)
        code, _, err = self.run_cli(*dec, "--active-rule", "AGENTS.md rule 2", "--commit")  # (c)
        self.assertEqual(code, 0, err)
        code, out, _ = self.run_cli("check")  # (d)
        self.assertEqual((code, out.strip()), (0, "OK"))


class TestSetStatus(Base):
    def test_only_status_line_changes(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(2) + m_entry(1))
        before = self.text("MEMORY.md")
        code, _, err = self.run_cli("set-status", "M001", "superseded by M002", "--commit")
        self.assertEqual(code, 0, err)
        after = self.text("MEMORY.md")
        diff = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        self.assertEqual(diff, [("- Status: active", "- Status: superseded by M002")])

    def test_dry_run_does_not_write(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1))
        before = self.text("MEMORY.md")
        self.write("MEMORY.md", MEM_HEAD + m_entry(2) + m_entry(1))
        before = self.text("MEMORY.md")
        self.run_cli("set-status", "M001", "superseded by M002")
        self.assertEqual(before, self.text("MEMORY.md"))

    def test_superseded_is_final_without_force(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(3) + m_entry(2) + m_entry(1, status="superseded by M002"))
        code, _, err = self.run_cli("set-status", "M001", "superseded by M003", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("already 'superseded by M002'", err)
        code, _, err = self.run_cli("set-status", "M001", "superseded by M003", "--commit", "--force")
        self.assertEqual(code, 0, err)

    def test_only_superseded_by_is_allowed(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1))
        for status in ("archived (x)", "promoted → AGENTS.md rule 1", "candidate (user)", "active"):
            code, _, err = self.run_cli("set-status", "M001", status, "--commit")
            self.assertNotEqual(code, 0, status)
            self.assertIn("the only status change is 'superseded by M0XX'", err)

    def test_lesson_that_changes_is_a_new_entry_that_supersedes(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1))
        code, _, err = self.add_m()
        self.assertEqual(code, 0, err)
        code, _, err = self.run_cli("set-status", "M001", "superseded by M002", "--commit")
        self.assertEqual(code, 0, err)
        t = self.text("MEMORY.md")
        self.assertLess(t.index("### M002"), t.index("### M001"))
        self.assertIn("- Status: superseded by M002", t)
        self.assertEqual(self.run_cli("check")[1].strip(), "OK")

    def test_d_entry_status(self):
        self.write("DECISIONS.md", DEC_HEAD + d_entry(2, "2026-01-02") + D001)
        code, _, err = self.run_cli("set-status", "D001", "superseded by D002", "--commit")
        self.assertEqual(code, 0, err)
        self.assertIn("- Status: superseded by D002", self.text("DECISIONS.md"))

    def test_invalid_id(self):
        code, _, err = self.run_cli("set-status", "X001", "superseded by X002")
        self.assertNotEqual(code, 0)
        self.assertIn("invalid ID", err)

    def test_multiline_status_rejected(self):
        code, _, err = self.run_cli("set-status", "M001", "superseded by M002\nextra", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("status must be a single line", err)

    def test_id_not_found(self):
        code, _, err = self.run_cli("set-status", "M042", "superseded by M043")
        self.assertNotEqual(code, 0)
        self.assertIn("M042 not found in MEMORY.md", err)

    def test_superseded_by_later_entry_commits(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(2) + m_entry(1))
        code, _, err = self.run_cli("set-status", "M001", "superseded by M002", "--commit")
        self.assertEqual(code, 0, err)
        self.assertIn("- Status: superseded by M002", self.text("MEMORY.md"))


class TestCheck(Base):
    def assert_error(self, needle):
        code, out, _ = self.run_cli("check")
        self.assertNotEqual(code, 0)
        self.assertIn(needle, out)

    def test_clean(self):
        code, out, _ = self.run_cli("check")
        self.assertEqual((code, out.strip()), (0, "OK"))

    def test_agents_too_long(self):
        self.write("AGENTS.md", AGENTS_OK + "x\n" * 140)
        self.assert_error("lines > 150")

    def test_missing_responsibility(self):
        self.write("MEMORY.md", "# MEMORY\n")
        self.assert_error("MEMORY.md: missing ems:responsibility header")

    def test_unclosed_anchor(self):
        self.write("AGENTS.md", AGENTS_OK.replace("<!-- /ems:rules -->", ""))
        self.assert_error("anchor ems:rules")

    def test_duplicate_id(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(2) + m_entry(2))
        self.assert_error("duplicate ID: M002")

    def test_invalid_status(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, status="done"))
        self.assert_error("M001: invalid status 'done'")

    def test_orphan_rule_origin(self):
        self.write("AGENTS.md", AGENTS_OK.replace("(origin: [D001](DECISIONS.md#d001--adopt))", "(origin: M009)"))
        self.assert_error("AGENTS.md rule 1: origin M009 not found")

    def test_missing_skill_path(self):
        self.write("AGENTS.md", AGENTS_OK.replace("project-memory/SKILL.md", "ghost/SKILL.md"))
        self.assert_error("skill path not found: .agents/skills/ghost/SKILL.md")

    def test_d_entry_in_memory_log(self):
        self.write("MEMORY.md", MEM_HEAD + d_entry(2, "2026-01-02"))
        self.assert_error("D002: D entry found in MEMORY.md")

    def test_m_entry_in_decisions_log(self):
        self.write("DECISIONS.md", DEC_HEAD + D001 + m_entry(1))
        self.assert_error("M001: M entry found in DECISIONS.md")

    def test_unrecognised_heading(self):
        self.write("MEMORY.md", MEM_HEAD + "\n### M1 — broken\n- Date: 2026-01-01\n")
        self.assert_error("MEMORY.md: unrecognised heading")

    def test_unknown_field(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Colour: blue\n"))
        self.assert_error("M001: unknown field 'Colour'")

    def test_duplicate_field(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Trigger: again\n"))
        self.assert_error("M001: duplicate field 'Trigger'")

    def test_malformed_line(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="free text inside the entry\n"))
        self.assert_error("M001: malformed line")

    def test_origin_grammar(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Origin: garbage\n"))
        self.assert_error("M001: Origin must be a comma-separated list of M/D IDs")

    def test_superseded_target_missing(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, status="superseded by M999"))
        self.assert_error("M001: superseded by M999 not found")

    def test_superseded_target_must_be_later_same_log(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1) + m_entry(2, status="superseded by M001"))
        self.assert_error("M002: superseded by M001 must be a later entry")

    def test_agents_bare_id_must_be_a_link(self):
        self.write("AGENTS.md", AGENTS_OK.replace("Do the thing.", "Do the thing, see D001."))
        self.assert_error("AGENTS.md: D001 is not a link to its entry (get it with: memory.py link D001)")

    def test_agents_link_with_wrong_anchor(self):
        self.write("AGENTS.md", AGENTS_OK.replace("#d001--adopt", "#d001--other"))
        self.assert_error("AGENTS.md: link to D001 must be [D001](DECISIONS.md#d001--adopt)")

    def test_agents_link_to_missing_entry(self):
        self.write("AGENTS.md", AGENTS_OK.replace("Do the thing.", "Do the thing, see [D007](DECISIONS.md#d007--x)."))
        self.assert_error("AGENTS.md: link to D007, which is not found")

    def test_link_command_prints_anchor(self):
        code, out, _ = self.run_cli("link", "D001")
        self.assertEqual((code, out.strip()), (0, "[D001](DECISIONS.md#d001--adopt)"))

    def test_entries_must_be_newest_first(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1) + m_entry(2))
        self.assert_error("MEMORY.md: entries must be newest first")

    def test_active_rule_must_exist(self):
        self.write("DECISIONS.md", DEC_HEAD + d_entry(2, "2026-01-02", "- Active rule: AGENTS.md rule 7\n") + D001)
        self.assert_error("D002: Active rule AGENTS.md rule 7 not found")

    def test_active_rule_must_be_cited_by_the_rule(self):
        self.write("DECISIONS.md", DEC_HEAD + d_entry(2, "2026-01-02", "- Active rule: AGENTS.md rule 1\n") + D001)
        self.assert_error("D002: AGENTS.md rule 1 does not cite (origin: D002)")

    def test_active_rule_ok(self):
        self.write("DECISIONS.md", DEC_HEAD + D001.rstrip() + "\n- Active rule: AGENTS.md rule 1\n")
        code, out, _ = self.run_cli("check")
        self.assertEqual((code, out.strip()), (0, "OK"))

    def test_active_rule_grammar(self):
        self.write("DECISIONS.md", DEC_HEAD + D001.rstrip() + "\n- Active rule: rule one\n")
        self.assert_error("D001: Active rule must start with 'AGENTS.md rule N'")

    def test_active_rule_multi_rule_form(self):
        two = AGENTS_OK.replace("<!-- /ems:rules -->",
                                "2. Other. (origin: [D001](DECISIONS.md#d001--adopt))\n<!-- /ems:rules -->")
        self.write("AGENTS.md", two)
        self.write("DECISIONS.md", DEC_HEAD + D001.rstrip() + "\n- Active rule: AGENTS.md rules 1 and 2\n")
        code, out, _ = self.run_cli("check")
        self.assertEqual((code, out.strip()), (0, "OK"))
        self.write("DECISIONS.md", DEC_HEAD + D001.rstrip() + "\n- Active rule: AGENTS.md rules 1 and 3\n")
        self.assert_error("D001: Active rule AGENTS.md rule 3 not found")

    def test_active_rule_with_oxford_comma_checks_every_rule(self):
        self.write("DECISIONS.md", DEC_HEAD + D001.rstrip() + "\n- Active rule: AGENTS.md rules 1, 2, and 3\n")
        self.assert_error("D001: Active rule AGENTS.md rule 3 not found")

    def test_active_rule_ignores_ids_after_the_rule_list(self):
        self.write("DECISIONS.md", DEC_HEAD + D001.rstrip() + "\n- Active rule: AGENTS.md rule 1, see D001\n")
        code, out, _ = self.run_cli("check")
        self.assertEqual((code, out.strip()), (0, "OK"))

    def test_link_slug_with_punctuation(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1).replace("— t1", "— Fix `a_b` in x.md / y"))
        code, out, _ = self.run_cli("link", "M001")
        self.assertEqual((code, out.strip()), (0, "[M001](MEMORY.md#m001--fix-a_b-in-xmd--y)"))

    def test_rule_without_origin(self):
        self.write("AGENTS.md", AGENTS_OK.replace(" (origin: [D001](DECISIONS.md#d001--adopt))", ""))
        self.assert_error("AGENTS.md rule 1: missing (origin")

    def test_invalid_date(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, date="9-nov"))
        self.assert_error("M001: invalid Date '9-nov'")

    def test_origin_repeats_an_id(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Origin: D001, D001\n"))
        self.assert_error("M001: Origin repeats an ID")

    def test_origin_cites_itself(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Origin: M001\n"))
        self.assert_error("M001: Origin cites itself")

    def test_impossible_calendar_date(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, date="2026-13-45"))
        self.assert_error("M001: invalid Date '2026-13-45'")

    def test_quoted_french_is_fine_and_unquoted_is_not(self):
        code, _, err = self.add_m("--evidence", "User: «les dates toujours en AAAA-MM-JJ, s'il vous plaît»")
        self.assertEqual(code, 0, err)
        code, _, err = self.run_cli("add", "--type", "M", "--title", "x", "--entry-type", "finding",
                                    "--trigger", "t", "--learning", "Toujours vérifier", "--evidence", "e", "--commit")
        self.assertNotEqual(code, 0)
        self.assertIn("non-English character 'é' in Learning", err)

    def test_symbols_are_not_letters(self):
        code, _, err = self.add_m("--learning", "Step a → step b — always · in order")
        self.assertEqual(code, 0, err)

    def test_unfilled_placeholder(self):
        self.write("AGENTS.md", AGENTS_OK.replace("map", "{{FILL:project}}"))
        self.assert_error("AGENTS.md: unfilled placeholder {{FILL:project}}")

    def test_claude_md_must_import_agents(self):
        self.write("CLAUDE.md", "@MEMORY.md\n")
        self.assert_error("CLAUDE.md: must import @AGENTS.md")
        self.write("CLAUDE.md", "@AGENTS.md\n@MEMORY.md\n")
        self.assertEqual(self.run_cli("check")[1].strip(), "OK")

    def test_old_statuses_are_invalid(self):
        for st in ("archived (x)", "promoted → AGENTS.md rule 1", "candidate (user)"):
            self.write("MEMORY.md", MEM_HEAD + m_entry(1, status=st))
            self.assert_error(f"M001: invalid status '{st}'")

    def test_topic_and_repeats_are_unknown_fields(self):
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Topic: agent\n"))
        self.assert_error("M001: unknown field 'Topic'")
        self.write("MEMORY.md", MEM_HEAD + m_entry(1, extra="- Repeats: M001\n"))
        self.assert_error("M001: unknown field 'Repeats'")

    def test_link_to_missing_entry(self):
        code, _, _ = self.run_cli("link", "M042")
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
