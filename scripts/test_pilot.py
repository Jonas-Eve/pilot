#!/usr/bin/env python3
"""Offline tests for scripts/pilot.py. Run: python3 -m unittest scripts/test_pilot.py"""
import copy
import importlib.util
import json
import pathlib
import re
import contextlib
import io
import os
import subprocess
import tempfile
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

    def open_pulls(self):
        return [copy.deepcopy(i) for i in self.store.values()
                if i["state"] == "open" and "pull_request" in i]

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


class ProtoTests(unittest.TestCase):
    def poc(self, number, status, **kw):
        return issue(number, ["type:poc", "level:story", status], **kw)

    def test_a_prototype_is_only_for_pilot_proto_and_pilot_proto_only_takes_a_prototype(self):
        m, _ = machine([self.poc(1, "status:poc-draft", assignees=["a"]), issue(2, ["status:dev-ready"])])
        for phase in ("spec", "dev", "review", "qa"):
            self.assertEqual(m.resolve(phase, 1)["reason"], "poc", phase)
        self.assertEqual(m.resolve("proto", 2)["reason"], "not-a-poc")

    def test_resume_a_draft(self):
        m, _ = machine([self.poc(1, "status:poc-draft", assignees=["a"])])
        self.assertEqual(m.resolve("proto", 1, resume=True)["action"], "resume-orphaned")
        self.assertEqual(m.resolve("proto", 1)["action"], "ask-resume")
        got = m.claim("proto", 1, "resume-orphaned")
        self.assertEqual((got["claimed"], got["assignee"], got["status"]), (True, "bot", "status:poc-draft"))

    def test_resume_needs_a_draft(self):
        m, _ = machine([self.poc(1, "status:poc-review")])
        self.assertEqual(m.resolve("proto", 1, resume=True)["reason"], "resume-mismatch")
        self.assertEqual(m.resolve("proto", 1)["reason"], "wrong-status")

    def test_no_pool_for_prototypes(self):
        with self.assertRaises(SystemExit):
            pilot.build_parser().parse_args(["pool", "proto"])

    def test_accept_moves_a_review_to_validated_and_is_idempotent(self):
        m, gh = machine([self.poc(1, "status:poc-review")])
        got = m.proto(1, "accept")
        self.assertEqual((got["changed"], got["status"]), (True, "status:poc-validated"))
        self.assertEqual(got["event"]["action"], "accept")
        self.assertEqual(m.proto(1, "accept")["changed"], False)
        self.assertEqual(len([c for c in gh.calls if c[0] == "patch"]), 1)

    def test_accept_refuses_anything_but_a_review(self):
        for status in ("status:poc-draft", "status:poc-rejected"):
            m, gh = machine([self.poc(1, status)])
            with self.assertRaises(pilot.Refused) as caught:
                m.proto(1, "accept")
            self.assertEqual(caught.exception.payload["reason"], "not-reviewable")
            self.assertEqual(gh.calls, [])

    def test_reject_needs_a_reason_posted_first_then_closes_and_unassigns(self):
        m, gh = machine([self.poc(1, "status:poc-review", assignees=["a"]), ])
        with self.assertRaises(pilot.Refused) as caught:
            m.proto(1, "reject", "  ")
        self.assertEqual(caught.exception.payload["reason"], "reason-required")
        self.assertEqual(gh.calls, [])
        got = m.proto(1, "reject", "Too costly")
        self.assertEqual(gh.calls[0][0], "comment")
        self.assertEqual(gh.posted, [(1, "Too costly")])
        self.assertEqual((got["status"], got["state"]), ("status:poc-rejected", "closed"))
        self.assertEqual(gh.store[1]["assignees"], [])
        self.assertEqual(names(gh.store[1]), ["level:story", "status:poc-rejected", "type:poc"])

    def test_reject_works_from_every_open_state_not_from_a_rejected_one(self):
        for status in ("status:poc-draft", "status:poc-review", "status:poc-validated"):
            m, _ = machine([self.poc(1, status)])
            self.assertEqual(m.proto(1, "reject", "why")["status"], "status:poc-rejected", status)
        m, _ = machine([self.poc(1, "status:poc-rejected")])
        with self.assertRaises(pilot.Refused):
            m.proto(1, "reject", "again")

    def test_a_discovery_only_starts_from_an_accepted_prototype(self):
        m, gh = machine([self.poc(1, "status:poc-validated"), self.poc(2, "status:poc-review")])
        self.assertTrue(m.proto(1, "from-proto")["ok"])
        with self.assertRaises(pilot.Refused) as caught:
            m.proto(2, "from-proto")
        self.assertEqual(caught.exception.payload["reason"], "not-accepted")
        self.assertEqual(gh.calls, [])

    def test_not_a_prototype_closed_or_flagged_are_refused(self):
        cases = [(issue(1, ["status:poc-review"]), "not-a-poc"),
                 (self.poc(1, "status:poc-review", state="closed"), "closed"),
                 (self.poc(1, "status:poc-review") | {"labels": [{"name": n} for n in ("type:poc", "status:poc-review", "needs-human")]}, "flagged")]
        for raw, reason in cases:
            m, _ = machine([raw])
            with self.assertRaises(pilot.Refused) as caught:
                m.proto(1, "accept")
            self.assertEqual(caught.exception.payload["reason"], reason)

    def test_set_knows_the_prototype_statuses(self):
        m, gh = machine([self.poc(1, "status:poc-draft")])
        m.set(1, status="poc-review", assign="none")
        self.assertIn("status:poc-review", names(gh.store[1]))


