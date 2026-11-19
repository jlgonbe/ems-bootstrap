"""Tests for scripts/gate.py (stdlib unittest; git must be installed). Run from the package:
python3 -B -m unittest discover -s tests -v
"""
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gate  # noqa: E402


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin",
                        "HOME": str(root)})


def commit(root, name):
    (root / name).write_text(name, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-m", name)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate.main(["--root", str(self.root)])
        return code, out.getvalue().strip()

    def test_empty_dir_is_new(self):
        self.assertEqual(self.run_gate(), (0, "new project"))

    def test_git_without_commits_is_new(self):
        git(self.root, "init", "-q")
        self.assertEqual(self.run_gate(), (0, "new project"))

    def test_scaffold_with_one_commit_is_new(self):
        git(self.root, "init", "-q")
        (self.root / "src").mkdir()
        (self.root / "src/index.js").write_text("console.log(1)", encoding="utf-8")
        (self.root / "README.md").write_text("# app", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "scaffold")
        self.assertEqual(self.run_gate(), (0, "new project"))

    def test_two_commits_is_history(self):
        git(self.root, "init", "-q")
        commit(self.root, "a.txt")
        commit(self.root, "b.txt")
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("git history has 2 commits", out)

    def test_each_offending_path_stops(self):
        for name in gate.OFFENDING:
            with self.subTest(name=name):
                path = self.root / name
                if name.startswith("."):
                    path.mkdir()
                    (path / "ctx.md").write_text("x", encoding="utf-8")
                else:
                    path.write_text("x", encoding="utf-8")
                code, out = self.run_gate()
                self.assertEqual(code, 1)
                self.assertIn(f"{name} already exists", out)
                if path.is_dir():
                    (path / "ctx.md").unlink()
                    path.rmdir()
                else:
                    path.unlink()

    def test_harness_housekeeping_is_not_context(self):
        (self.root / ".claude/.cc-writes").mkdir(parents=True)
        (self.root / ".claude/settings.local.json").write_text("{}", encoding="utf-8")
        (self.root / ".opencode/node_modules").mkdir(parents=True)
        (self.root / ".opencode/.gitignore").write_text("node_modules", encoding="utf-8")
        self.assertEqual(self.run_gate(), (0, "new project"))
        (self.root / ".agents/skills/x").mkdir(parents=True)
        code, out = self.run_gate()
        self.assertEqual((code, out), (1, "not a new project: .agents already exists"))

    def test_empty_harness_folder_is_not_context(self):
        (self.root / ".claude").mkdir()
        self.assertEqual(self.run_gate(), (0, "new project"))

    def test_harness_folder_with_context_stops(self):
        (self.root / ".claude/.cc-writes").mkdir(parents=True)
        (self.root / ".claude/agents").mkdir()
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn(".claude already exists", out)

    def test_this_skill_installed_in_the_project_is_not_context(self):
        for harness in (".claude", ".agents", ".codex", ".opencode"):
            with self.subTest(harness=harness):
                (self.root / harness / "skills/ems-bootstrap").mkdir(parents=True)
                self.assertEqual(self.run_gate(), (0, "new project"))
                (self.root / harness / "skills/other").mkdir()
                self.assertEqual(self.run_gate()[0], 1)
                import shutil
                shutil.rmtree(self.root / harness)

    def test_gate_writes_nothing(self):
        (self.root / "AGENTS.md").write_text("# old", encoding="utf-8")
        before = sorted(p.name for p in self.root.iterdir())
        self.run_gate()
        self.assertEqual(before, sorted(p.name for p in self.root.iterdir()))
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8"), "# old")


if __name__ == "__main__":
    unittest.main()
