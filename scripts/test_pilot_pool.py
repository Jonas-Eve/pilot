#!/usr/bin/env python3
"""Offline tests for scripts/pilot-pool.py. Run: python3 -m unittest scripts/test_pilot_pool.py"""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location(
    "pilot_pool", pathlib.Path(__file__).with_name("pilot-pool.py")
)
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)


def issue(number, labels, body="", assignees=(), created="2026-01-01T00:00:00Z"):
    return {
        "number": number,
        "title": f"t{number}",
        "labels": [{"name": l} for l in labels],
        "assignees": [{"login": a} for a in assignees],
        "body": body,
        "created_at": created,
    }


class FakeGh:
    def __init__(self, issues, states=None, comments=None):
        self.issues, self.states, self.comment_map = issues, states or {}, comments or {}

    def issues_with_label(self, label):
        return [i for i in self.issues if label in [l["name"] for l in i["labels"]]]

    def is_open(self, number):
        return self.states.get(number)

    def comments(self, number):
        return self.comment_map.get(number, [])


def picks(phase, issues, **kw):
    result = pool.Select(FakeGh(issues, **kw)).run(phase, 10)
    return [c["number"] for c in result["candidates"]], {e["number"]: e["reason"] for e in result["excluded"]}


class PoolTests(unittest.TestCase):
    def test_fresh_pool_skips_assigned_and_flagged(self):
        got, ex = picks("dev", [
            issue(1, ["status:dev-ready"]),
            issue(2, ["status:dev-ready"], assignees=["a"]),
            issue(3, ["status:dev-ready", "needs-human"]),
            issue(4, ["status:dev-ready", "on-hold"]),
        ])
        self.assertEqual(got, [1])
        self.assertEqual(ex, {2: "assigned", 3: "needs-human", 4: "on-hold"})

    def test_dependency_gate_open_closed_unknown(self):
        got, ex = picks("dev", [
            issue(1, ["status:dev-ready"], body="Depends on #10"),
            issue(2, ["status:dev-ready"], body="Depends on #11"),
            issue(3, ["status:dev-ready"], body="Depends on #12"),
        ], states={10: True, 11: False, 12: None})
        self.assertEqual(got, [2])
        self.assertEqual(ex, {1: "depends-on-open", 3: "depends-on-open"})

    def test_one_open_dependency_among_several_blocks(self):
        got, _ = picks("dev", [issue(1, ["status:dev-ready"], body="Depends on #10\nDepends on #11")],
                       states={10: False, 11: True})
        self.assertEqual(got, [])

    def test_priority_then_blocks_then_oldest(self):
        got, _ = picks("dev", [
            issue(1, ["status:dev-ready", "priority:P1"], created="2026-01-01T00:00:00Z"),
            issue(2, ["status:dev-ready", "priority:P0"], created="2026-03-01T00:00:00Z"),
            issue(3, ["status:dev-ready", "priority:P0"], created="2026-02-01T00:00:00Z"),
            issue(4, ["status:dev-ready"], created="2025-01-01T00:00:00Z"),
        ])
        self.assertEqual(got, [3, 2, 1, 4])
        got, _ = picks("dev", [
            issue(2, ["status:dev-ready", "priority:P0"], created="2026-03-01T00:00:00Z"),
            issue(3, ["status:dev-ready", "priority:P0"], created="2026-02-01T00:00:00Z"),
        ], states={50: True}, comments={2: ["Blocks #50"]})
        self.assertEqual(got, [2, 3])

    def test_blocks_ignored_when_blocked_ticket_is_closed(self):
        got, _ = picks("dev", [
            issue(2, ["status:dev-ready", "priority:P0"], created="2026-03-01T00:00:00Z"),
            issue(3, ["status:dev-ready", "priority:P0"], created="2026-02-01T00:00:00Z"),
        ], states={50: False}, comments={2: ["Blocks #50"]})
        self.assertEqual(got, [3, 2])

    def test_resumable_needs_can_resume(self):
        got, ex = picks("dev", [
            issue(1, ["status:in-dev"], assignees=["a"]),
            issue(2, ["status:in-dev", "can-resume"], assignees=["a"]),
            issue(3, ["status:in-dev", "can-resume", "needs-human"], assignees=["a"]),
        ])
        self.assertEqual(got, [2])
        self.assertEqual(ex, {1: "in-progress-without-can-resume", 3: "needs-human"})

    def test_reclaim_only_in_dev(self):
        issues = [issue(1, ["status:changes-requested"], assignees=["reviewer"]),
                  issue(2, ["status:changes-requested", "needs-human"], assignees=["reviewer"])]
        got, ex = picks("dev", issues)
        self.assertEqual((got, ex), ([1], {2: "needs-human"}))
        self.assertEqual(picks("review", issues)[0], [])

    def test_phase_status_pairs(self):
        for phase, fresh in (("spec", "status:backlog"), ("review", "status:review-ready"), ("qa", "status:qa")):
            self.assertEqual(picks(phase, [issue(7, [fresh])])[0], [7], phase)

    def test_repo_from_remote(self):
        for url in (
            "https://github.com/Jonas-Eve/pilot",
            "https://github.com/Jonas-Eve/pilot.git",
            "git@github.com:Jonas-Eve/pilot.git",
            "http://local_proxy@127.0.0.1:51234/git/Jonas-Eve/pilot",
        ):
            self.assertEqual(pool.repo_from_remote(url), "Jonas-Eve/pilot", url)
        self.assertIsNone(pool.repo_from_remote("/some/local/path"))

    def test_decode_concatenated_pages(self):
        self.assertEqual(pool.GhClient._decode('[{"a":1}]\n[{"a":2}]'), [{"a": 1}, {"a": 2}])


if __name__ == "__main__":
    unittest.main()
