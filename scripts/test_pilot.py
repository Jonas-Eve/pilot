#!/usr/bin/env python3
"""Offline tests for scripts/pilot.py. Run: python3 -m unittest scripts/test_pilot.py"""
import copy
import importlib.util
import json
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("pilot", pathlib.Path(__file__).with_name("pilot.py"))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def issue(number, labels=(), body="", assignees=(), created="2026-01-01T00:00:00Z",
          state="open", pr=False):
    raw = {
        "number": number, "title": f"t{number}", "state": state, "body": body,
        "labels": [{"name": l} for l in labels],
        "assignees": [{"login": a} for a in assignees], "created_at": created,
    }
    if pr:
        raw["pull_request"] = {}
    return raw


class FakeGh:
    """In-memory GitHub: applies PATCHes, records writes in order."""

    def __init__(self, issues, comments=None, subs=None, me="bot"):
        self.repo = "o/r"
        self.store = {i["number"]: copy.deepcopy(i) for i in issues}
        self.comment_map, self.subs, self._me = comments or {}, subs or {}, me
        self.calls, self.posted, self.after_patch = [], [], None

    def issues_with_label(self, label):
        return [copy.deepcopy(i) for i in self.store.values()
                if i["state"] == "open" and "pull_request" not in i
                and label in [l["name"] for l in i["labels"]]]

    def get_issue(self, number):
        return copy.deepcopy(self.store.get(number))

    def is_open(self, number):
        found = self.store.get(number)
        return None if found is None else found["state"] == "open"

    def comments(self, number):
        return self.comment_map.get(number, [])

    def sub_issues(self, number):
        return [copy.deepcopy(self.store[n]) for n in self.subs.get(number, [])]

    def me(self):
        if self._me is None:
            raise pilot.GhError("gh: not authenticated")
        return self._me

    def open_issues(self):
        return [copy.deepcopy(i) for i in self.store.values()
                if i["state"] == "open" and "pull_request" not in i]

    def repo_info(self):
        return {"full_name": "o/r", "permissions": getattr(self, "perms", {"push": True})}

    def label_names(self):
        return set(getattr(self, "labels", pilot.REQUIRED_LABELS))

    def patch_issue(self, number, body):
        target = self.store[number]
        if "labels" in body:
            target["labels"] = [{"name": l} for l in body["labels"]]
        if "assignees" in body:
            target["assignees"] = [{"login": a} for a in body["assignees"]]
        if "state" in body:
            target["state"] = body["state"]
        self.calls.append(("patch", number, body))
        if self.after_patch:
            self.after_patch(self)
        return copy.deepcopy(target)

    def post_comment(self, number, text):
        self.posted.append((number, text))
        self.calls.append(("comment", number))


def machine(issues, **kw):
    gh = FakeGh(issues, **kw)
    return pilot.Machine(gh), gh


def names(raw):
    return sorted(l["name"] for l in raw["labels"])