class ProtoPackTests(unittest.TestCase):
    def pack(self, html, **kw):
        import os
        import tempfile
        m, _ = machine([issue(7, ["type:poc", "status:poc-draft"])])
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "m.html")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write(html)
            out = os.path.join(tmp, "out")
            got = m.proto_pack(7, src, out, **kw)
            docs = {}
            for path in got["files"]:
                with open(path, encoding="utf-8") as handle:
                    docs[os.path.basename(path)] = json.load(handle)
            return got, docs

    def test_a_small_mockup_is_one_part_with_its_metadata(self):
        got, docs = self.pack("<!doctype html><p>hi</p>", brief="  Test the alert  ", height=5000)
        self.assertEqual((got["parts"], got["bytes"]), (1, len("<!doctype html><p>hi</p>")))
        meta = docs["proto-7.json"]
        self.assertEqual((meta["kind"], meta["n"], meta["repo"], meta["title"], meta["parts"], meta["brief"], meta["height"]),
                         ("proto", 7, "o/r", "t7", 1, "Test the alert", 900))
        self.assertEqual(docs["protoHtml-7-0.json"], {"n": 7, "k": 0, "html": "<!doctype html><p>hi</p>"})

    def test_a_large_mockup_is_split_in_parts_that_fit_and_join_back(self):
        html = "<p>" + "é" * 150_000 + "</p>"          # 2 bytes a character: ~300 KB
        got, docs = self.pack(html)
        self.assertEqual(got["parts"], 2)
        joined = "".join(docs[f"protoHtml-7-{k}.json"]["html"] for k in range(got["parts"]))
        self.assertEqual(joined, html)
        for k in range(got["parts"]):
            self.assertLessEqual(len(docs[f"protoHtml-7-{k}.json"]["html"].encode("utf-8")), pilot.PROTO_PART_BYTES)
        self.assertEqual(docs["proto-7.json"]["parts"], 2)

    def test_an_external_resource_is_refused_but_an_xml_namespace_is_not(self):
        self.pack('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
        for bad in ('<img src="https://x.test/a.png">', '<p>https://x.test</p>', '<script src="//cdn.test/a.js"></script>',
                    '<style>@import url(a.css)</style>', '<iframe src="a"></iframe>', '<link rel="stylesheet" href="a.css">',
                    '<meta http-equiv="refresh" content="0;url=a">'):
            with self.assertRaises(pilot.Refused) as caught:
                self.pack(bad)
            self.assertEqual(caught.exception.payload["reason"], "invalid-mockup", bad)

    def test_too_big_or_empty_is_refused(self):
        for html in ("a" * (pilot.PROTO_MAX_BYTES + 1), "   "):
            with self.assertRaises(pilot.Refused) as caught:
                self.pack(html)
            self.assertTrue(caught.exception.payload["problems"])

    def test_only_a_prototype_has_a_mockup(self):
        m, _ = machine([issue(7, ["status:dev-ready"])])
        with self.assertRaises(pilot.Refused) as caught:
            m.proto_pack(7, "x", "y")
        self.assertEqual(caught.exception.payload["reason"], "not-a-poc")


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

    def test_events_carry_the_parent_and_the_pr_the_caller_just_opened(self):
        child = issue(2, ["status:dev-ready"]); child["parent_issue_url"] = "https://api.github.com/repos/o/r/issues/1"
        m, _ = machine([issue(1, ["level:epic"]), child, issue(3, ["status:in-dev"], assignees=["bot"])])
        ev = m.claim("dev", 2, "fresh")["event"]
        self.assertEqual(ev["parent"], 1)
        self.assertNotIn("pr", ev)
        ev = m.set(3, status="review-ready", assign="none", pr=44)["event"]
        self.assertEqual(ev["pr"], 44)
        self.assertNotIn("parent", ev)

    def test_event_command_reports_a_ticket_the_skill_changed_itself(self):
        story = issue(5, ["type:feature", "level:story", "status:draft"], assignees=["bot"])
        story["parent_issue_url"] = "https://api.github.com/repos/o/r/issues/4"
        m, gh = machine([story])
        got = m.events([5], "created", "discovery")
        ev = got["events"][0]
        self.assertEqual((ev["kind"], ev["n"], ev["action"], ev["phase"], ev["parent"], ev["by"]), ("ticket", 5, "created", "discovery", 4, "bot"))
        self.assertEqual(ev["labels"], ["level:story", "status:draft", "type:feature"])
        self.assertEqual(gh.calls, [])  # read-only
        with self.assertRaises(pilot.Refused) as ctx:
            m.events([5, 99], "created")
        self.assertEqual((ctx.exception.payload["reason"], ctx.exception.payload["issue"]), ("not-found", 99))

    def test_event_command_builds_one_event_per_ticket_in_one_call(self):
        m, gh = machine([issue(1, ["level:epic"]), issue(2, ["status:draft"], assignees=["bot"]), issue(3, ["status:draft"])])
        got = m.events([1, 2, 3], "approved", "discovery")
        self.assertEqual([e["n"] for e in got["events"]], [1, 2, 3])
        self.assertEqual(got["issues"], [1, 2, 3])
        self.assertTrue(all(e["action"] == "approved" and e["phase"] == "discovery" for e in got["events"]))

    def test_cli_accepts_the_new_arguments(self):
        args = pilot.build_parser().parse_args(["event", "7", "8", "--action", "approved", "--phase", "discovery"])
        self.assertEqual((args.cmd, args.issues, args.action, args.phase), ("event", [7, 8], "approved", "discovery"))
        args = pilot.build_parser().parse_args(["set", "7", "--status", "review-ready", "--unassign", "--pr", "12"])
        self.assertEqual(args.pr, 12)

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

    def test_snapshot_carries_the_assignee_and_the_open_pr_closing_a_ticket(self):
        a = issue(1, ["status:in-dev"], assignees=["alice"])
        pr = issue(9, pr=True, body="Summary\n\nCloses #1, and also fixes #2")
        older = issue(8, pr=True, body="closes #1")
        gone = issue(7, pr=True, body="Closes #3", state="closed")
        m, _ = machine([a, issue(2), issue(3), pr, older, gone])
        rows = {r["n"]: r for r in m.snapshot()["issues"]}
        self.assertEqual((rows[1].get("a"), rows[1].get("r")), ("alice", 9))
        self.assertEqual((rows[2].get("a"), rows[2].get("r")), (None, 9))
        self.assertNotIn("r", rows[3])

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
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.wiki_dir = pathlib.Path(self._tmp.name) / "wiki"
        self.wiki_dir.mkdir()

    def report(self, **attrs):
        gh = FakeGh([])
        for key, value in attrs.items():
            setattr(gh, key, value)
        return pilot.Machine(gh).doctor(str(self.wiki_dir), {"wiki": True})

    def test_an_enabled_wiki_module_needs_its_directory(self):
        got = pilot.Machine(FakeGh([])).doctor(str(self.wiki_dir / "missing"), {"wiki": True})
        self.assertFalse(got["ok"])
        self.assertEqual([c["name"] for c in got["failed"]], ["wiki"])
        self.assertIn("run /pilot-wiki", got["failed"][0]["detail"])

    def test_a_disabled_or_absent_wiki_module_is_not_checked(self):
        for modules in ({"wiki": False}, {}):
            got = pilot.Machine(FakeGh([])).doctor(str(self.wiki_dir / "missing"), modules)
            self.assertTrue(got["ok"], modules)
            self.assertNotIn("wiki", [c["name"] for c in got["checks"]])

    def test_the_modules_come_from_the_state_file_by_default(self):
        state = pathlib.Path(self._tmp.name) / "state.json"
        self.assertEqual(pilot.read_modules(str(state)), {})
        state.write_text(json.dumps({"projectName": "p", "modules": {"wiki": True}}))
        self.assertEqual(pilot.read_modules(str(state)), {"wiki": True})
        state.write_text("{not json")
        self.assertEqual(pilot.read_modules(str(state)), {})
        state.write_text(json.dumps({"projectName": "p"}))
        self.assertEqual(pilot.read_modules(str(state)), {})

    def test_set_module_changes_only_the_modules_field(self):
        state = pathlib.Path(self._tmp.name) / "state.json"
        state.write_text(json.dumps({"projectName": "p", "pilotVersion": "2.0.0"}, indent=2) + "\n")
        self.assertEqual(pilot.set_module("wiki", True, str(state)), {"ok": True, "modules": {"wiki": True}})
        self.assertEqual(json.loads(state.read_text()), {"projectName": "p", "pilotVersion": "2.0.0", "modules": {"wiki": True}})
        pilot.set_module("wiki", False, str(state))
        self.assertEqual(pilot.read_modules(str(state)), {"wiki": False})

    def modules_state(self, modules=None):
        state = pathlib.Path(self._tmp.name) / "state.json"
        state.write_text(json.dumps({"projectName": "p", "modules": modules or {}}))
        return state

    def test_a_module_needing_another_is_refused_until_it_is_on(self):
        state = self.modules_state()
        with self.assertRaises(pilot.Refused) as caught:
            pilot.set_module("design", True, str(state))
        self.assertEqual((caught.exception.payload["reason"], caught.exception.payload["missing"]), ("requires", ["dashboard"]))
        self.assertEqual(pilot.read_modules(str(state)), {})
        pilot.set_module("dashboard", True, str(state))
        self.assertEqual(pilot.set_module("design", True, str(state))["modules"], {"dashboard": True, "design": True})

    def test_with_requires_turns_the_prerequisites_on_too(self):
        state = self.modules_state()
        out = pilot.set_module("proto", True, str(state), with_requires=True)
        self.assertEqual(out["modules"], {"dashboard": True, "proto": True})

    def test_a_module_another_one_needs_cannot_be_turned_off(self):
        state = self.modules_state({"dashboard": True, "design": True})
        with self.assertRaises(pilot.Refused) as caught:
            pilot.set_module("dashboard", False, str(state))
        self.assertEqual((caught.exception.payload["reason"], caught.exception.payload["by"]), ("required-by", ["design"]))
        pilot.set_module("design", False, str(state))
        self.assertEqual(pilot.set_module("dashboard", False, str(state))["modules"], {"dashboard": False, "design": False})

    def test_the_registry_lists_every_module_with_its_state(self):
        reg = pilot.module_registry({"dashboard": True})
        self.assertEqual(sorted(reg), ["architecture", "dashboard", "design", "proto", "wiki"])
        self.assertEqual((reg["architecture"]["use"], reg["architecture"]["bootstrap"]), ("/pilot-architecture", "/pilot-architecture --bootstrap"))
        self.assertEqual((reg["dashboard"]["enabled"], reg["design"]["enabled"], reg["design"]["requires"], reg["wiki"]["bootstrap"]),
                         (True, False, ["dashboard"], "/pilot-wiki --bootstrap"))
        self.assertEqual((reg["dashboard"]["use"], reg["dashboard"]["bootstrap"]), ("/pilot-dashboard", None))
        self.assertTrue(all(set(m) == {"enabled", "requires", "skills", "use", "bootstrap"} for m in reg.values()))

    def test_every_module_requires_only_known_modules_and_names_a_pilot_skill(self):
        for name, meta in pilot.MODULES.items():
            self.assertTrue(set(meta["requires"]) <= set(pilot.MODULES), name)
            self.assertTrue(all(s.startswith("pilot-") for s in meta["skills"]), name)
            self.assertTrue(meta["use"].startswith("/pilot-"), name)
            self.assertTrue(meta.get("bootstrap", meta["use"]).startswith(meta["use"]), name)

    def test_set_module_refuses_an_unknown_module_and_a_missing_state(self):
        with self.assertRaises(pilot.Refused) as caught:
            pilot.set_module("nope", True, str(pathlib.Path(self._tmp.name) / "state.json"))
        self.assertEqual(caught.exception.payload["reason"], "unknown-module")
        with self.assertRaises(pilot.Refused) as caught:
            pilot.set_module("wiki", True, str(pathlib.Path(self._tmp.name) / "absent.json"))
        self.assertEqual(caught.exception.payload["reason"], "no-state")

    def test_the_cli_flag_skips_the_wiki_check_and_module_is_offline(self):
        self.assertTrue(pilot.build_parser().parse_args(["doctor", "--no-wiki"]).no_wiki)
        self.assertFalse(pilot.build_parser().parse_args(["doctor"]).no_wiki)
        self.assertFalse(pilot.needs_github(pilot.build_parser().parse_args(["module", "list"])))

    def test_not_authenticated(self):
        got = FakeGh([], me=None)
        got = pilot.Machine(got).doctor(str(self.wiki_dir), {})
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
        self.assertEqual(len(pilot.REQUIRED_LABELS), 32)  # pilot-process.md section 0


class LabelScriptTests(unittest.TestCase):
    def test_the_provisioning_script_and_the_doctor_agree_on_the_labels(self):
        import os
        import re
        path = os.path.join(os.path.dirname(__file__), "setup-github-labels.sh")
        with open(path, encoding="utf-8") as handle:
            in_script = set(re.findall(r'^  "([^|"]+)\|', handle.read(), re.M))
        self.assertEqual(in_script, set(pilot.REQUIRED_LABELS))

    def test_every_label_description_fits_github_limit(self):
        import os
        import re
        path = os.path.join(os.path.dirname(__file__), "setup-github-labels.sh")
        with open(path, encoding="utf-8") as handle:
            rows = re.findall(r'^  "([^|"]+)\|[0-9A-Fa-f]{6}\|(.*)"\s*$', handle.read(), re.M)
        self.assertEqual(len(rows), len(pilot.REQUIRED_LABELS))
        for name, description in rows:
            self.assertLessEqual(len(description), 100, name)  # GitHub: "description is too long (maximum is 100 characters)"


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


class WikiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "wiki"
        self.root.mkdir()
        self.entry("search/search-filter.md", "specified", [12, 15], "Filter by accessibility",
                   "The user can filter results.", body="The user can filter results.")
        self.entry("search/search-sort.md", "implemented", [3], "Sort results", "Nearest place first.",
                   stamp=("2026-01-01T00:00:00Z", "abc123"))
        self.wiki = pilot.Wiki(str(self.root))
        self.wiki.reindex()

    def raw(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def entry(self, rel, status, tickets=(), title=None, description="A rule.", body="", stamp=None, okf=None, extra=""):
        okf = okf or pilot.WIKI_OKF_STATUS.get(status, "draft")
        lines = ["---", "type: Behavior", f"title: {title or rel}", f"description: {description}", f"status: {okf}"]
        if extra:
            lines.append(extra)
        if stamp:
            lines += ["verified:", "  by: process:pilot-wiki", f"  at: {stamp[0]}"]
        lines += ["pilot:", f"  status: {status}", "  tickets: [" + ", ".join(map(str, tickets)) + "]"]
        if stamp:
            lines.append(f"  verifiedCommit: {stamp[1]}")
        self.raw(rel, "\n".join(lines) + "\n---\n" + (("\n" + body + "\n") if body else ""))

    def text(self, rel):
        return (self.root / rel).read_text()

    def codes(self, report):
        return sorted(f["code"] for f in report["findings"])

    def lint(self, *issues):
        return self.wiki.lint(FakeGh(list(issues) or [issue(12), issue(15), issue(3)]))

    # ---- the YAML subset ---------------------------------------------------------------
    def test_frontmatter_subset_parses_scalars_lists_and_one_nested_block(self):
        got = pilot.parse_frontmatter('type: Behavior\n# a comment\ntitle: "A: quoted"\ntags: [a, "b, c", 3]\nok: true\nnone:\n'
                                      'pilot:\n  status: specified\n  tickets: [12, 15]\n'.replace("\\n", "\n"))
        self.assertEqual(got, {"type": "Behavior", "title": "A: quoted", "tags": ["a", "b, c", 3], "ok": True, "none": None,
                               "pilot": {"status": "specified", "tickets": [12, 15]}})

    def test_frontmatter_outside_the_subset_is_refused_not_misread(self):
        for block in ("verified:\n  - by: x\n    at: y", "a: {b: c", "a: 1\na: 2", "a:\n  b:\n    c: 1\n  d: 2",
                      "not a mapping", "title: \"unterminated"):
            with self.assertRaises(ValueError, msg=block):
                pilot.parse_frontmatter(block)

    def test_frontmatter_accepts_flow_mappings_and_inline_comments_as_valid_okf_has_them(self):
        got = pilot.parse_frontmatter('type: Metric  # a comment\ngenerated: { by: human:me, at: 2026-06-20T14:30:00Z }\n'
                                      'title: "Quoted" # trailing\ntags: [a, b]  # more\nempty: {}\nsingle: \'it\'\'s\'\n')
        self.assertEqual(got, {"type": "Metric", "generated": {"by": "human:me", "at": "2026-06-20T14:30:00Z"},
                               "title": "Quoted", "tags": ["a", "b"], "empty": {}, "single": "it's"})

    def test_dump_and_parse_round_trip_including_awkward_strings(self):
        data = {"type": "Behavior", "title": "Colon: inside", "description": "- starts with a dash", "n": "12", "t": "true", "e": "",
                "hash": "a #b", "list": [1, "x y"], "pilot": {"status": "specified", "tickets": []}}
        self.assertEqual(pilot.parse_frontmatter(pilot.dump_frontmatter(data).rstrip("\n")), data)

    def test_split_frontmatter_keeps_what_follows_the_closing_line(self):
        self.assertEqual(pilot.split_frontmatter("---\na: 1\n---\n\nBody\n"), ("a: 1", "\nBody\n"))
        self.assertEqual(pilot.split_frontmatter("no front\n"), (None, "no front\n"))
        self.assertEqual(pilot.split_frontmatter("---\nunclosed\n"), (None, "---\nunclosed\n"))

    # ---- reading -------------------------------------------------------------------------
    def test_index_lists_entries_with_their_description_and_status(self):
        out = self.wiki.index()
        self.assertEqual([e["id"] for e in out["entries"]], ["search-filter", "search-sort"])
        first, second = out["entries"]
        self.assertEqual((first["path"], first["status"], first["tickets"], first["description"]),
                         ("search/search-filter.md", "specified", [12, 15], "The user can filter results."))
        self.assertEqual((second["verifiedAt"], second["verifiedCommit"]), ("2026-01-01T00:00:00Z", "abc123"))
        self.assertEqual(out["problems"], 0)

    def test_index_filters_by_ticket(self):
        self.assertEqual([e["id"] for e in self.wiki.index(15)["entries"]], ["search-filter"])
        self.assertEqual(self.wiki.index(99)["entries"], [])

    def test_absent_wiki_is_refused_with_the_init_hint(self):
        with self.assertRaises(pilot.Refused) as caught:
            pilot.Wiki(str(self.root / "nope")).index()
        self.assertEqual(caught.exception.payload["reason"], "wiki-absent")

    def test_index_and_log_files_are_not_concepts(self):
        self.raw("search/log.md", "# Directory Update Log\n")
        self.assertEqual([e["id"] for e in self.wiki.index()["entries"]], ["search-filter", "search-sort"])

    def test_unreadable_entries_are_reported(self):
        self.raw("bad/no-front.md", "# just prose\n")
        self.raw("bad/list-of-maps.md", "---\ntype: Behavior\nverified:\n  - by: x\n    at: y\npilot:\n  status: proposed\n---\n")
        self.raw("bad/no-type.md", "---\ntitle: T\npilot:\n  status: proposed\n  tickets: [1]\n---\n")
        self.entry("bad/derived.md", "in-dev", [1])
        self.entry("bad/tickets.md", "proposed", [], okf="draft", extra="")
        self.raw("bad/tickets.md", "---\ntype: Behavior\ndescription: d\nstatus: draft\npilot:\n  status: proposed\n  tickets: [twelve]\n---\n")
        self.entry("bad/stamp.md", "implemented", [1])
        self.raw("bad/stamp.md", self.text("bad/stamp.md").replace("pilot:", "verified:\n  by: x\n  at: 2026-01-01T00:00:00Z\npilot:"))
        self.entry("bad/mismatch.md", "implemented", [1], okf="draft")
        self.entry("bad/nodesc.md", "proposed", [1], description="")
        self.raw("bad/nodesc.md", self.text("bad/nodesc.md").replace("description: \n", ""))
        self.entry("bad/UpperCase.md", "proposed", [1])
        self.raw("bad/pilot-string.md", "---\ntype: Behavior\npilot: yes\n---\n")
        report = self.lint(*[issue(n) for n in (1, 3, 12, 15)])
        for code in ("no-frontmatter", "bad-frontmatter", "missing-type", "bad-status", "bad-tickets", "partial-stamp",
                     "status-mismatch", "missing-description", "bad-id", "bad-pilot"):
            self.assertIn(code, self.codes(report))
        self.assertIn("derived", next(f for f in report["findings"] if f["code"] == "bad-status")["message"])

    def test_valid_okf_the_script_cannot_read_is_tolerated_in_a_concept_it_does_not_manage(self):
        self.raw("search/sources.md", "---\ntype: Reference\nsources:\n  - resource: https://example.com\n    id: a\n---\n\nText.\n")
        self.wiki.reindex()
        self.assertEqual(self.lint()["findings"], [])
        self.assertEqual(self.wiki.index()["problems"], 0)
        self.assertIn("[sources](sources.md)", self.text("search/index.md"))

    def test_an_absent_okf_status_means_stable(self):
        self.entry("search/no-status.md", "implemented", [3], "No status", "d")
        self.raw("search/no-status.md", self.text("search/no-status.md").replace("status: stable\n", ""))
        self.wiki.reindex()
        self.assertEqual(self.lint()["findings"], [])
        self.entry("search/spec-no-status.md", "specified", [12], "Spec", "d")
        self.raw("search/spec-no-status.md", self.text("search/spec-no-status.md").replace("status: draft\n", ""))
        self.wiki.reindex()
        self.assertEqual([f["code"] for f in self.lint()["findings"]], ["status-mismatch"])

    def test_a_concept_pilot_does_not_manage_is_indexed_and_never_checked(self):
        self.raw("search/glossary.md", "---\ntype: Reference\ntitle: Glossary\ndescription: Words.\n---\n\nText.\n")
        self.wiki.reindex()
        self.assertEqual(self.lint()["findings"], [])
        self.assertIn("[Glossary](glossary.md) - Words.", self.text("search/index.md"))
        self.assertEqual(self.wiki.snapshot(FakeGh([issue(12), issue(15), issue(3)]))["total"], 2)
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("glossary", status="proposed")
        self.assertEqual(caught.exception.payload["reason"], "not-a-pilot-entry")

    # ---- indexes --------------------------------------------------------------------------
    def test_reindex_writes_one_index_per_folder_and_the_root_carries_the_okf_version(self):
        self.assertEqual(self.text("index.md"), '---\nokf_version: "0.2"\n---\n# Wiki\n\n* [search](search/) - 2 entries\n')
        self.assertEqual(self.text("search/index.md"),
                         "# search\n\n* [Filter by accessibility](search-filter.md) - The user can filter results.\n"
                         "* [Sort results](search-sort.md) - Nearest place first.\n")
        self.assertEqual(self.wiki.reindex(), [])

    def test_a_stale_or_missing_index_is_a_lint_finding_that_reindex_fixes(self):
        (self.root / "search/index.md").write_text("# search\n")
        (self.root / "index.md").unlink()
        report = self.lint()
        self.assertEqual(self.codes(report), ["stale-index", "stale-index"])
        self.wiki.reindex()
        self.assertEqual(self.lint()["findings"], [])

    # ---- writing --------------------------------------------------------------------------
    def test_set_rewrites_only_the_frontmatter_and_keeps_unknown_keys_and_the_body(self):
        self.entry("search/with-extra.md", "specified", [20], "Extra", "Has extras.", body="Body stays\n\nexactly.", extra="custom: keep me")
        before = self.text("search/with-extra.md")
        out = self.wiki.set("with-extra", status="implemented", add=[21], remove=[20])
        self.assertEqual((out["status"], out["tickets"]), ("implemented", [21]))
        after = self.text("search/with-extra.md")
        self.assertEqual(after.split("---\n", 2)[2], before.split("---\n", 2)[2])
        self.assertIn("custom: keep me", after)
        self.assertIn("status: stable", after)
        self.assertEqual(pilot.parse_frontmatter(pilot.split_frontmatter(after)[0])["pilot"]["tickets"], [21])

    def test_set_stamp_records_time_and_commit_and_clear_stamp_forgets_them(self):
        out = self.wiki.set("search-filter", stamp="deadbeef")
        self.assertEqual(out["verifiedCommit"], "deadbeef")
        self.assertRegex(out["verifiedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertIn("by: process:pilot-wiki", self.text("search/search-filter.md"))
        out = self.wiki.set("search-filter", status="specified", clear_stamp=True)
        self.assertEqual((out["verifiedAt"], out["verifiedCommit"]), ("", ""))
        self.assertNotIn("verified", self.text("search/search-filter.md"))
        self.assertEqual(self.wiki.index()["problems"], 0)

    def test_set_updates_title_and_description_and_the_index_follows(self):
        self.wiki.set("search-filter", title="Filter places", description="New one-liner.")
        self.assertIn("* [Filter places](search-filter.md) - New one-liner.", self.text("search/index.md"))

    def test_set_refuses_a_derived_status_an_unknown_entry_and_an_unreadable_file(self):
        for derived in ("in-dev", "verified"):
            with self.assertRaises(pilot.Refused) as caught:
                self.wiki.set("search-filter", status=derived)
            self.assertEqual(caught.exception.payload["reason"], "bad-status")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("nope", status="proposed")
        self.assertEqual(caught.exception.payload["reason"], "entry-not-found")
        self.raw("search/broken.md", "---\ntype: Behavior\nverified:\n  - by: x\n    at: y\n---\n")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("broken", status="proposed")
        self.assertEqual(caught.exception.payload["reason"], "unreadable-frontmatter")
        self.assertIn("- by: x", self.text("search/broken.md"))

    def test_add_creates_the_file_the_body_and_the_indexes(self):
        self.wiki.add("flows/booking-start.md", "Start a booking", "A booking starts from a place.", "proposed", [7], "Body text.")
        self.assertEqual(self.text("flows/booking-start.md"),
                         "---\ntype: Behavior\ntitle: Start a booking\ndescription: A booking starts from a place.\nstatus: draft\n"
                         "pilot:\n  status: proposed\n  tickets: [7]\n---\n\nBody text.\n")
        self.assertIn("[flows](flows/)", self.text("index.md"))
        self.assertIn("[Start a booking](booking-start.md)", self.text("flows/index.md"))
        self.assertEqual(self.wiki.index()["problems"], 0)
        self.assertEqual(self.lint(issue(7), issue(12), issue(15), issue(3))["findings"], [])

    def test_add_refuses_duplicates_and_bad_input(self):
        for args, reason in ((("other/search-sort.md", "T", "d", "proposed"), "duplicate-id"),
                             (("x/Bad_Id.md", "T", "d", "proposed"), "bad-path"),
                             (("x/ok-id.txt", "T", "d", "proposed"), "bad-path"),
                             (("../x/ok-id.md", "T", "d", "proposed"), "bad-path"),
                             (("x/index.md", "T", "d", "proposed"), "bad-path"),
                             (("x/ok-id.md", "T", "d", "in-dev"), "bad-status"),
                             (("x/ok-id.md", "", "d", "proposed"), "title-and-description-required"),
                             (("x/ok-id.md", "T", " ", "proposed"), "title-and-description-required")):
            with self.assertRaises(pilot.Refused) as caught:
                self.wiki.add(*args)
            self.assertEqual(caught.exception.payload["reason"], reason, args)

    def test_remove_deletes_a_proposed_entry_and_its_empty_folder(self):
        self.wiki.add("tmp/one.md", "One", "d", "proposed", [7])
        self.wiki.remove("one")
        self.assertFalse((self.root / "tmp").exists())
        self.assertNotIn("tmp", self.text("index.md"))
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.remove("search-sort")
        self.assertEqual((caught.exception.payload["reason"], caught.exception.payload["status"]), ("not-removable", "implemented"))

    # ---- derived status ---------------------------------------------------------------------
    def derived(self, entry_id, *issues):
        return self.wiki.status(FakeGh(list(issues)), [entry_id])["entries"][0]

    def test_derived_status_is_the_most_advanced_open_ticket(self):
        self.assertEqual(self.derived("search-filter", issue(12, ["status:in-dev"]), issue(15, ["status:backlog"]))["derived"], "in-dev")
        self.assertEqual(self.derived("search-filter", issue(12, ["status:in-dev"]), issue(15, ["status:review-ready"]))["derived"], "in-review")
        self.assertEqual(self.derived("search-filter", issue(12, ["status:changes-requested"]), issue(15, ["status:backlog"]))["derived"], "in-review")
        out = self.derived("search-filter", issue(12, ["status:qa"]), issue(15, ["status:in-review"]))
        self.assertEqual((out["derived"], out["display"]), ("in-qa", "specified · in-qa"))
        self.assertEqual(self.derived("search-filter", issue(12, ["status:backlog"]), issue(15, ["status:backlog"]))["derived"], "")

    def test_verified_needs_an_implemented_stamped_entry_and_a_done_feature_story(self):
        done = issue(3, ["type:feature", "level:story", "status:done"], state="closed")
        self.assertEqual(self.derived("search-sort", done)["display"], "implemented · verified")
        for labels in (["type:tech", "level:story", "status:done"], ["type:feature", "level:task", "status:done"]):
            self.assertEqual(self.derived("search-sort", issue(3, labels, state="closed"))["derived"], "")

    def test_verified_also_needs_a_lint_stamp(self):
        done = issue(12, ["type:feature", "level:story", "status:done"], state="closed")
        self.wiki.set("search-filter", status="implemented")
        self.assertEqual(self.derived("search-filter", done, issue(15, state="closed"))["derived"], "")
        self.wiki.set("search-filter", stamp="abc123")
        self.assertEqual(self.derived("search-filter", done, issue(15, state="closed"))["derived"], "verified")

    def test_derived_tickets_carry_their_level_and_a_missing_ticket_is_not_fatal(self):
        out = self.derived("search-filter", issue(12, ["level:task", "status:in-dev"]), issue(15, ["level:story", "status:split"]))
        self.assertEqual([t["level"] for t in out["tickets"]], ["task", "story"])
        self.assertEqual(self.derived("search-sort")["tickets"], [{"number": 3, "missing": True}])

    def test_show_returns_the_text_and_the_overlay(self):
        out = self.wiki.show("search-filter", FakeGh([issue(12, ["status:in-dev"]), issue(15)]))
        self.assertEqual((out["text"], out["derived"]["display"]), ("The user can filter results.", "specified · in-dev"))

    # ---- lint -------------------------------------------------------------------------------
    def test_lint_is_clean_on_a_coherent_wiki(self):
        report = self.lint(issue(12, ["status:in-dev"]), issue(15, ["status:backlog"]), issue(3, ["status:done"], state="closed"))
        self.assertEqual(report, {"ok": True, "entries": 2, "findings": []})

    def test_lint_flags_duplicates_orphaned_promises_and_reopened_work(self):
        self.entry("elsewhere/search-sort.md", "proposed", [])
        self.wiki.reindex()
        report = self.lint(issue(12, state="closed"), issue(15, state="closed"), issue(3, ["status:backlog"]))
        self.assertEqual(self.codes(report), sorted(
            ["duplicate-id", "duplicate-id", "no-ticket", "orphaned-promise", "implemented-but-reopened"]))

    def test_lint_flags_an_unknown_ticket_and_spares_an_open_pr(self):
        self.assertEqual(self.codes(self.lint(issue(3, ["status:done"], state="closed"), issue(12, ["status:backlog"]))), ["unknown-ticket"])
        self.assertEqual(self.lint(issue(12), issue(15), issue(3, ["status:in-review"]))["findings"], [])

    # ---- snapshot -----------------------------------------------------------------------------
    def test_snapshot_carries_entries_derived_status_and_text(self):
        gh = FakeGh([issue(12, ["status:in-dev"]), issue(15, ["status:backlog"]), issue(3, ["status:done"], state="closed")])
        doc = self.wiki.snapshot(gh)
        self.assertEqual((doc["kind"], doc["repo"], doc["total"], doc["truncated"]), ("wiki", "o/r", 2, False))
        first, second = doc["entries"]
        self.assertEqual((first["id"], first["path"], first["display"], first["tickets"], first["description"]),
                         ("search-filter", "search/search-filter.md", "specified · in-dev", [12, 15], "The user can filter results."))
        self.assertEqual(first["text"], "The user can filter results.")
        self.assertEqual((second["id"], second["verifiedAt"], second["text"]), ("search-sort", "2026-01-01T00:00:00Z", ""))

    def test_snapshot_shortens_then_drops_text_to_fit_a_database_document(self):
        for i in range(250):
            self.entry(f"big/e{i}.md", "implemented", [], f"E{i}", "d", body="x" * 1500)
        doc = self.wiki.snapshot(FakeGh([issue(12), issue(15), issue(3)]))
        self.assertTrue(doc["truncated"])
        self.assertLessEqual(len(json.dumps(doc, ensure_ascii=False).encode("utf-8")), pilot.WIKI_SNAPSHOT_MAX_BYTES)
        self.assertEqual(doc["total"], 252)

    # ---- migration from the earlier page format -------------------------------------------------
    OLD = ("# Search\n\nIntro prose.\n\n## Filter by accessibility {#search-filter}\n"
           "<!-- wiki: status=specified tickets=#12,#15 verifiedAt= verifiedCommit= -->\n\nThe user can filter results. More text.\n\n"
           "## A plain section\n\nNot an entry.\n\n## Sort results {#search-sort}\n"
           "<!-- wiki: status=implemented tickets=#3 verifiedAt=2026-01-01T00:00:00Z verifiedCommit=abc123 -->\n\nNearest first.\n"
           "\n## Odd {#odd}\n<!-- wiki: status=in-dev tickets=#1 verifiedAt= verifiedCommit= -->\n")

    def test_migrate_converts_old_pages_into_okf_files(self):
        legacy = pathlib.Path(self._tmp.name) / "old"
        (legacy / "search").mkdir(parents=True)
        (legacy / "search/matching.md").write_text(self.OLD)
        (legacy / "README.md").write_text("# Wiki\n\nIntro.\n")
        out = pilot.Wiki(str(legacy)).migrate()
        self.assertEqual(sorted(out["created"]), ["search/search-filter.md", "search/search-sort.md"])
        self.assertEqual(sorted(out["removed"]), ["README.md", "search/matching.md"])
        self.assertEqual(len(out["skipped"]), 1)
        self.assertIn("odd", out["skipped"][0])
        text = (legacy / "search/search-sort.md").read_text()
        fm = pilot.parse_frontmatter(pilot.split_frontmatter(text)[0])
        self.assertEqual((fm["status"], fm["pilot"], fm["verified"]["at"], fm["description"]),
                         ("stable", {"status": "implemented", "tickets": [3], "verifiedCommit": "abc123"}, "2026-01-01T00:00:00Z", "Nearest first."))
        self.assertEqual(pilot.parse_frontmatter(pilot.split_frontmatter((legacy / "search/search-filter.md").read_text())[0])["description"],
                         "The user can filter results.")
        self.assertTrue((legacy / "index.md").exists() and (legacy / "search/index.md").exists())
        self.assertFalse((legacy / "search/matching.md").exists())
        self.assertEqual(pilot.Wiki(str(legacy)).migrate()["created"], [])

    # ---- the command line ------------------------------------------------------------------------
    def test_offline_commands_need_no_repository(self):
        parser = pilot.build_parser()
        for argv, needs in ((["wiki", "index"], False), (["wiki", "reindex"], False), (["wiki", "migrate"], False),
                            (["wiki", "remove", "x"], False), (["wiki", "add", "a/b.md", "--title", "T", "--description", "d", "--status", "proposed"], False),
                            (["wiki", "set", "x", "--stamp", "c"], False), (["wiki", "lint"], True), (["wiki", "show", "x"], True),
                            (["wiki", "status"], True), (["wiki", "snapshot"], True), (["pool", "dev"], True)):
            self.assertEqual(pilot.needs_github(parser.parse_args(argv)), needs, argv)

    def test_repo_flag_is_accepted_after_a_wiki_subcommand(self):
        self.assertEqual(pilot.build_parser().parse_args(["wiki", "lint", "--repo", "o/r"]).repo, "o/r")

    def test_main_runs_index_without_a_repo_and_an_absent_wiki_exits_1(self):
        def call(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = pilot.main(list(argv))
            return code, json.loads(out.getvalue())
        code, doc = call("wiki", "--dir", str(self.root), "index")
        self.assertEqual((code, len(doc["entries"]), "repo" in doc), (0, 2, False))
        code, doc = call("wiki", "--dir", str(self.root / "missing"), "index")
        self.assertEqual((code, doc["reason"]), (1, "wiki-absent"))


class SnapshotModulesTests(unittest.TestCase):
    """The snapshot document carries the project's modules, so the dashboard's tabs can follow them."""

    def snapshot_in(self, state):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                if state is not None:
                    os.makedirs(".pilot")
                    pathlib.Path(".pilot/state.json").write_text(json.dumps(state))
                return pilot.Machine(FakeGh([issue(1, ["status:backlog"])])).snapshot()
            finally:
                os.chdir(old)

    def test_the_modules_field_is_copied_into_the_snapshot(self):
        doc = self.snapshot_in({"projectName": "p", "modules": {"wiki": True, "design": False}})
        self.assertEqual(doc["modules"], {"wiki": True, "design": False})

    def test_the_snapshot_carries_the_project_language_english_by_default(self):
        self.assertEqual(self.snapshot_in({"projectName": "p", "language": "fr"})["language"], "fr")
        self.assertEqual(self.snapshot_in({"projectName": "p"})["language"], "en")

    def test_a_state_without_the_field_or_without_a_state_adds_nothing(self):
        self.assertNotIn("modules", self.snapshot_in({"projectName": "p"}))
        self.assertNotIn("modules", self.snapshot_in(None))


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "architecture"
        self.root.mkdir()
        self.arch = pilot.Architecture(str(self.root))

    def add(self, rel, status, **kw):
        return self.arch.add(rel, kw.get("title", rel), kw.get("description", "A rule."), status, [], "")

    def text(self, rel):
        return (self.root / rel).read_text()

    def codes(self):
        return sorted(f["code"] for f in self.arch.lint()["findings"])

    def test_type_follows_the_folder_and_status_maps_to_okf(self):
        self.add("adr/0001-a.md", "accepted")
        self.add("overview.md", "accepted")
        self.add("guidelines/testing.md", "proposed")
        self.assertIn("type: ADR", self.text("adr/0001-a.md"))
        self.assertIn("status: stable", self.text("adr/0001-a.md"))
        self.assertIn("type: Architecture", self.text("overview.md"))
        self.assertIn("type: Guideline", self.text("guidelines/testing.md"))
        self.assertIn("status: draft", self.text("guidelines/testing.md"))

    def test_root_index_is_titled_and_versioned(self):
        self.add("overview.md", "accepted")
        index = self.text("index.md")
        self.assertIn('okf_version: "0.2"', index)
        self.assertIn("# Architecture", index)

    def test_supersede_links_both_ways_and_lints_clean(self):
        self.add("adr/0001-a.md", "accepted")
        self.add("adr/0002-b.md", "proposed")
        self.assertEqual(self.arch.supersede("0002-b", "0001-a")["supersedes"], "0001-a")
        old = self.text("adr/0001-a.md")
        self.assertIn("status: deprecated", old)
        self.assertIn("supersededBy: 0002-b", old)
        self.assertIn("supersedes: 0001-a", self.text("adr/0002-b.md"))
        self.assertEqual(self.arch.show("0001-a")["supersededBy"], "0002-b")
        self.assertEqual(self.codes(), [])

    def test_supersede_refuses_a_non_accepted_target_and_itself(self):
        self.add("adr/0001-a.md", "proposed")
        self.add("adr/0002-b.md", "proposed")
        with self.assertRaises(pilot.Refused) as ctx:
            self.arch.supersede("0002-b", "0001-a")
        self.assertEqual(ctx.exception.payload["reason"], "not-accepted")
        with self.assertRaises(pilot.Refused):
            self.arch.supersede("0001-a", "0001-a")

    def test_lint_flags_a_superseded_entry_without_successor(self):
        self.add("adr/0001-a.md", "superseded")
        self.assertIn("missing-supersededBy", self.codes())

    def test_remove_only_proposed(self):
        self.add("adr/0001-a.md", "accepted")
        self.add("adr/0002-b.md", "proposed")
        with self.assertRaises(pilot.Refused):
            self.arch.remove("0001-a")
        self.assertTrue(self.arch.remove("0002-b")["ok"])
        self.assertFalse((self.root / "adr/0002-b.md").exists())

    def test_add_refuses_a_path_outside_the_layout(self):
        for bad in ("notes.md", "wiki/x.md", "adr/sub/x.md"):
            with self.assertRaises(pilot.Refused) as ctx:
                self.add(bad, "accepted")
            self.assertEqual(ctx.exception.payload["reason"], "bad-path")

    def test_active_index_drops_history_and_stays_short(self):
        self.add("adr/0001-a.md", "accepted")
        self.add("adr/0002-b.md", "proposed")
        self.arch.supersede("0002-b", "0001-a")
        self.add("guidelines/layering.md", "accepted", description="Domain never imports adapters.")
        self.add("guidelines/old.md", "deprecated")
        rows = self.arch.index(active=True)["entries"]
        self.assertEqual(sorted(r["id"] for r in rows), ["0002-b", "layering"])
        self.assertTrue(all(set(r) == {"id", "path", "description", "status"} for r in rows))
        self.assertEqual(len(self.arch.index()["entries"]), 4)

    def test_active_index_grows_one_row_per_entry_without_bodies(self):
        for n in range(30):
            self.arch.add("guidelines/rule-%02d.md" % n, "T", "One rule.", "accepted", [], "B" * 2000)
        out = json.dumps(self.arch.index(active=True))
        self.assertNotIn("BBBB", out)
        self.assertLess(len(out), 30 * 200)

    def test_snapshot_carries_links_and_needs_no_github(self):
        self.add("adr/0001-a.md", "accepted")
        self.add("adr/0002-b.md", "proposed")
        self.arch.supersede("0002-b", "0001-a")
        doc = self.arch.snapshot("o/r")
        rows = {r["id"]: r for r in doc["entries"]}
        self.assertEqual((doc["kind"], doc["repo"], doc["total"]), ("architecture", "o/r", 2))
        self.assertEqual((rows["0001-a"]["status"], rows["0001-a"]["supersededBy"], rows["0002-b"]["supersedes"]),
                         ("superseded", "0002-b", "0001-a"))
        args = pilot.build_parser().parse_args(["arch", "snapshot"])
        self.assertFalse(pilot.needs_github(args))

    def test_a_monorepo_keeps_each_app_in_its_own_subfolder(self):
        self.add("overview.md", "accepted")
        self.add("guidelines/layering.md", "accepted")
        self.add("apps/web/web-overview.md", "accepted")
        self.add("apps/web/guidelines/a11y.md", "accepted")
        self.add("apps/api/guidelines/pagination.md", "accepted")
        self.add("apps/api/adr/0003-store.md", "accepted")
        self.assertIn("type: Architecture", self.text("apps/web/web-overview.md"))
        self.assertIn("type: ADR", self.text("apps/api/adr/0003-store.md"))
        self.assertIn("type: Guideline", self.text("apps/web/guidelines/a11y.md"))
        for bad in ("apps/web/overview.md", "apps/web/notes.md", "apps/Web/guidelines/x.md", "apps/web/deep/guidelines/x.md",
                    "apps/web/guidelines/sub/x.md", "apps/guidelines/x.md"):
            with self.assertRaises(pilot.Refused, msg=bad):
                self.add(bad, "accepted")

    def test_an_app_view_is_the_transversal_entries_plus_that_apps(self):
        for rel in ("overview.md", "guidelines/layering.md", "apps/web/guidelines/a11y.md", "apps/api/guidelines/pagination.md"):
            self.add(rel, "accepted")
        ids = lambda **kw: sorted(r["id"] for r in self.arch.index(active=True, **kw)["entries"])
        self.assertEqual(ids(), ["a11y", "layering", "overview", "pagination"])
        self.assertEqual(ids(app="web"), ["a11y", "layering", "overview"])
        self.assertEqual(ids(app="api"), ["layering", "overview", "pagination"])
        self.assertEqual([r["id"] for r in self.arch.search("pagination", app="web")["results"]], [])
        self.assertEqual([r["id"] for r in self.arch.search("pagination", app="api")["results"]], ["pagination"])
        outline = self.arch.outline("", app="web")
        self.assertEqual([(f["path"], f["entries"]) for f in outline["folders"]], [("apps", 1), ("guidelines", 1)])
        self.assertEqual([f["path"] for f in self.arch.outline("apps", app="web")["folders"]], ["apps/web"])

    def test_adr_numbers_run_across_the_whole_bundle(self):
        self.assertEqual(self.arch.next_number()["next"], "0001")
        self.add("adr/0001-a.md", "accepted")
        self.add("apps/api/adr/0004-b.md", "accepted")
        self.assertEqual(self.arch.next_number()["next"], "0005")

    def test_the_same_id_in_two_places_is_refused_and_found_by_lint(self):
        self.add("guidelines/testing.md", "accepted")
        with self.assertRaises(pilot.Refused) as ctx:
            self.add("apps/web/guidelines/testing.md", "accepted")
        self.assertEqual(ctx.exception.payload["reason"], "duplicate-id")
        (self.root / "apps/web/guidelines").mkdir(parents=True)
        (self.root / "apps/web/guidelines/testing.md").write_text((self.root / "guidelines/testing.md").read_text())
        self.assertIn("duplicate-id", self.codes())

    def test_cli_app_filter_and_next_number_need_no_github(self):
        parser = pilot.build_parser()
        args = parser.parse_args(["arch", "index", "--active", "--app", "web"])
        self.assertEqual((args.app, pilot.needs_github(args)), ("web", False))
        self.assertFalse(pilot.needs_github(parser.parse_args(["arch", "next-number"])))
        self.assertEqual(parser.parse_args(["arch", "search", "x", "--app", "api"]).app, "api")
        with self.assertRaises(SystemExit):
            parser.parse_args(["wiki", "index", "--app", "web"])

    def test_inventory_outlines_what_the_project_has_without_reading_it_whole(self):
        base = pathlib.Path(self._tmp.name)
        (base / "docs").mkdir()
        (base / "docs/layers.md").write_text("# Layers\n\nThe domain never imports adapters.\n" + "more\n" * 400)
        (base / "apps/web/docs").mkdir(parents=True)
        (base / "apps/web/README.md").write_text("# Web\n\nThe React front end.\n")
        (base / "apps/web/docs/state.md").write_text("# State\n\nOne store per page.\n")
        (base / "apps/api").mkdir()
        (base / ".pilot").mkdir()
        (base / ".pilot/state.json").write_text(json.dumps({"apps": [{"name": "worker", "purpose": "jobs", "stack": "node"}]}))
        (base / "CLAUDE.md").write_text("x\n<!-- PILOT:ARCHITECTURE:START -->\nThree apps.\n<!-- PILOT:ARCHITECTURE:END -->\n"
                                        "<!-- PILOT:COMMANDS:START -->\n_Not yet defined — run `/pilot-init-archi`_\n<!-- PILOT:COMMANDS:END -->\n")
        (base / "README.md").write_text("<!-- PILOT:ARCHITECTURE:START -->\nSee `architecture/` (`/pilot-architecture`).\n<!-- PILOT:ARCHITECTURE:END -->\n")
        out = self.arch.inventory(str(base))
        self.assertEqual(out["apps"], ["api", "web", "worker"])
        rows = {d["path"]: d for d in out["docs"]}
        self.assertEqual(sorted(rows), ["apps/web/README.md", "apps/web/docs/state.md", "docs/layers.md"])
        self.assertEqual((rows["docs/layers.md"]["title"], rows["docs/layers.md"]["summary"], rows["docs/layers.md"]["app"]),
                         ("Layers", "The domain never imports adapters.", ""))
        self.assertEqual(rows["apps/web/docs/state.md"]["app"], "web")
        self.assertNotIn("more", json.dumps(out))
        self.assertEqual(out["blocks"], {"CLAUDE.md:ARCHITECTURE": "filled", "CLAUDE.md:COMMANDS": "placeholder",
                                         "README.md:ARCHITECTURE": "pointer", "README.md:COMMANDS": "absent"})
        self.assertFalse(pilot.needs_github(pilot.build_parser().parse_args(["arch", "inventory"])))

    def test_reindex_creates_the_folder_a_module_needs(self):
        base = pathlib.Path(self._tmp.name)
        for cls, name in ((pilot.Wiki, "fresh-wiki"), (pilot.Architecture, "fresh-arch")):
            bundle = cls(str(base / name))
            with self.assertRaises(pilot.Refused):
                bundle.index()  # reading an absent bundle is refused
            self.assertEqual(bundle.reindex(), ["index.md"])
            self.assertIn('okf_version: "0.2"', (base / name / "index.md").read_text())
            self.assertEqual(bundle.index()["entries"], [])

    def test_cli_needs_no_github(self):
        args = pilot.build_parser().parse_args(["arch", "lint"])
        self.assertFalse(pilot.needs_github(args))


class ReadingContractTests(unittest.TestCase):
    """The port the agents and skills depend on: index, search, show, outline. Whatever sits behind it (ranking,
    caches) may change; these keys and shapes may only grow."""

    def bundles(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        wiki = pilot.Wiki(os.path.join(tmp.name, "wiki"))
        arch = pilot.Architecture(os.path.join(tmp.name, "architecture"))
        os.makedirs(wiki.root)
        os.makedirs(arch.root)
        wiki.add("search/search-by-name.md", "Search by name", "Places are found by part of their name.", "implemented", [1],
                 "A traveler types part of a place name and the matching places are listed. See [sorting](sort-results.md).")
        wiki.add("search/sort-results.md", "Sort results", "Results come nearest first.", "specified", [2], "Nearest first.")
        wiki.add("output/csv.md", "CSV export", "An option prints the result as CSV.", "proposed", [3], "One header line then one row per place.")
        arch.add("overview.md", "Overview", "The apps and how they relate.", "accepted", [], "One CLI.")
        arch.add("guidelines/layering.md", "Layering", "The domain never imports adapters.", "accepted", [], "Domain stays pure. See [ADR](../adr/0001-store.md).")
        arch.add("adr/0001-store.md", "Catalog stored", "The catalog is stored, not computed.", "accepted", [], "Stored for speed.")
        return [wiki, arch]

    def test_every_bundle_answers_the_same_contract(self):
        for b in self.bundles():
            first = b.index(active=True)["entries"][0]
            self.assertEqual(set(first), {"id", "path", "description", "status"})
            out = b.outline("")
            self.assertEqual(set(out), {"ok", "dir", "under", "description", "folders", "entries"})
            self.assertTrue(all(set(f) == {"path", "description", "entries"} for f in out["folders"]))
            hit = b.search("name places")["results"]
            if hit:
                self.assertEqual(set(hit[0]), {"id", "path", "description", "status", "score", "snippet"})
            self.assertEqual(set(b.search("anything")), {"ok", "query", "total", "results"})

    def test_outline_is_one_level_with_counts_and_descriptions(self):
        wiki = self.bundles()[0]
        wiki.describe("search", "Finding and ordering places.")
        out = wiki.outline("")
        self.assertEqual([(f["path"], f["entries"], f["description"]) for f in out["folders"]],
                         [("output", 1, ""), ("search", 2, "Finding and ordering places.")])
        self.assertEqual(out["entries"], [])
        self.assertEqual([e["id"] for e in wiki.outline("search")["entries"]], ["search-by-name", "sort-results"])
        self.assertIn("Finding and ordering places. (2 entries)", pathlib.Path(wiki.root, "index.md").read_text())
        with self.assertRaises(pilot.Refused):
            wiki.outline("nope")

    def test_describe_survives_a_reindex_and_rejects_bad_text(self):
        wiki = self.bundles()[0]
        wiki.describe("search", "Finding places.")
        wiki.describe("", "The product's behavior.")
        wiki.reindex()
        self.assertEqual(wiki.outline("")["description"], "The product's behavior.")
        self.assertEqual(wiki.outline("")["folders"][1]["description"], "Finding places.")
        self.assertIn('okf_version: "0.2"', pathlib.Path(wiki.root, "index.md").read_text())
        for bad in ("", 'a "quote"', "x" * 161):
            with self.assertRaises(pilot.Refused):
                wiki.describe("search", bad)
        with self.assertRaises(pilot.Refused):
            wiki.describe("nope", "x")

    def test_search_ranks_title_over_text_and_filters_history(self):
        wiki, arch = self.bundles()
        self.assertEqual(wiki.search("name")["results"][0]["id"], "search-by-name")
        self.assertEqual([r["id"] for r in wiki.search("nearest")["results"]], ["sort-results", "search-by-name"][:1])
        self.assertEqual([r["id"] for r in wiki.search("csv", under="search")["results"]], [])
        self.assertTrue(wiki.search("traveler")["results"][0]["snippet"].startswith("A traveler types"))
        arch.add("adr/0002-compute.md", "Catalog computed", "Compute the catalog.", "proposed", [], "Computed on demand.")
        arch.supersede("0002-compute", "0001-store")
        self.assertNotIn("0001-store", [r["id"] for r in arch.search("catalog")["results"]])
        self.assertIn("0001-store", [r["id"] for r in arch.search("catalog", include_history=True)["results"]])
        with self.assertRaises(pilot.Refused):
            wiki.search("the of")

    def test_search_folds_accents_and_plurals(self):
        wiki = self.bundles()[0]
        wiki.add("search/acces.md", "Accès de plain-pied", "Les lieux accessibles sont filtrés.", "specified", [4], "Filtre.")
        self.assertEqual(wiki.search("acces lieu")["results"][0]["id"], "acces")
        self.assertEqual(wiki.search("places")["results"][0]["id"], "search-by-name")

    def test_show_lists_what_an_entry_cites_and_what_cites_it(self):
        wiki, arch = self.bundles()
        shown = arch.show("layering")
        self.assertEqual([l["id"] for l in shown["links"]], ["0001-store"])
        self.assertEqual([l["id"] for l in arch.show("0001-store")["backlinks"]], ["layering"])
        by_name = wiki.show("search-by-name", FakeGh([issue(1)]))
        self.assertEqual([l["id"] for l in by_name["links"]], ["sort-results"])
        self.assertEqual([l["id"] for l in wiki.show("sort-results", FakeGh([issue(2)]))["backlinks"]], ["search-by-name"])
        wiki.add("x/y.md", "Y", "Cites outside.", "proposed", [9], "See [it](../elsewhere/z.md).")
        self.assertEqual(wiki.show("y", FakeGh([issue(9)]))["external"], ["../elsewhere/z.md"])

    def test_lint_warns_about_size_without_failing(self):
        wiki = self.bundles()[0]
        wiki.add("search/long.md", "Long", "d" * 170, "proposed", [5], "word " * 450)
        report = wiki.lint(FakeGh([issue(1), issue(2), issue(3), issue(5)]))
        codes = sorted(f["code"] for f in report["findings"] if f.get("level") == "warn")
        self.assertEqual(codes, ["long-description", "long-entry"])
        self.assertTrue(report["ok"])

    def test_what_a_first_look_costs_does_not_grow_with_the_bundle(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sizes = []
        for count in (30, 300):
            root = os.path.join(tmp.name, "w%d" % count)
            os.makedirs(root)
            wiki = pilot.Wiki(root)
            for n in range(count):
                wiki.add("domain-%d/entry-%03d.md" % (n % 10, n), "Entry %d" % n, "Rule number %d of the product." % n,
                         "implemented", [1], "Some prose about rule %d. " % n * 20)
            for d in range(10):
                wiki.describe("domain-%d" % d, "Area number %d." % d)
            first = len(json.dumps(wiki.outline("")))
            hits = len(json.dumps(wiki.search("rule product", limit=8)))
            sizes.append((first, hits, len(json.dumps(wiki.index(active=True)))))
        self.assertLess(abs(sizes[1][0] - sizes[0][0]), 40)  # only the counts' digits differ
        self.assertLess(sizes[1][1], 8 * 400)  # a search is bounded by its limit
        self.assertGreater(sizes[1][2], 5 * sizes[0][2] // 2)  # the flat index is what grows
        self.assertLess(sizes[1][0] * 10, sizes[1][2])  # the outline is a small fraction of it

    def test_cli_reads_without_github(self):
        for argv in (["wiki", "search", "x"], ["wiki", "index", "--depth", "1"], ["arch", "describe", "", "x"], ["wiki", "describe", "a", "b"]):
            self.assertFalse(pilot.needs_github(pilot.build_parser().parse_args(argv)))


class ContractTests(unittest.TestCase):
    """A phase knows only its own contract; the chain is their composition."""

    def test_the_contracts_compose(self):
        self.assertEqual(pilot.composition_problems(), [])

    def test_a_missing_producer_or_consumer_is_found(self):
        saved = pilot.CONTRACTS["review"]["produces"]
        try:
            pilot.CONTRACTS["review"]["produces"] = ["status:approved"]  # nobody now produces changes-requested
            codes = {(p["status"], p["code"]) for p in pilot.composition_problems()}
            self.assertIn(("status:changes-requested", "no-producer"), codes)
            pilot.CONTRACTS["review"]["produces"] = ["status:approved", "status:changes-requested", "status:nowhere"]
            self.assertIn(("status:nowhere", "unknown-status"),
                          {(p["status"], p["code"]) for p in pilot.composition_problems()})
        finally:
            pilot.CONTRACTS["review"]["produces"] = saved

    def test_a_phase_contract_is_what_the_phase_reads_claims_and_leaves(self):
        dev = pilot.phase_contract("dev")
        self.assertEqual((dev["claims"], dev["produces"]), ("status:in-dev", ["status:review-ready"]))
        self.assertEqual(dev["consumes"], ["status:changes-requested", "status:dev-ready", "status:in-dev"])
        self.assertIn("status:split", pilot.phase_contract("spec")["consumes"])
        self.assertEqual(pilot.phase_contract("discovery")["claims"], None)
        with self.assertRaises(pilot.Refused):
            pilot.phase_contract("nope")

    def test_every_transition_a_skill_makes_is_admitted(self):
        for current, new in (("status:in-spec", "status:dev-ready"), ("status:in-spec", "status:split"),
                             ("status:in-spec", "status:wont-do"), ("status:backlog", "status:wont-do"),
                             ("status:in-dev", "status:review-ready"), ("status:in-review", "status:approved"),
                             ("status:in-review", "status:changes-requested"), ("status:in-qa", "status:done"),
                             ("status:approved", "status:done"), ("status:split", "status:qa"),
                             ("status:poc-draft", "status:poc-review"), ("status:poc-review", "status:poc-validated"),
                             ("status:poc-validated", "status:poc-rejected"), ("", "status:draft")):
            self.assertTrue(pilot.transition_allowed(current, new), (current, new))
        for current, new in (("status:in-spec", "status:review-ready"), ("status:dev-ready", "status:approved"),
                             ("status:in-dev", "status:done"), ("status:done", "status:in-dev")):
            self.assertFalse(pilot.transition_allowed(current, new), (current, new))

    def test_set_warns_about_a_transition_no_contract_admits_and_still_does_it(self):
        m = pilot.Machine(FakeGh([issue(1, ["status:dev-ready"])]))
        got = m.set(1, status="approved")
        self.assertEqual(got["status"], "status:approved")
        self.assertEqual((got["warning"]["code"], got["warning"]["from"], got["warning"]["to"]),
                         ("unexpected-transition", "status:dev-ready", "status:approved"))
        m = pilot.Machine(FakeGh([issue(2, ["status:in-dev"])]))
        self.assertNotIn("warning", m.set(2, status="review-ready"))

    def test_cli_contract_needs_no_github_and_fails_only_on_a_broken_chain(self):
        self.assertFalse(pilot.needs_github(pilot.build_parser().parse_args(["contract"])))
        self.assertTrue(pilot.run_contract(pilot.build_parser().parse_args(["contract"]))["ok"])
        self.assertEqual(pilot.run_contract(pilot.build_parser().parse_args(["contract", "qa"]))["produces"], ["status:done"])


class WorkflowProfileTests(unittest.TestCase):
    """The chain a project runs depends on its workflow profile (`workflow` in .pilot/state.json); standard is today's."""

    def in_state(self, state):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "state.json"
        if state is not None:
            path.write_text(json.dumps(state))
        return str(path)

    def test_standard_is_the_whole_chain_and_the_default(self):
        self.assertEqual(pilot.DEFAULT_PROFILE, "standard")
        self.assertEqual(pilot.composition_problems("standard"), [])
        self.assertEqual(pilot.phase_contract("qa", "standard"), pilot.phase_contract("qa"))
        self.assertTrue(pilot.transition_allowed("status:split", "status:qa", "standard"))

    def test_every_profile_composes(self):
        for name in pilot.PROFILES:
            self.assertEqual(pilot.composition_problems(name), [], name)

    def test_lean_has_no_qa_phase_and_no_qa_stop(self):
        with self.assertRaises(pilot.Refused) as got:
            pilot.phase_contract("qa", "lean")
        self.assertEqual(got.exception.payload["reason"], "phase-not-in-profile")
        self.assertNotIn("status:qa", pilot.phase_contract("spec", "lean")["consumes"])
        self.assertFalse(pilot.transition_allowed("status:split", "status:qa", "lean"))
        self.assertTrue(pilot.transition_allowed("status:split", "status:done", "lean"))
        self.assertTrue(pilot.transition_allowed("status:approved", "status:done", "lean"))
        self.assertTrue(pilot.transition_allowed("status:in-review", "status:approved", "lean"))

    def test_a_contract_producing_a_status_the_profile_dropped_is_found(self):
        saved = pilot.CONTRACTS["spec"]["produces"]
        try:
            pilot.CONTRACTS["spec"]["produces"] = saved + ["status:qa"]
            self.assertIn(("status:qa", "unknown-status"),
                          {(p["status"], p["code"]) for p in pilot.composition_problems("lean")})
            self.assertEqual(pilot.composition_problems("standard"), [])
        finally:
            pilot.CONTRACTS["spec"]["produces"] = saved

    def test_an_unknown_profile_is_refused(self):
        with self.assertRaises(pilot.Refused) as got:
            pilot.composition_problems("nope")
        self.assertEqual(got.exception.payload["reason"], "unknown-profile")

    def test_the_profile_is_read_from_the_state_standard_when_absent(self):
        self.assertEqual(pilot.read_workflow(self.in_state(None)), {"profile": "standard", "source": "default"})
        self.assertEqual(pilot.read_workflow(self.in_state({"projectName": "p"}))["source"], "default")
        got = pilot.read_workflow(self.in_state({"workflow": {"profile": "lean"}}))
        self.assertEqual((got["profile"], got["source"]), ("lean", "state"))
        bad = pilot.read_workflow(self.in_state({"workflow": {"profile": "wild"}}))
        self.assertEqual((bad["profile"], bad["source"], bad["unknown"]), ("standard", "default", "wild"))

    def test_set_refuses_a_profile_that_is_not_ready_and_an_unknown_one(self):
        path = self.in_state({"projectName": "p"})
        saved = pilot.PROFILES["lean"]["ready"]
        try:
            pilot.PROFILES["lean"]["ready"] = False  # a profile the skills do not follow yet
            with self.assertRaises(pilot.Refused) as got:
                pilot.set_workflow("lean", path)
            self.assertEqual(got.exception.payload["reason"], "profile-not-ready")
        finally:
            pilot.PROFILES["lean"]["ready"] = saved
        with self.assertRaises(pilot.Refused) as got:
            pilot.set_workflow("wild", path)
        self.assertEqual(got.exception.payload["reason"], "unknown-profile")
        with self.assertRaises(pilot.Refused) as got:
            pilot.set_workflow("standard", self.in_state(None))
        self.assertEqual(got.exception.payload["reason"], "no-state")

    def test_set_writes_the_profile_and_keeps_every_other_field(self):
        path = self.in_state({"projectName": "p", "modules": {"wiki": True}, "workflow": {"note": "x"}})
        saved = pilot.PROFILES["lean"]["ready"]
        try:
            pilot.PROFILES["lean"]["ready"] = True
            self.assertEqual(pilot.set_workflow("lean", path)["profile"], "lean")
        finally:
            pilot.PROFILES["lean"]["ready"] = saved
        data = json.loads(pathlib.Path(path).read_text())
        self.assertEqual(data, {"projectName": "p", "modules": {"wiki": True}, "workflow": {"note": "x", "profile": "lean"}})

    def test_set_refuses_a_profile_whose_chain_does_not_compose(self):
        path = self.in_state({"projectName": "p"})
        saved, ready = pilot.CONTRACTS["spec"]["produces"], pilot.PROFILES["lean"]["ready"]
        try:
            pilot.PROFILES["lean"]["ready"] = True
            pilot.CONTRACTS["spec"]["produces"] = saved + ["status:qa"]
            with self.assertRaises(pilot.Refused) as got:
                pilot.set_workflow("lean", path)
            self.assertEqual(got.exception.payload["reason"], "does-not-compose")
        finally:
            pilot.CONTRACTS["spec"]["produces"], pilot.PROFILES["lean"]["ready"] = saved, ready
        self.assertNotIn("workflow", json.loads(pathlib.Path(path).read_text()))

    def test_set_warns_about_the_statuses_the_profile_drops(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "state.json"
            path.write_text(json.dumps({"projectName": "p"}))
            got = pilot.set_workflow("lean", str(path))
            self.assertEqual(got["warning"]["code"], "dropped-statuses")
            self.assertEqual(got["warning"]["statuses"], ["status:qa", "status:in-qa"])
            self.assertNotIn("warning", pilot.set_workflow("standard", str(path)))

    def test_a_machine_refuses_a_phase_its_profile_does_not_run(self):
        m = pilot.Machine(FakeGh([issue(1, ["status:qa", "type:feature", "level:story"])]), profile="lean")
        for call in (lambda: m.pool("qa", 5), lambda: m.resolve("qa", 1), lambda: m.claim("qa", 1, "fresh")):
            with self.assertRaises(pilot.Refused) as got:
                call()
            self.assertEqual((got.exception.payload["reason"], got.exception.payload["profile"]),
                             ("phase-not-in-profile", "lean"))
        self.assertEqual(pilot.Machine(FakeGh([]), profile="standard").pool("qa", 5)["pick"], None)

    def test_set_warns_by_the_machines_profile(self):
        lean = pilot.Machine(FakeGh([issue(1, ["status:split"])]), profile="lean")
        self.assertEqual(lean.set(1, status="qa")["warning"]["code"], "unexpected-transition")
        std = pilot.Machine(FakeGh([issue(2, ["status:split"])]), profile="standard")
        self.assertNotIn("warning", std.set(2, status="qa"))

    def test_the_snapshot_carries_the_profile_only_when_the_state_declares_one(self):
        def snap(state):
            with tempfile.TemporaryDirectory() as tmp:
                old = os.getcwd()
                os.chdir(tmp)
                try:
                    if state is not None:
                        os.makedirs(".pilot")
                        pathlib.Path(".pilot/state.json").write_text(json.dumps(state))
                    return pilot.Machine(FakeGh([issue(1, ["status:backlog"])])).snapshot()
                finally:
                    os.chdir(old)
        self.assertEqual(snap({"workflow": {"profile": "lean"}})["workflow"], {"profile": "lean"})
        self.assertNotIn("workflow", snap({"projectName": "p"}))
        self.assertNotIn("workflow", snap(None))

    def test_cli_workflow_needs_no_github_and_check_covers_every_profile(self):
        parse = pilot.build_parser().parse_args
        self.assertFalse(pilot.needs_github(parse(["workflow", "check"])))
        got = pilot.run_workflow(parse(["workflow", "check"]))
        self.assertTrue(got["ok"])
        self.assertEqual(sorted(got["profiles"]), sorted(pilot.PROFILES))
        self.assertNotIn("qa", got["profiles"]["lean"]["phases"])
        self.assertIn("qa", got["profiles"]["standard"]["phases"])
        shown = pilot.run_workflow(parse(["workflow", "show"]))
        self.assertEqual((shown["profile"], shown["problems"]), ("standard", []))

    def test_cli_contract_takes_a_profile(self):
        parse = pilot.build_parser().parse_args
        self.assertTrue(pilot.run_contract(parse(["contract", "--profile", "lean"]))["ok"])
        self.assertNotIn("qa", pilot.run_contract(parse(["contract", "--profile", "lean"]))["phases"])
        self.assertIn("qa", pilot.run_contract(parse(["contract"]))["phases"])


class WorkflowRulesTests(unittest.TestCase):
    """What a profile means for the skills, the task docs and the merge workflow, as data they read instead of restating."""

    def test_standard_rules_are_todays_process(self):
        rules = pilot.profile_rules("standard")
        self.assertEqual((rules["qa"], rules["e2e_task"], rules["feature_done_goes_to"]), (True, True, "status:qa"))
        self.assertEqual(rules["review"]["feature"], ["pilot-pm", "pilot-techlead"])
        self.assertEqual(rules["review"]["e2e"], ["pilot-pm", "pilot-techlead"])
        self.assertEqual(rules["review"]["tech"], ["pilot-techlead"])
        self.assertEqual(rules["review"]["bug"], ["pilot-techlead"])

    def test_lean_has_no_qa_no_e2e_task_and_the_tech_lead_alone_reviews(self):
        rules = pilot.profile_rules("lean")
        self.assertEqual((rules["qa"], rules["e2e_task"], rules["feature_done_goes_to"]), (False, False, "status:done"))
        for kind in ("feature", "e2e", "tech", "bug"):
            self.assertEqual(rules["review"][kind], ["pilot-techlead"], kind)

    def test_lean_is_ready_and_every_profile_has_no_problem(self):
        self.assertTrue(pilot.PROFILES["lean"]["ready"])
        for name in pilot.PROFILES:
            self.assertEqual(pilot.profile_problems(name), [], name)

    def test_a_profile_never_takes_the_tech_lead_out_of_a_review(self):
        saved = pilot.PROFILES["lean"]["review"]
        try:
            pilot.PROFILES["lean"]["review"] = {**saved, "feature": ["pilot-pm"]}
            self.assertIn({"code": "review-without-techlead", "type": "feature"}, pilot.profile_problems("lean"))
            pilot.PROFILES["lean"]["review"] = {**saved, "tech": []}
            self.assertIn({"code": "review-without-techlead", "type": "tech"}, pilot.profile_problems("lean"))
            pilot.PROFILES["lean"]["review"] = {**saved, "bug": ["pilot-techlead", "pilot-nobody"]}
            self.assertIn({"code": "unknown-reviewer", "type": "bug", "reviewer": "pilot-nobody"},
                          pilot.profile_problems("lean"))
        finally:
            pilot.PROFILES["lean"]["review"] = saved

    def test_the_qa_stop_and_the_qa_phase_agree(self):
        saved = pilot.PROFILES["lean"]["drop_external"]
        try:
            pilot.PROFILES["lean"]["drop_external"] = ()  # the stop is back but the phase is still dropped
            self.assertIn({"code": "qa-stop-without-qa-phase"}, pilot.profile_problems("lean"))
        finally:
            pilot.PROFILES["lean"]["drop_external"] = saved

    def test_workflow_show_and_check_carry_the_rules_and_set_accepts_lean(self):
        parse = pilot.build_parser().parse_args
        shown = pilot.run_workflow(parse(["workflow", "show"]))
        self.assertEqual(shown["rules"], pilot.profile_rules("standard"))
        checked = pilot.run_workflow(parse(["workflow", "check"]))
        self.assertEqual(checked["profiles"]["lean"]["rules"], pilot.profile_rules("lean"))
        self.assertTrue(checked["ok"])
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "state.json"
            path.write_text(json.dumps({"projectName": "p"}))
            self.assertEqual(pilot.set_workflow("lean", str(path))["profile"], "lean")
            self.assertEqual(pilot.read_workflow(str(path))["profile"], "lean")

    def test_the_merge_workflow_asks_the_engine_where_a_finished_feature_goes(self):
        text = pathlib.Path(__file__).with_name("..").joinpath("assets/github/workflows/pilot-status-on-merge.yml").resolve().read_text()
        self.assertIn("workflow show", text)
        self.assertIn("feature_done_goes_to", text)
        self.assertIn("contents: read", text)
        self.assertIn("'status:qa'", text)  # the fallback when the rules cannot be read is today's behaviour


class ProcessReferencesTests(unittest.TestCase):
    """Sections move between the generic file, the link docs and the skills; no citation may be left pointing at one that
    is gone, whether it names a section of pilot-process.md or a titled section of another doc."""

    ROOT = pathlib.Path(__file__).resolve().parent.parent

    @staticmethod
    def flat(text):
        return re.sub(r"\s+", " ", text.replace("`", ""))

    def family(self):
        files = list((self.ROOT / ".claude/skills").glob("*/SKILL.md")) + list((self.ROOT / ".claude/agents").glob("*.md"))
        files += list((self.ROOT / "assets/docs").glob("*.md")) + list((self.ROOT / "assets/templates").glob("*.tmpl"))
        files += [self.ROOT / "README.md", self.ROOT / "CLAUDE.md"]
        return files

    def headings(self, path):
        """What a citation can name: a heading, a bullet's label (`- `status:done` — ...`) or a bold lead-in."""
        text = path.read_text()
        found = [self.flat(l.lstrip("#").strip()) for l in text.split("\n") if re.match(r"^#{1,4} ", l)]
        found += [self.flat(m.group(1)) for m in re.finditer(r"(?m)^\s*- (.+?) —", text)]
        found += [self.flat(m.group(1)) for m in re.finditer(r"\*\*([^*]+?)\*\*", text, flags=re.S)]
        return found

    def test_every_cited_section_of_the_generic_file_exists(self):
        process = self.ROOT / "assets/docs/pilot-process.md"
        heads = self.headings(process)
        numbers = {m.group(1) for h in heads for m in [re.match(r"(\d+)\. ", h)] if m}
        bad = []
        for f in self.family():
            text = re.sub(r"\s+", " ", f.read_text())
            cites = [(m.group(1), m.group(2)) for m in re.finditer(r"pilot-process\.md`? ?§(\d+)(?: \"([^\"]+)\")?", text)]
            cites += [(m.group(1), m.group(2)) for m in re.finditer(r"§(\d+) \"([^\"]+)\"", text)]  # a titled citation names process.md even bare
            for num, title in cites:
                if num not in numbers:
                    bad.append((f.name, "§" + num))
                elif title and not any(self.flat(title).rstrip(".").lower() in h.lower() for h in heads):
                    bad.append((f.name, "§%s %s" % (num, title)))
        self.assertEqual(bad, [])

    def test_every_cited_title_of_another_doc_exists_there(self):
        bad = []
        for f in self.family():
            text = re.sub(r"\s+", " ", f.read_text())
            for m in re.finditer(r"`(\.pilot/pilot-[\w-]+\.md|\.claude/skills/[\w-]+/SKILL\.md)` \"([^\"]+)\"", text):
                ref, title = m.group(1), m.group(2)
                dest = self.ROOT / (ref.replace(".pilot/", "assets/docs/") if ref.startswith(".pilot/") else ref)
                if not dest.exists():
                    bad.append((f.name, ref))
                elif not any(self.flat(title).lower() in h.lower() for h in self.headings(dest)):
                    bad.append((f.name, ref, title))
        self.assertEqual(bad, [])

    def test_skill_descriptions_stay_short(self):
        """Every skill's description sits in the context of every session of a consuming project, invoked or not: the
        mechanics belong in the body, which is loaded only when the skill runs."""
        sizes = {}
        for f in (self.ROOT / ".claude/skills").glob("*/SKILL.md"):
            m = re.search(r"^description: (.*)$", f.read_text(), re.M)
            sizes[f.parent.name] = len(m.group(1).encode())
        self.assertEqual({k: v for k, v in sizes.items() if v > 1500}, {})
        self.assertLess(sum(sizes.values()), 12_000)

    def test_the_generic_file_stays_small(self):
        size = (self.ROOT / "assets/docs/pilot-process.md").stat().st_size
        self.assertLess(size, 28_000, "pilot-process.md is loaded by every phase; move what only some read into a link doc or a skill")


class LanguageTests(unittest.TestCase):
    EN = "The traveler can filter the results to the places that are step-free, and the list is sorted by distance when it is shown."
    FR = "Le voyageur peut filtrer les résultats sur les lieux de plain-pied, et la liste est triée par distance quand elle est affichée."

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def bundle(self, language):
        root = pathlib.Path(self._tmp.name) / ("wiki-" + str(language))
        bundle = pilot.Wiki(str(root), language=language)
        bundle.reindex()
        bundle.add("search/filter.md", "Filter", "One rule.", "proposed", [1], self.FR)
        bundle.add("search/sort.md", "Sort", "Another rule.", "proposed", [2], self.EN)
        return bundle

    def codes(self, bundle):
        return sorted((f["entry"], f["code"]) for f in bundle.lint(FakeGh([issue(1), issue(2)]))["findings"] if f["code"] == "other-language")

    def test_english_when_the_state_names_no_language(self):
        base = pathlib.Path(self._tmp.name)
        self.assertEqual(pilot.read_language(str(base / "absent.json")), "en")
        (base / "s.json").write_text(json.dumps({"language": " FR "}))
        self.assertEqual(pilot.read_language(str(base / "s.json")), "fr")
        (base / "e.json").write_text(json.dumps({"projectName": "x"}))
        self.assertEqual(pilot.read_language(str(base / "e.json")), "en")

    def test_detection_needs_a_clear_signal(self):
        self.assertEqual(pilot.detect_language(self.EN), "en")
        self.assertEqual(pilot.detect_language(self.FR), "fr")
        self.assertIsNone(pilot.detect_language("Search by name"))
        self.assertIsNone(pilot.detect_language("Das ist ein deutscher Satz ohne Hinweis darauf."))

    def test_lint_warns_about_the_other_language_without_failing(self):
        english = self.bundle("en")
        self.assertEqual(self.codes(english), [("filter", "other-language")])
        self.assertTrue(english.lint(FakeGh([issue(1), issue(2)]))["ok"])
        self.assertEqual(self.codes(self.bundle("fr")), [("sort", "other-language")])

    def test_another_language_is_not_judged(self):
        self.assertEqual(self.codes(self.bundle("de")), [])

    def test_module_list_says_the_language(self):
        self.assertEqual(pilot.run_module(pilot.build_parser().parse_args(["module", "list"]))["language"], pilot.read_language())


    def test_reading_doc_tells_search_terms_to_follow_the_project_language(self):
        doc = (pathlib.Path(__file__).resolve().parent.parent / "assets/docs/pilot-link-knowledge.md").read_text(encoding="utf-8")
        self.assertIn("write its terms in the project's language", doc)
        self.assertIn("fall back to `index --depth 1`", doc)


class VersionBumpTests(unittest.TestCase):
    """A change to what projects copy must raise VERSION (CLAUDE.md §4). Compares with origin/main;
    skipped where that ref or git is not available."""

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    SHIPPED = (".claude/skills/", ".claude/agents/", "assets/", "scripts/pilot.py", "scripts/setup-github-labels.sh")

    def git(self, *args):
        out = subprocess.run(["git", *args], cwd=self.ROOT, capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("git or origin/main is not available here")
        return out.stdout

    @staticmethod
    def parse(text):
        return tuple(int(part) for part in text.strip().split("."))

    def test_shipped_changes_come_with_a_higher_version(self):
        base = self.git("merge-base", "HEAD", "origin/main").strip()
        changed = set(self.git("diff", "--name-only", base).split()) | set(self.git("ls-files", "--others", "--exclude-standard").split())
        shipped = sorted(f for f in changed if f.startswith(self.SHIPPED))
        if not shipped:
            return
        before = self.parse(self.git("show", f"{base}:VERSION"))
        after = self.parse((self.ROOT / "VERSION").read_text())
        self.assertGreater(after, before, "shipped files changed (e.g. %s) but VERSION did not go up from %s: bump it (CLAUDE.md §4)"
                           % (", ".join(shipped[:3]), ".".join(map(str, before))))


class VersionTests(unittest.TestCase):
    def test_version_file_is_a_semantic_version(self):
        text = pathlib.Path(__file__).with_name("..").resolve().joinpath("VERSION").read_text()
        self.assertRegex(text, r"^\d+\.\d+\.\d+\n$")


class DemoSnapshotTests(unittest.TestCase):
    """scripts/demo_snapshot.py feeds the demo dashboard: its document must look like pilot.py's."""

    def setUp(self):
        demo_spec = importlib.util.spec_from_file_location("demo_snapshot", pathlib.Path(__file__).with_name("demo_snapshot.py"))
        self.demo = importlib.util.module_from_spec(demo_spec)
        demo_spec.loader.exec_module(self.demo)
        self.doc = self.demo.snapshot()

    def test_the_demo_snapshot_has_every_module_on(self):
        self.assertEqual(self.doc["modules"], {name: True for name in pilot.MODULES})

    def test_wiki_document_has_the_shape_of_wiki_snapshot(self):
        doc = self.demo.wiki_document()
        self.assertEqual((doc["kind"], doc["repo"], doc["total"], doc["truncated"]), ("wiki", "Jonas-Eve/pilot", len(doc["entries"]), False))
        self.assertLessEqual(len(json.dumps(doc, ensure_ascii=False).encode()), pilot.WIKI_SNAPSHOT_MAX_BYTES)
        keys = {"id", "title", "description", "path", "status", "derived", "display", "tickets", "verifiedAt", "text"}
        for row in doc["entries"]:
            self.assertEqual(set(row), keys)
            self.assertIn(row["status"], pilot.WIKI_STATUSES)
            self.assertIn(row["derived"], ("", "in-dev", "in-review", "in-qa", "verified"))

    def test_document_has_the_snapshot_shape_and_fits_a_database_document(self):
        self.assertEqual((self.doc["repo"], self.doc["truncated"], self.doc["total"]), ("Jonas-Eve/pilot", False, len(self.doc["issues"])))
        self.assertLessEqual(len(json.dumps(self.doc, ensure_ascii=False).encode()), pilot.SNAPSHOT_MAX_BYTES)
        numbers = [r["n"] for r in self.doc["issues"]]
        self.assertEqual(len(numbers), len(set(numbers)))
        for row in self.doc["issues"]:
            self.assertTrue({"n", "t", "l", "u"} <= set(row))

    def test_parents_progress_and_every_phase_are_covered(self):
        rows = {r["n"]: r for r in self.doc["issues"]}
        for row in rows.values():
            if "p" in row:
                self.assertIn(row["p"], rows)
            if "k" in row:
                self.assertLessEqual(row["k"][0], row["k"][1])
        statuses = {l for r in rows.values() for l in r["l"] if l.startswith("status:")}
        self.assertTrue({f"status:{s}" for s in ("draft", "backlog", "in-spec", "dev-ready", "in-dev", "changes-requested",
                                                 "review-ready", "in-review", "approved", "qa", "in-qa", "split")} <= statuses)
        self.assertTrue(any("level:epic" in r["l"] and "k" in r for r in rows.values()))
        self.assertTrue(any("r" in r for r in rows.values()) and any("a" in r for r in rows.values()))
        self.assertTrue(any("needs-human" in r["l"] for r in rows.values()) and any("on-hold" in r["l"] for r in rows.values()))

    def test_a_changes_requested_ticket_is_unassigned_like_the_review_leaves_it(self):
        for row in self.doc["issues"]:
            if "status:changes-requested" in row["l"] or "status:approved" in row["l"]:
                self.assertNotIn("a", row)

    def test_live_documents(self):
        docs = self.demo.live_documents()
        self.assertEqual({d["kind"] for d in docs.values()}, {"activity", "ticket"})


if __name__ == "__main__":
    unittest.main()
