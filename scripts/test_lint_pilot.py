#!/usr/bin/env python3
"""Tests for scripts/lint_pilot.py. Run: python3 -m unittest scripts/test_lint_pilot.py"""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lint_pilot", HERE / "lint_pilot.py")
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)
REPO = HERE.parent


class LintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        for d in (".claude", "assets", "scripts"):
            src = REPO / d
            shutil.copytree(src, self.root / d, ignore=shutil.ignore_patterns("lab", "bench", "__pycache__"))
        shutil.copy(REPO / "CLAUDE.md", self.root / "CLAUDE.md")

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, rule=None):
        return [f for f in lint.Linter(self.root).run() if f[0] == "error" and (rule is None or f[1] == rule)]

    def edit(self, rel, fn):
        p = self.root / rel
        p.write_text(fn(p.read_text()))

    def test_repo_is_clean(self):
        self.assertEqual(lint.Linter(REPO).run() and [f for f in lint.Linter(REPO).run() if f[0] == "error"], [])

    def test_missing_doc_reference(self):
        self.edit(".claude/skills/pilot-dev/SKILL.md", lambda t: t + "\nSee pilot-task-nope.md\n")
        self.assertTrue(self.errors("doc-ref"))

    def test_orphan_doc(self):
        (self.root / "assets/docs/pilot-link-lonely.md").write_text("x")
        self.assertTrue(self.errors("orphan-doc"))

    def test_unknown_label(self):
        self.edit("assets/docs/pilot-task-implement.md", lambda t: t + "\nSet `status:bogus`.\n")
        self.assertTrue(self.errors("label"))

    def test_agent_duty_missing(self):
        self.edit(".claude/agents/pilot-dev.md", lambda t: t.replace("pilot-task-implement.md", "pilot-task-ghost.md"))
        self.assertTrue(self.errors("agent-duties"))

    def test_skill_name_mismatch(self):
        self.edit(".claude/skills/pilot-dev/SKILL.md", lambda t: t.replace("name: pilot-dev", "name: pilot-devx", 1))
        self.assertTrue(self.errors("frontmatter"))

    def test_unbalanced_marker(self):
        self.edit("assets/templates/CLAUDE.md.tmpl", lambda t: t.replace("<!-- PILOT:INTRO:END -->", "", 1))
        self.assertTrue(self.errors("marker"))


if __name__ == "__main__":
    unittest.main()