class PoolTests(unittest.TestCase):
    def pick(self, phase, issues, **kw):
        m, _ = machine(issues, **kw)
        result = m.pool(phase, 10)
        return [c["number"] for c in result["candidates"]], {e["number"]: e["reason"] for e in result["excluded"]}

    def test_fresh_pool_skips_assigned_and_flagged(self):
        got, ex = self.pick("dev", [
            issue(1, ["status:dev-ready"]),
            issue(2, ["status:dev-ready"], assignees=["a"]),
            issue(3, ["status:dev-ready", "needs-human"]),
            issue(4, ["status:dev-ready", "on-hold"]),
        ])
        self.assertEqual(got, [1])
        self.assertEqual(ex, {2: "assigned", 3: "needs-human", 4: "on-hold"})

    def test_dependency_gate_open_closed_unknown(self):
        got, ex = self.pick("dev", [
            issue(1, ["status:dev-ready"], body="Depends on #10"),
            issue(2, ["status:dev-ready"], body="Depends on #11"),
            issue(3, ["status:dev-ready"], body="Depends on #12"),
            issue(10), issue(11, state="closed"),
        ])
        self.assertEqual(got, [2])
        self.assertEqual(ex, {1: "depends-on-open", 3: "depends-on-open"})

    def test_priority_then_blocks_then_oldest(self):
        got, _ = self.pick("dev", [
            issue(1, ["status:dev-ready", "priority:P1"], created="2026-01-01T00:00:00Z"),
            issue(2, ["status:dev-ready", "priority:P0"], created="2026-03-01T00:00:00Z"),
            issue(3, ["status:dev-ready", "priority:P0"], created="2026-02-01T00:00:00Z"),
            issue(4, ["status:dev-ready"], created="2025-01-01T00:00:00Z"),
        ])
        self.assertEqual(got, [3, 2, 1, 4])
        got, _ = self.pick("dev", [
            issue(2, ["status:dev-ready", "priority:P0"], created="2026-03-01T00:00:00Z"),
            issue(3, ["status:dev-ready", "priority:P0"], created="2026-02-01T00:00:00Z"),
            issue(50),
        ], comments={2: ["Blocks #50"]})
        self.assertEqual(got, [2, 3])

    def test_blocks_ignored_when_blocked_ticket_is_closed(self):
        got, _ = self.pick("dev", [
            issue(2, ["status:dev-ready", "priority:P0"], created="2026-03-01T00:00:00Z"),
            issue(3, ["status:dev-ready", "priority:P0"], created="2026-02-01T00:00:00Z"),
            issue(50, state="closed"),
        ], comments={2: ["Blocks #50"]})
        self.assertEqual(got, [3, 2])

    def test_resumable_needs_can_resume(self):
        got, ex = self.pick("dev", [
            issue(1, ["status:in-dev"], assignees=["a"]),
            issue(2, ["status:in-dev", "can-resume"], assignees=["a"]),
            issue(3, ["status:in-dev", "can-resume", "needs-human"], assignees=["a"]),
        ])
        self.assertEqual(got, [2])
        self.assertEqual(ex, {1: "in-progress-without-can-resume", 3: "needs-human"})

    def test_reclaim_only_in_dev(self):
        issues = [issue(1, ["status:changes-requested"], assignees=["reviewer"]),
                  issue(2, ["status:changes-requested", "needs-human"], assignees=["reviewer"])]
        self.assertEqual(self.pick("dev", issues), ([1], {2: "needs-human"}))
        self.assertEqual(self.pick("review", issues)[0], [])

    def test_phase_status_pairs(self):
        for phase, fresh in (("spec", "status:backlog"), ("review", "status:review-ready"),
                             ("qa", "status:qa")):
            self.assertEqual(self.pick(phase, [issue(7, [fresh])])[0], [7], phase)

    def test_only_restricts_the_pool(self):
        m, _ = machine([issue(1, ["status:dev-ready"]), issue(2, ["status:dev-ready"])])
        self.assertEqual([c["number"] for c in m.pool("dev", 5, only={2})["candidates"]], [2])


