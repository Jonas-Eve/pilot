#!/usr/bin/env python3
"""Tests for scripts/lint_pilot.py. Run: python3 -m unittest scripts/test_lint_pilot.py"""
import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import subprocess
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

    def test_unknown_pilot_command(self):
        self.edit(".claude/skills/pilot-dev/SKILL.md", lambda t: t + "\nRun `python3 .pilot/pilot.py nope --x`.\n")
        self.assertTrue(self.errors("command"))

    def test_agent_duty_missing(self):
        self.edit(".claude/agents/pilot-dev.md", lambda t: t.replace("pilot-task-implement.md", "pilot-task-ghost.md"))
        self.assertTrue(self.errors("agent-duties"))

    def test_skill_name_mismatch(self):
        self.edit(".claude/skills/pilot-dev/SKILL.md", lambda t: t.replace("name: pilot-dev", "name: pilot-devx", 1))
        self.assertTrue(self.errors("frontmatter"))

    def test_unbalanced_marker(self):
        self.edit("assets/templates/CLAUDE.md.tmpl", lambda t: t.replace("<!-- PILOT:INTRO:END -->", "", 1))
        self.assertTrue(self.errors("marker"))


class HookTests(unittest.TestCase):
    def run_hook(self, mode, rel):
        import json, subprocess, sys
        payload = json.dumps({"tool_input": {"file_path": str(REPO / rel)}})
        return subprocess.run([sys.executable, str(HERE / "hooks" / "repo_hook.py"), mode], input=payload,
                              capture_output=True, text=True).returncode

    def test_guard_refuses_owned_copies(self):
        self.assertEqual(self.run_hook("guard", ".pilot/pilot.py"), 2)
        self.assertEqual(self.run_hook("guard", ".github/workflows/pilot-status-on-merge.yml"), 2)
        self.assertEqual(self.run_hook("guard", "scripts/pilot.py"), 0)

    def test_lint_hook_passes_on_clean_repo(self):
        self.assertEqual(self.run_hook("lint", "CLAUDE.md"), 0)
        self.assertEqual(self.run_hook("lint", "README.md"), 0)


class ReviewGateTests(unittest.TestCase):
    """The PR gate refuses until a passing maintainer review of the exact diff was recorded."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("repo_hook", HERE / "hooks" / "repo_hook.py")
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.session = f"gate-{os.getpid()}-{id(self)}"
        self.addCleanup(lambda: self.hook.review_marker(self.session).unlink(missing_ok=True))
        for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *cmd], cwd=self.root, check=True)
        (self.root / "CLAUDE.md").write_text("base\n")
        (self.root / "notes.txt").write_text("base\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root, check=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=self.root, check=True)

    def gate(self, tool="mcp__github__create_pull_request", **params):
        payload = {"session_id": self.session, "tool_name": tool, "tool_input": params}
        with contextlib.redirect_stderr(io.StringIO()):
            return self.hook.main_safe(payload, self.root)

    def review(self, verdict, prompt="Read docs/maintainer-review.md and review the diff"):
        payload = {"session_id": self.session, "tool_name": "Agent", "tool_input": {"prompt": prompt},
                   "tool_response": {"content": [{"type": "text", "text": f"VERDICT: {verdict}\nnotes"}]}}
        self.hook.review_track(payload, self.root)

    def edit(self, name="CLAUDE.md", text="changed\n"):
        (self.root / name).write_text(text)

    def test_a_change_to_nothing_projects_copy_needs_no_review(self):
        self.edit("notes.txt")
        self.assertEqual(self.gate(), 0)

    def test_the_pr_tool_is_gated_whatever_the_server_is_called(self):
        self.edit()
        self.assertEqual(self.gate("mcp__GitHub__create_pull_request"), 2)
        self.assertEqual(self.gate("mcp__github__create_pull_request"), 2)
        self.assertEqual(self.gate("mcp__github__get_file_contents"), 0)

    def test_a_shipped_change_is_refused_until_a_review_passed(self):
        self.edit()
        self.assertEqual(self.gate(), 2)
        self.review("PASS")
        self.assertEqual(self.gate(), 0)

    def test_a_review_with_findings_does_not_open_the_gate(self):
        self.edit()
        self.review("FINDINGS")
        self.assertEqual(self.gate(), 2)

    def test_the_pass_counts_only_for_the_diff_it_saw(self):
        self.edit()
        self.review("PASS")
        self.edit(text="changed again\n")
        self.assertEqual(self.gate(), 2)

    def test_an_untracked_new_file_is_part_of_the_diff(self):
        self.edit("notes.txt")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "new.md").write_text("x")
        self.assertEqual(self.gate(), 2)

    def test_an_agent_that_is_not_the_review_records_nothing(self):
        self.edit()
        self.review("PASS", prompt="Summarize the repository")
        self.assertEqual(self.gate(), 2)

    def test_only_a_real_pr_creation_command_is_gated(self):
        self.edit()
        self.assertEqual(self.gate("Bash", command="gh pr create --title x"), 2)
        self.assertEqual(self.gate("Bash", command="cd x && gh pr create --title x"), 2)
        self.assertEqual(self.gate("Bash", command="gh pr view 5"), 0)
        self.assertEqual(self.gate("Bash", command="git push"), 0)
        self.assertEqual(self.gate("Bash", command='echo "then run gh pr create"'), 0)
        self.assertEqual(self.gate("Bash", command="cat <<'EOF'\ngh pr create\nEOF"), 0)

    def test_without_git_history_the_gate_stays_open(self):
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        payload = {"session_id": self.session, "tool_name": "mcp__github__create_pull_request", "tool_input": {}}
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.hook.main_safe(payload, other.name), 0)


if __name__ == "__main__":
    unittest.main()
