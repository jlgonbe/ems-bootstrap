"""Tests for scripts/setup.py (stdlib unittest). Run from the package:
python3 -B -m unittest discover -s tests -v
"""
import io
import re
import shutil
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "scripts"))
import setup  # noqa: E402

BASE = ["--project-name", "Recetas", "--project", "A recipe site built with Astro.", "--how", "npm run dev; npm test.",
        "--language", "Spanish", "--triggers", "«guarda esto», «apunta esto», «cierra la tarea»"]


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_setup(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = setup.main(["--root", str(self.root), *BASE, *args])
        return code, out.getvalue()

    def check(self):
        r = subprocess.run([sys.executable, str(self.root / ".agents/skills/project-memory/scripts/memory.py"),
                            "--root", str(self.root), "check"], capture_output=True, text=True)
        return r.returncode, r.stdout.strip()

    def files(self):
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file())

    def test_both_harnesses(self):
        code, out = self.run_setup("--harness", "opencode,claude", "--planner-model-opencode", "anthropic/claude-opus-5-5",
                                   "--executor-model-opencode", "anthropic/claude-sonnet-5-5",
                                   "--planner-model-claude", "opus", "--executor-model-claude", "sonnet")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.check(), (0, "OK"))
        for rel in ("AGENTS.md", "CLAUDE.md", "MEMORY.md", "DECISIONS.md", "opencode.json",
                    ".agents/skills/project-memory/SKILL.md", ".agents/skills/project-memory/scripts/memory.py",
                    ".agents/skills/project-memory/references/entry-format.md",
                    ".opencode/agents/project-planner.md", ".opencode/agents/project-plan-executor.md",
                    ".claude/agents/project-planner.md", ".claude/agents/project-plan-executor.md",
                    ".claude/skills/project-memory/SKILL.md"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertTrue((self.root / ".claude/skills/project-memory").is_symlink())
        self.assertIn("model: anthropic/claude-opus-5-5", (self.root / ".opencode/agents/project-planner.md").read_text())
        self.assertIn("model: sonnet", (self.root / ".claude/agents/project-plan-executor.md").read_text())
        self.assertEqual((self.root / "DECISIONS.md").read_text().count("### D0"), 1)
        self.assertIn("«guarda esto», «apunta esto»", (self.root / ".agents/skills/project-memory/SKILL.md").read_text())
        self.assertIn("@AGENTS.md\n@MEMORY.md", (self.root / "CLAUDE.md").read_text())
        self.assertIn('"instructions": ["MEMORY.md"]', (self.root / "opencode.json").read_text())

    def test_opencode_only(self):
        code, out = self.run_setup("--harness", "opencode")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.check(), (0, "OK"))
        self.assertFalse((self.root / ".claude/agents").exists())
        self.assertFalse((self.root / ".claude/skills").exists())
        self.assertTrue((self.root / "CLAUDE.md").exists())  # AGENTS.md and CLAUDE.md always go together
        self.assertNotIn("model:", (self.root / ".opencode/agents/project-planner.md").read_text())
        self.assertNotIn(".claude/agents", (self.root / "AGENTS.md").read_text())

    def test_claude_only(self):
        code, out = self.run_setup("--harness", "claude")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.check(), (0, "OK"))
        self.assertFalse((self.root / "opencode.json").exists())
        self.assertFalse((self.root / ".opencode").exists())

    def test_existing_project_aborts_writing_nothing(self):
        (self.root / "CLAUDE.md").write_text("# old", encoding="utf-8")
        before = self.files()
        code, out = self.run_setup("--harness", "opencode,claude")
        self.assertEqual(code, 1)
        self.assertIn("not a new project: CLAUDE.md already exists", out)
        self.assertIn("nothing written", out)
        self.assertEqual(before, self.files())

    def test_non_english_answer_rejected_writing_nothing(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = setup.main(["--root", str(self.root), "--project-name", "Recetas", "--project", "Una web de recetas",
                               "--how", "npm", "--language", "Español", "--harness", "claude"])
        self.assertEqual(code, 2)
        self.assertIn("--language must be written in English", out.getvalue())
        self.assertEqual(self.files(), [])

    def test_bad_opencode_model_rejected(self):
        code, out = self.run_setup("--harness", "opencode", "--planner-model-opencode", "opus")
        self.assertEqual(code, 2)
        self.assertIn("provider/model-id", out)
        self.assertEqual(self.files(), [])

    def test_unknown_harness_rejected(self):
        code, out = self.run_setup("--harness", "cursor")
        self.assertEqual(code, 2)
        self.assertIn("--harness must be", out)

    def test_sandbox_blocking_claude_folder_stages_files(self):
        real_write, real_mkdir = Path.write_text, Path.mkdir

        def blocked(path):  # as Claude Code's sandbox: any path under a .claude/agents or .claude/skills segment
            s = path.as_posix()
            return "/.claude/agents" in s or "/.claude/skills" in s

        def write_text(path, *a, **k):
            if blocked(path):
                raise PermissionError(f"Operation not permitted: '{path}'")
            return real_write(path, *a, **k)

        def mkdir(path, *a, **k):
            if blocked(path):
                raise PermissionError(f"Operation not permitted: '{path}'")
            return real_mkdir(path, *a, **k)

        with mock.patch.object(Path, "write_text", write_text), mock.patch.object(Path, "mkdir", mkdir), \
                mock.patch.object(Path, "symlink_to", side_effect=PermissionError("blocked")):
            code, out = self.run_setup("--harness", "claude", "--planner-model-claude", "opus")
        self.assertEqual(code, 5, out)
        self.assertIn("check: OK", out)
        self.assertIn("pending: the harness sandbox did not let this script write these files", out)
        for rel in (".claude/agents/project-planner.md", ".claude/agents/project-plan-executor.md",
                    ".claude/skills/project-memory/SKILL.md", ".claude/skills/project-memory/scripts/memory.py"):
            staged = ".ems-pending/claude/" + rel[len(".claude/"):]
            self.assertIn(f"  {rel} <- {staged}", out)
            self.assertTrue((self.root / staged).exists(), staged)
        self.assertFalse((self.root / ".ems-pending/.claude").exists())  # the sandbox blocks any .claude segment
        self.assertIn("model: opus", (self.root / ".ems-pending/claude/agents/project-planner.md").read_text())
        self.assertEqual(self.check(), (0, "OK"))

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_codex_agents_are_valid_toml(self):
        code, out = self.run_setup("--harness", "codex", "--planner-model-codex", "gpt-6.2-sol",
                                   "--executor-model-codex", "gpt-6-luna")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.check(), (0, "OK"))
        for name, model in (("project-planner", "gpt-6.2-sol"), ("project-plan-executor", "gpt-6-luna")):
            agent = tomllib.loads((self.root / f".codex/agents/{name}.toml").read_text(encoding="utf-8"))
            self.assertEqual(agent["name"], name)
            self.assertEqual(agent["model"], model)
            self.assertTrue(agent["description"] and agent["developer_instructions"].strip())
        self.assertIn("never edit files yourself", tomllib.loads(
            (self.root / ".codex/agents/project-planner.toml").read_text(encoding="utf-8"))["developer_instructions"])
        self.assertFalse((self.root / "opencode.json").exists())
        self.assertIn("`.codex/agents/project-planner.toml`", (self.root / "AGENTS.md").read_text())

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_codex_without_models_inherits_the_session_model(self):
        code, out = self.run_setup("--harness", "codex")
        self.assertEqual(code, 0, out)
        agent = tomllib.loads((self.root / ".codex/agents/project-planner.toml").read_text(encoding="utf-8"))
        self.assertNotIn("model", agent)

    def test_codex_sandbox_on_agents_and_codex_stages_files(self):
        real_write, real_mkdir = Path.write_text, Path.mkdir

        def blocked(path):  # as Codex's workspace-write sandbox: .agents and .codex are read-only
            root = self.root.resolve()
            parts = path.relative_to(root).parts if path.is_relative_to(root) else ()
            return bool(parts) and parts[0] in (".agents", ".codex")

        def write_text(path, *a, **k):
            if blocked(path):
                raise PermissionError(f"Operation not permitted: '{path}'")
            return real_write(path, *a, **k)

        def mkdir(path, *a, **k):
            if blocked(path):
                raise PermissionError(f"Operation not permitted: '{path}'")
            return real_mkdir(path, *a, **k)

        with mock.patch.object(Path, "write_text", write_text), mock.patch.object(Path, "mkdir", mkdir):
            code, out = self.run_setup("--harness", "codex", "--planner-model-codex", "gpt-6.2-sol")
        self.assertEqual(code, 5, out)
        self.assertIn("check: OK", out)
        pending = [l.strip() for l in out.splitlines() if " <- .ems-pending/" in l]
        self.assertEqual(sorted(l.split(" <- ")[0] for l in pending), sorted([
            ".agents/skills/project-memory/SKILL.md", ".agents/skills/project-memory/references/entry-format.md",
            ".agents/skills/project-memory/scripts/memory.py",
            ".codex/agents/project-planner.toml", ".codex/agents/project-plan-executor.toml"]))
        self.assertIn("- Status: accepted", (self.root / "DECISIONS.md").read_text())  # D001 written anyway
        for line in pending:  # what the agent does with its own file tool
            target, staged = line.split(" <- ")
            (self.root / target).parent.mkdir(parents=True, exist_ok=True)
            (self.root / target).write_text((self.root / staged).read_text(encoding="utf-8"), encoding="utf-8")
        shutil.rmtree(self.root / ".ems-pending")
        self.assertEqual(self.check(), (0, "OK"))
        self.assertIn('model = "gpt-6.2-sol"', (self.root / ".codex/agents/project-planner.toml").read_text())

    def test_unexpected_permission_error_is_not_hidden(self):
        real_write = Path.write_text

        def write_text(path, *a, **k):
            if path.name == "MEMORY.md":
                raise PermissionError("blocked")
            return real_write(path, *a, **k)

        with mock.patch.object(Path, "write_text", write_text):
            code, out = self.run_setup("--harness", "codex")
        self.assertEqual(code, 6, out)
        self.assertIn("PermissionError", out)
        self.assertEqual(list(self.root.iterdir()), [])  # AGENTS.md and CLAUDE.md, written before, are gone

    def frontmatter(self, rel):
        text = (self.root / rel).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), rel)
        head = text.split("---\n", 2)[1]
        fields = {}
        for line in head.splitlines():
            if line and not line.startswith(" "):
                key, _, value = line.partition(":")
                fields[key] = value.strip()
        return fields, text.split("---\n", 2)[2]

    def test_markdown_agents_follow_each_harness_schema(self):
        code, out = self.run_setup("--harness", "opencode,claude", "--planner-model-claude", "opus",
                                   "--planner-model-opencode", "anthropic/claude-opus-5-5")
        self.assertEqual(code, 0, out)
        claude_tools = {"Read", "Grep", "Glob", "Bash", "Edit", "Write", "WebFetch", "WebSearch"}
        for name in ("project-planner", "project-plan-executor"):
            fields, body = self.frontmatter(f".claude/agents/{name}.md")
            self.assertEqual(fields["name"], name)
            self.assertTrue(fields["description"].startswith('"') and fields["description"].endswith('"'))
            for tool in filter(None, (t.strip() for t in fields.get("tools", "").split(","))):
                self.assertIn(tool, claude_tools)
            self.assertTrue(body.strip())
            fields, body = self.frontmatter(f".opencode/agents/{name}.md")
            self.assertIn(fields["mode"], {"primary", "subagent", "all"})
            self.assertTrue(fields["description"].startswith('"') and fields["description"].endswith('"'))
            self.assertNotIn("permissions", fields)  # V1 format: read by OpenCode 1 and translated by OpenCode 2
        self.assertEqual(self.frontmatter(".claude/agents/project-planner.md")[0]["tools"], "Read, Grep, Glob")
        self.assertEqual(self.frontmatter(".claude/agents/project-planner.md")[0]["model"], "opus")
        planner = (self.root / ".opencode/agents/project-planner.md").read_text(encoding="utf-8")
        self.assertIn("permission:\n  edit: deny\n  bash: ask\n  task: deny\n", planner)
        self.assertEqual(self.frontmatter(".claude/agents/project-planner.md")[0]["effort"], "high")
        self.assertNotIn("effort", self.frontmatter(".claude/agents/project-plan-executor.md")[0])
        for marker in ("Created:", "Status: proposed", "File: plans/<YYYY-MM-DD>_", "## Phase 1", "- [ ] 1.1", "Evidence:", "## Execution log"):
            self.assertIn(marker, planner)
        executor = (self.root / ".opencode/agents/project-plan-executor.md").read_text(encoding="utf-8")
        self.assertIn("plans/<YYYY-MM-DD>_", executor)
        self.assertIn("Never mark a step without its evidence", executor)
        self.assertIn("Status: completed <today>", executor)

    def test_codex_planner_gets_high_reasoning_only_with_a_model(self):
        self.run_setup("--harness", "codex", "--planner-model-codex", "gpt-6.2-sol", "--executor-model-codex", "gpt-6-luna")
        planner = (self.root / ".codex/agents/project-planner.toml").read_text(encoding="utf-8")
        executor = (self.root / ".codex/agents/project-plan-executor.toml").read_text(encoding="utf-8")
        self.assertIn('model_reasoning_effort = "high"', planner)
        self.assertNotIn("model_reasoning_effort", executor)
        if tomllib:
            self.assertEqual(tomllib.loads(planner)["model_reasoning_effort"], "high")

    def test_agents_md_maps_the_plans_folder(self):
        self.run_setup("--harness", "claude")
        self.assertIn("| `plans/` |", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_proper_name_inside_quotes_is_accepted(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = setup.main(["--root", str(self.root), "--project-name", "Bitácora", "--project",
                               "The newsletter «Bitácora de un Ingeniero de Software».", "--how", "Not defined yet.",
                               "--language", "Spanish", "--harness", "opencode"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(self.check(), (0, "OK"))

    def test_triggers_that_overflow_the_description_are_rejected(self):
        code, out = self.run_setup("--harness", "opencode", "--triggers", ", ".join(["«apunta esto ahora mismo»"] * 40))
        self.assertEqual(code, 2)
        self.assertIn("--triggers is too long", out)
        self.assertEqual(self.files(), [])

    def test_failed_d001_rolls_back_everything(self):
        (self.root / ".claude/.cc-writes").mkdir(parents=True)  # housekeeping that existed before stays
        real_run = setup.subprocess.run

        def failing_add(cmd, *a, **k):
            if "add" in cmd:
                return real_run([sys.executable, "-c", "import sys; print('boom'); sys.exit(2)"], *a, **k)
            return real_run(cmd, *a, **k)

        with mock.patch.object(setup.subprocess, "run", failing_add):
            code, out = self.run_setup("--harness", "opencode,claude")
        self.assertEqual(code, 3)
        self.assertIn("everything this run created was removed", out)
        self.assertEqual([str(p.relative_to(self.root)) for p in sorted(self.root.rglob("*"))],
                         [".claude", ".claude/.cc-writes"])
        code, out = self.run_setup("--harness", "opencode,claude")  # a retry now passes the gate
        self.assertEqual(code, 0, out)

    def test_failed_check_rolls_back_everything(self):
        real_run = setup.subprocess.run

        def failing_check(cmd, *a, **k):
            if cmd[-1] == "check":
                return real_run([sys.executable, "-c", "import sys; print('FAILED: 1 error(s)'); sys.exit(1)"], *a, **k)
            return real_run(cmd, *a, **k)

        with mock.patch.object(setup.subprocess, "run", failing_check):
            code, out = self.run_setup("--harness", "opencode,claude")
        self.assertEqual(code, 4)
        self.assertIn("everything this run created was removed", out)
        self.assertEqual(self.files(), [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_generated_tree_has_no_placeholder(self):
        self.run_setup("--harness", "opencode,claude")
        for p in self.root.rglob("*"):
            if p.is_file():
                self.assertIsNone(re.search(r"\{\{FILL:[a-z_]+\}\}", p.read_text(encoding="utf-8")), str(p))


if __name__ == "__main__":
    unittest.main()