class ResolveTests(unittest.TestCase):
    def act(self, phase, issues, number, resume=False, **kw):
        m, _ = machine(issues, **kw)
        return m.resolve(phase, number, resume)

    def test_fresh_unassigned_is_claimable(self):
        self.assertEqual(self.act("dev", [issue(1, ["status:dev-ready"])], 1)["action"], "claim-fresh")

    def test_stop_reasons(self):
        cases = [
            (issue(1, ["status:dev-ready"], assignees=["a"]), "assigned"),
            (issue(1, ["status:dev-ready", "needs-human"]), "flagged"),
            (issue(1, ["status:in-dev", "on-hold"], assignees=["a"]), "flagged"),
            (issue(1, ["status:backlog"]), "wrong-status"),
            (issue(1, ["status:dev-ready"], state="closed"), "closed"),
            (issue(1, ["status:in-dev"]), "in-progress-unassigned"),
        ]
        for raw, reason in cases:
            got = self.act("dev", [raw], 1)
            self.assertEqual((got["action"], got["reason"]), ("stop", reason), reason)
        self.assertEqual(self.act("dev", [], 1)["reason"], "not-found")

    def test_dependency_gate_applies_to_dev_and_qa_not_spec_or_review(self):
        dep = [issue(10)]
        for phase, fresh, expect in (("dev", "status:dev-ready", "stop"), ("qa", "status:qa", "stop"),
                                     ("spec", "status:backlog", "claim-fresh"),
                                     ("review", "status:review-ready", "claim-fresh")):
            got = self.act(phase, [issue(1, [fresh], body="Depends on #10")] + dep, 1)
            self.assertEqual(got["action"], expect, phase)

    def test_in_progress_variants(self):
        base = ["status:in-dev"]
        self.assertEqual(self.act("dev", [issue(1, base + ["can-resume"], assignees=["a"])], 1)["action"],
                         "resume-cleared")
        self.assertEqual(self.act("dev", [issue(1, base, assignees=["a"])], 1)["action"], "ask-resume")
        self.assertEqual(self.act("dev", [issue(1, base, assignees=["a"])], 1, resume=True)["action"],
                         "resume-orphaned")
        self.assertEqual(self.act("dev", [issue(1, base)], 1, resume=True)["reason"], "resume-mismatch")
        self.assertEqual(self.act("dev", [issue(1, ["status:dev-ready"])], 1, resume=True)["reason"],
                         "resume-mismatch")

    def test_spec_resume_also_recovers_a_draft(self):
        raw = issue(1, ["status:draft"], assignees=["a"])
        self.assertEqual(self.act("spec", [raw], 1, resume=True)["action"], "resume-orphaned")
        self.assertEqual(self.act("dev", [raw], 1, resume=True)["reason"], "resume-mismatch")
        m, gh = machine([raw])
        m.claim("spec", 1, "resume-orphaned")
        self.assertEqual(names(gh.store[1]), ["status:draft"])  # status stays where it was

    def test_reclaim_is_dev_only(self):
        raw = issue(1, ["status:changes-requested"], assignees=["rev"])
        self.assertEqual(self.act("dev", [raw], 1)["action"], "reclaim")
        self.assertEqual(self.act("review", [raw], 1)["action"], "stop")

    def test_pr_number_is_left_to_the_skill(self):
        self.assertEqual(self.act("review", [issue(1, pr=True)], 1)["action"], "manual")

    def test_epic_and_split_descend(self):
        issues = [issue(1, ["level:epic"]), issue(2, ["level:story", "status:split"]),
                  issue(3, ["status:dev-ready", "priority:P1"]),
                  issue(4, ["status:dev-ready", "priority:P0"]),
                  issue(5, ["status:dev-ready"], state="closed")]
        subs = {1: [2], 2: [3, 4, 5]}
        got = self.act("dev", issues, 1, subs=subs)
        self.assertEqual((got["action"], got["pick"]["number"]), ("descend", 4))
        got = self.act("dev", issues, 2, subs=subs)
        self.assertEqual((got["action"], got["pick"]["number"]), ("descend", 4))
        self.assertEqual(self.act("qa", issues, 1, subs=subs)["action"], "stop")  # qa: no containers

    def test_descend_with_nothing_found(self):
        got = self.act("dev", [issue(1, ["level:epic"]), issue(2, ["status:backlog"])], 1, subs={1: [2]})
        self.assertEqual((got["action"], got["pick"]), ("descend", None))

    def test_spec_specials(self):
        epic = issue(1, ["level:epic"])
        self.assertEqual(self.act("spec", [epic], 1)["reason"], "epic-without-open-subissues")
        self.assertEqual(self.act("spec", [issue(1, ["status:qa"])], 1)["action"], "rescope")
        self.assertEqual(self.act("spec", [issue(1, ["status:in-qa"], assignees=["a"])], 1)["action"], "rescope")
        # a still-open status:split story is spec's own territory, never descended into
        self.assertEqual(self.act("spec", [issue(1, ["level:story", "status:split"]), issue(2)], 1,
                                  subs={1: [2]})["action"], "rescope")
        self.assertEqual(self.act("spec", [issue(1, ["status:dev-ready"])], 1)["reason"], "wrong-status")


