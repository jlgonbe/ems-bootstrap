"""Tests for install.py (stdlib unittest). Run from the package: python3 -B -m unittest discover -s tests -v"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install  # noqa: E402


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "skills" / "ems-bootstrap"

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = install.main(["--harness", "codex", "--dest", str(self.dest), *args])
        return code, out.getvalue()

    def test_installs_only_what_the_skill_needs(self):
        code, out = self.run_install()
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["SKILL.md", "assets", "references", "scripts"])
        self.assertTrue((self.dest / "scripts/setup.py").exists())
        self.assertFalse(list(self.dest.rglob("__pycache__")))
        self.assertIn("monta el sistema de memoria", out)

    def test_existing_installation_needs_replace(self):
        self.run_install()
        (self.dest / "marker").write_text("x", encoding="utf-8")
        code, out = self.run_install()
        self.assertEqual(code, 2)
        self.assertTrue((self.dest / "marker").exists())
        code, out = self.run_install("--replace")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.dest / "marker").exists())

    def test_default_destinations(self):
        self.assertEqual(install.DESTS["claude"], "~/.claude/skills/ems-bootstrap")
        self.assertEqual(install.DESTS["opencode"], install.DESTS["codex"])


if __name__ == "__main__":
    unittest.main()