class ClaimTests(unittest.TestCase):
    def test_fresh_claim_swaps_status_and_assigns(self):
        m, gh = machine([issue(1, ["status:dev-ready", "type:tech"])])
        got = m.claim("dev", 1, "fresh")
        self.assertTrue(got["claimed"])
        self.assertEqual(names(gh.store[1]), ["status:in-dev", "type:tech"])
        self.assertEqual([a["login"] for a in gh.store[1]["assignees"]], ["bot"])
        self.assertEqual(len(gh.calls), 1)  # one atomic PATCH

    def test_fresh_claim_refusals(self):
        for raw, reason in ((issue(1, ["status:dev-ready"], assignees=["a"]), "not-claimable"),
                            (issue(1, ["status:backlog"]), "not-claimable"),
                            (issue(1, ["status:dev-ready"], state="closed"), "closed")):
            m, gh = machine([raw])
            with self.assertRaises(pilot.Refused) as ctx:
                m.claim("dev", 1, "fresh")
            self.assertEqual(ctx.exception.payload["reason"], reason)
            self.assertEqual(gh.calls, [])

    def test_lost_race_is_reported(self):
        m, gh = machine([issue(1, ["status:dev-ready"])])
        gh.after_patch = lambda g: g.store[1].update(assignees=[{"login": "someone-else"}])
        with self.assertRaises(pilot.Refused) as ctx:
            m.claim("dev", 1, "fresh")
        self.assertEqual(ctx.exception.payload["reason"], "lost-race")

    def test_reclaim_overwrites_assignee(self):
        m, gh = machine([issue(1, ["status:changes-requested"], assignees=["reviewer"])])
        m.claim("dev", 1, "reclaim")
        self.assertEqual(names(gh.store[1]), ["status:in-dev"])
        self.assertEqual([a["login"] for a in gh.store[1]["assignees"]], ["bot"])

    def test_reclaim_refused_outside_dev(self):
        m, _ = machine([issue(1, ["status:changes-requested"])])
        with self.assertRaises(pilot.Refused):
            m.claim("review", 1, "reclaim")

    def test_resume_orphaned_keeps_status_and_consumes_can_resume(self):
        m, gh = machine([issue(1, ["status:in-dev", "can-resume"], assignees=["old"])])
        m.claim("dev", 1, "resume-orphaned")
        self.assertEqual(names(gh.store[1]), ["status:in-dev"])
        self.assertEqual([a["login"] for a in gh.store[1]["assignees"]], ["bot"])

    def test_resume_cleared_only_drops_the_signal(self):
        m, gh = machine([issue(1, ["status:in-dev", "can-resume"], assignees=["old"])])
        m.claim("dev", 1, "resume-cleared")
        self.assertEqual(names(gh.store[1]), ["status:in-dev"])
        self.assertEqual([a["login"] for a in gh.store[1]["assignees"]], ["old"])
        self.assertNotIn("assignees", gh.calls[0][2])

    def test_rescope_is_spec_only(self):
        m, gh = machine([issue(1, ["status:qa", "type:feature"])])
        m.claim("spec", 1, "rescope")
        self.assertEqual(names(gh.store[1]), ["status:in-spec", "type:feature"])
        m, gh = machine([issue(1, ["status:split", "level:story"], assignees=["x"])])
        m.claim("spec", 1, "rescope")
        self.assertEqual(names(gh.store[1]), ["level:story", "status:in-spec"])
        m, _ = machine([issue(1, ["status:qa"])])
        with self.assertRaises(pilot.Refused):
            m.claim("dev", 1, "rescope")

    def test_flagged_ticket_is_never_claimed(self):
        m, gh = machine([issue(1, ["status:in-dev", "can-resume", "needs-human"], assignees=["a"])])
        with self.assertRaises(pilot.Refused) as ctx:
            m.claim("dev", 1, "resume-cleared")
        self.assertEqual(ctx.exception.payload["reason"], "flagged")
        self.assertEqual(gh.calls, [])


class SetTests(unittest.TestCase):
    def test_status_swap_unassign_and_labels(self):
        m, gh = machine([issue(1, ["status:in-dev", "type:tech", "priority:P1"], assignees=["bot"])])
        got = m.set(1, status="review-ready", assign="none", remove=["priority:P1"], add=["x"])
        self.assertEqual(names(gh.store[1]), ["status:review-ready", "type:tech", "x"])
        self.assertEqual(gh.store[1]["assignees"], [])
        self.assertEqual(got["status"], "status:review-ready")

    def test_status_none_and_prefixed_name(self):
        m, gh = machine([issue(1, ["status:split", "priority:P1"])])
        m.set(1, status="none")
        self.assertEqual(names(gh.store[1]), ["priority:P1"])
        m.set(1, status="status:done")
        self.assertIn("status:done", names(gh.store[1]))

    def test_unknown_status_refused_without_writing(self):
        m, gh = machine([issue(1, ["status:in-dev"])])
        with self.assertRaises(pilot.Refused):
            m.set(1, status="scoping")
        self.assertEqual(gh.calls, [])

    def test_assign_me_and_close(self):
        m, gh = machine([issue(1, ["status:qa"])])
        got = m.set(1, status="done", assign="me", close=True)
        self.assertEqual((got["state"], got["assignees"]), ("closed", ["bot"]))

    def test_untouched_assignees_when_not_asked(self):
        m, gh = machine([issue(1, ["status:in-dev"], assignees=["x"])])
        m.set(1, status="review-ready")
        self.assertNotIn("assignees", gh.calls[0][2])


class FlagTests(unittest.TestCase):
    def test_flag_requires_a_comment_and_posts_it_first(self):
        m, gh = machine([issue(1, ["status:in-dev"])])
        with self.assertRaises(pilot.Refused):
            m.flag(1, "   ")
        m.flag(1, "Why: ... Needed: ...")
        self.assertEqual([c[0] for c in gh.calls], ["comment", "patch"])
        self.assertIn("needs-human", names(gh.store[1]))
        self.assertIn("status:in-dev", names(gh.store[1]))

    def test_unflag_posts_resolution_then_removes_flag(self):
        m, gh = machine([issue(1, ["status:in-dev", "needs-human"])])
        with self.assertRaises(pilot.Refused):
            m.unflag(1, "")
        m.unflag(1, "Decided: A")
        self.assertEqual([c[0] for c in gh.calls], ["comment", "patch"])
        self.assertNotIn("needs-human", names(gh.store[1]))


class DashboardPayloadTests(unittest.TestCase):
    def test_claim_returns_event_and_activity(self):
        m, gh = machine([issue(7, ["status:dev-ready", "type:tech"])])
        got = m.claim("dev", 7, "fresh")
        ev, act = got["event"], got["activity"]
        self.assertEqual((ev["kind"], ev["n"], ev["action"], ev["phase"], ev["by"], ev["state"]),
                         ("ticket", 7, "claim:fresh", "dev", "bot", "open"))
        self.assertEqual(ev["labels"], ["status:in-dev", "type:tech"])
        self.assertEqual(ev["assignees"], ["bot"])
        self.assertRegex(ev["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual((act["kind"], act["phase"], act["n"], act["mode"], act["by"]), ("activity", "dev", 7, "fresh", "bot"))
        self.assertTrue(act["id"].startswith("dev-7-"))

    def test_set_flag_unflag_return_the_resulting_state(self):
        m, gh = machine([issue(1, ["status:in-dev"], assignees=["bot"])])
        ev = m.set(1, status="review-ready", assign="none")["event"]
        self.assertEqual((ev["action"], ev["assignees"], ev["labels"]), ("set", [], ["status:review-ready"]))
        ev = m.flag(1, "Why: x. Needed: y.")["event"]
        self.assertEqual((ev["action"], "needs-human" in ev["labels"]), ("flag", True))
        ev = m.unflag(1, "Resolved")["event"]
        self.assertEqual((ev["action"], "needs-human" in ev["labels"]), ("unflag", False))
        ev = m.set(1, status="done", close=True)["event"]
        self.assertEqual(ev["state"], "closed")

    def test_snapshot_lists_open_tickets_newest_first_without_prs(self):
        a = issue(1, ["status:qa"]); a["updated_at"] = "2026-01-01T00:00:00Z"
        b = issue(2, ["type:tech", "status:dev-ready"]); b["updated_at"] = "2026-02-01T00:00:00Z"
        m, _ = machine([a, b, issue(3, pr=True), issue(4, state="closed")])
        doc = m.snapshot()
        self.assertEqual([r["n"] for r in doc["issues"]], [2, 1])
        self.assertEqual(doc["issues"][0], {"n": 2, "t": "t2", "l": ["status:dev-ready", "type:tech"], "u": "2026-02-01T00:00:00Z"})
        self.assertEqual((doc["total"], doc["truncated"], doc["source"]), (2, False, "pilot.py"))

    def test_snapshot_carries_the_parent_and_the_sub_issue_progress(self):
        epic = issue(1, ["level:epic"]); epic["sub_issues_summary"] = {"total": 10, "completed": 4}
        child = issue(2, ["level:story"]); child["parent_issue_url"] = "https://api.github.com/repos/o/r/issues/1"
        m, _ = machine([epic, child, issue(3)])
        rows = {r["n"]: r for r in m.snapshot()["issues"]}
        self.assertEqual((rows[1].get("k"), rows[1].get("p")), ([4, 10], None))
        self.assertEqual((rows[2].get("p"), rows[2].get("k")), (1, None))
        self.assertNotIn("p", rows[3]); self.assertNotIn("k", rows[3])

    def test_snapshot_is_truncated_to_fit_a_database_document(self):
        issues = [issue(n, ["status:backlog"]) for n in range(1, 2600)]
        for i in issues:
            i["title"] = "x" * 120
            i["updated_at"] = f"2026-01-01T00:{i['number'] % 60:02d}:00Z"
        m, _ = machine(issues)
        doc = m.snapshot()
        self.assertTrue(doc["truncated"])
        self.assertLessEqual(len(pilot.json.dumps(doc, ensure_ascii=False).encode()), pilot.SNAPSHOT_MAX_BYTES)


class DoctorTests(unittest.TestCase):
    def report(self, **attrs):
        gh = FakeGh([])
        for key, value in attrs.items():
            setattr(gh, key, value)
        return pilot.Machine(gh).doctor()

    def test_everything_fine(self):
        got = self.report()
        self.assertTrue(got["ok"])
        self.assertEqual(got["failed"], [])

    def test_not_authenticated(self):
        got = FakeGh([], me=None)
        got = pilot.Machine(got).doctor()
        self.assertFalse(got["ok"])
        self.assertEqual([c["name"] for c in got["failed"]], ["github-api"])

    def test_read_only_account(self):
        got = self.report(perms={"push": False, "pull": True})
        self.assertEqual([c["name"] for c in got["failed"]], ["repo-write-permission"])

    def test_missing_labels_are_listed(self):
        got = self.report(labels=pilot.REQUIRED_LABELS - {"status:dev-ready", "needs-human"})
        failed = got["failed"][0]
        self.assertEqual(failed["name"], "pilot-labels")
        self.assertIn("needs-human", failed["detail"])
        self.assertIn("2 missing", failed["detail"])

    def test_required_labels_cover_every_status_and_flag(self):
        for status in pilot.STATUSES:
            self.assertIn(f"status:{status}", pilot.REQUIRED_LABELS)
        self.assertTrue({"needs-human", "on-hold", "can-resume", "type:e2e"} <= pilot.REQUIRED_LABELS)
        self.assertEqual(len(pilot.REQUIRED_LABELS), 27)  # pilot-process.md section 0


class MiscTests(unittest.TestCase):
    def test_repo_from_remote(self):
        for url in ("https://github.com/Jonas-Eve/pilot", "https://github.com/Jonas-Eve/pilot.git",
                    "git@github.com:Jonas-Eve/pilot.git",
                    "http://local_proxy@127.0.0.1:51234/git/Jonas-Eve/pilot"):
            self.assertEqual(pilot.repo_from_remote(url), "Jonas-Eve/pilot", url)
        self.assertIsNone(pilot.repo_from_remote("/some/local/path"))

    def test_pages_are_requested_by_number_until_a_short_page(self):
        requested = []

        class Client(pilot.GhClient):
            def _run(self, path, params=None, method="GET", body=None):
                requested.append((path, params["page"]))
                size = {1: 100, 2: 100, 3: 37}[params["page"]]
                return json.dumps([{"number": params["page"] * 1000 + k} for k in range(size)])

        got = Client("o/r")._pages("repos/o/r/issues", {"state": "open"})
        self.assertEqual(len(got), 237)
        self.assertEqual([p for _, p in requested], [1, 2, 3])
        self.assertTrue(all(path.startswith("repos/o/r/") for path, _ in requested))  # never repositories/{id}

    def test_repo_flag_accepted_before_and_after_the_subcommand(self):
        parser = pilot.build_parser()
        self.assertEqual(parser.parse_args(["--repo", "o/r", "pool", "dev"]).repo, "o/r")
        self.assertEqual(parser.parse_args(["pool", "dev", "--repo", "o/r"]).repo, "o/r")
        self.assertIsNone(parser.parse_args(["pool", "dev"]).repo)

    def test_run_dispatch(self):
        gh = FakeGh([issue(1, ["status:dev-ready"])])
        args = pilot.build_parser().parse_args(["claim", "dev", "1", "--mode", "fresh"])
        self.assertTrue(pilot.run(args, gh)["claimed"])


if __name__ == "__main__":
    unittest.main()
