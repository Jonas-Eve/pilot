#!/usr/bin/env python3
"""Offline tests for scripts/pilot.py. Run: python3 -m unittest scripts/test_pilot.py"""
import copy
import importlib.util
import json
import pathlib
import contextlib
import io
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
    SEARCH = (
        "# Search\n\nIntro prose.\n\n"
        "## Filter by accessibility {#search-filter}\n"
        "<!-- wiki: status=specified tickets=#12,#15 verifiedAt= verifiedCommit= -->\n\n"
        "The user can filter results.\n\n"
        "## A plain section\n\nNot an entry.\n\n"
        "## Sort results {#search-sort}\n"
        "<!-- wiki: status=implemented tickets=#3 verifiedAt=2026-01-01T00:00:00Z verifiedCommit=abc123 -->\n"
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "wiki"
        self.root.mkdir()
        (self.root / "features").mkdir()
        self.page("features/search.md", self.SEARCH)
        self.wiki = pilot.Wiki(str(self.root))

    def page(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def codes(self, report):
        return sorted(f["code"] for f in report["findings"])

    def test_index_lists_entries_and_ignores_plain_sections(self):
        out = self.wiki.index()
        self.assertEqual([e["id"] for e in out["entries"]], ["search-filter", "search-sort"])
        first = out["entries"][0]
        self.assertEqual((first["page"], first["status"], first["tickets"]), ("features/search.md", "specified", [12, 15]))
        self.assertEqual(out["entries"][1]["verifiedCommit"], "abc123")
        self.assertEqual(out["problems"], 0)

    def test_index_filters_by_ticket(self):
        self.assertEqual([e["id"] for e in self.wiki.index(15)["entries"]], ["search-filter"])
        self.assertEqual(self.wiki.index(99)["entries"], [])

    def test_absent_wiki_is_refused_with_the_init_hint(self):
        with self.assertRaises(pilot.Refused) as caught:
            pilot.Wiki(str(self.root / "nope")).index()
        self.assertEqual(caught.exception.payload["reason"], "wiki-absent")

    def test_headings_and_meta_inside_a_code_fence_are_ignored(self):
        self.page("fence.md", "# F\n\n```\n## Fake {#fake}\n<!-- wiki: status=proposed tickets=#1 -->\n```\n")
        out = self.wiki.index()
        self.assertNotIn("fake", [e["id"] for e in out["entries"]])
        self.assertEqual(out["problems"], 0)

    def test_unreadable_entries_are_reported(self):
        self.page("bad.md", (
            "## No meta {#no-meta}\n\ntext\n\n"
            "## Derived {#derived}\n<!-- wiki: status=in-dev tickets=#1 -->\n\n"
            "## Tickets {#bad-tickets}\n<!-- wiki: status=proposed tickets=12 -->\n\n"
            "## Stamp {#stamp}\n<!-- wiki: status=implemented tickets=#1 verifiedAt=2026-01-01T00:00:00Z verifiedCommit= -->\n\n"
            "## Key {#key}\n<!-- wiki: status=proposed tickets=#1 colour=red -->\n\n"
            "<!-- wiki: status=proposed tickets=#1 -->\n"))
        report = self.wiki.lint(FakeGh([issue(n) for n in (1, 3, 12, 15)]))
        self.assertFalse(report["ok"])
        for code in ("missing-meta", "bad-status", "bad-tickets", "partial-stamp", "unknown-key", "orphan-meta"):
            self.assertIn(code, self.codes(report))
        derived = next(f for f in report["findings"] if f["code"] == "bad-status")
        self.assertIn("derived", derived["message"])

    def test_set_rewrites_only_the_meta_line(self):
        before = (self.root / "features/search.md").read_text()
        out = self.wiki.set("search-filter", status="implemented", add=[20], remove=[12])
        self.assertEqual(out["tickets"], [15, 20])
        after = (self.root / "features/search.md").read_text()
        diff = [(a, b) for a, b in zip(before.split("\n"), after.split("\n")) if a != b]
        self.assertEqual(len(diff), 1)
        self.assertEqual(diff[0][1], "<!-- wiki: status=implemented tickets=#15,#20 verifiedAt= verifiedCommit= -->")
        self.assertEqual(len(before.split("\n")), len(after.split("\n")))

    def test_set_stamp_records_time_and_commit(self):
        out = self.wiki.set("search-filter", stamp="deadbeef")
        self.assertEqual(out["verifiedCommit"], "deadbeef")
        self.assertRegex(out["verifiedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(self.wiki.index()["entries"][0]["verifiedCommit"], "deadbeef")

    def test_set_clear_stamp_forgets_the_verification(self):
        out = self.wiki.set("search-sort", status="specified", clear_stamp=True)
        self.assertEqual((out["verifiedAt"], out["verifiedCommit"]), ("", ""))
        self.assertEqual(self.wiki.index()["problems"], 0)

    def test_derived_tickets_carry_their_level(self):
        out = self.derived("search-filter", issue(12, ["level:task", "status:in-dev"]), issue(15, ["level:story", "status:split"]))
        self.assertEqual([t["level"] for t in out["tickets"]], ["task", "story"])

    def test_set_refuses_a_derived_status_and_an_unknown_entry(self):
        for derived in ("in-dev", "verified"):
            with self.assertRaises(pilot.Refused) as caught:
                self.wiki.set("search-filter", status=derived)
            self.assertEqual(caught.exception.payload["reason"], "bad-status")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("nope", status="proposed")
        self.assertEqual(caught.exception.payload["reason"], "entry-not-found")

    def test_add_appends_an_entry_and_creates_the_page(self):
        self.wiki.add("flows/booking.md", "booking-start", "Start a booking", "proposed", [7], "Body text.")
        text = (self.root / "flows/booking.md").read_text()
        self.assertTrue(text.startswith("# Booking\n"))
        entry = next(e for e in self.wiki.index()["entries"] if e["id"] == "booking-start")
        self.assertEqual((entry["status"], entry["tickets"], entry["page"]), ("proposed", [7], "flows/booking.md"))
        self.assertIn("Body text.", self.wiki.show("booking-start", FakeGh([issue(7)]))["text"])
        self.assertEqual(self.wiki.index()["problems"], 0)

    def test_add_refuses_duplicates_and_bad_input(self):
        for args, reason in ((("features/search.md", "search-sort", "T", "proposed"), "duplicate-id"),
                             (("x.md", "Bad Id", "T", "proposed"), "bad-id"),
                             (("x.md", "ok-id", "T", "in-dev"), "bad-status"),
                             (("../x.md", "ok-id", "T", "proposed"), "bad-page"),
                             (("x.txt", "ok-id", "T", "proposed"), "bad-page")):
            with self.assertRaises(pilot.Refused) as caught:
                self.wiki.add(*args)
            self.assertEqual(caught.exception.payload["reason"], reason, args)

    def derived(self, entry_id, *issues):
        return self.wiki.status(FakeGh(list(issues)), [entry_id])["entries"][0]

    def test_derived_status_is_the_most_advanced_open_ticket(self):
        self.assertEqual(self.derived("search-filter", issue(12, ["status:in-dev"]), issue(15, ["status:backlog"]))["derived"], "in-dev")
        self.assertEqual(self.derived("search-filter", issue(12, ["status:in-dev"]), issue(15, ["status:review-ready"]))["derived"], "in-review")
        self.assertEqual(self.derived("search-filter", issue(12, ["status:changes-requested"]), issue(15, ["status:backlog"]))["derived"], "in-review")
        out = self.derived("search-filter", issue(12, ["status:qa"]), issue(15, ["status:in-review"]))
        self.assertEqual((out["derived"], out["display"]), ("in-qa", "specified · in-qa"))
        self.assertEqual(self.derived("search-filter", issue(12, ["status:backlog"]), issue(15, ["status:backlog"]))["derived"], "")

    def test_verified_needs_an_implemented_entry_and_a_done_feature_story(self):
        done = issue(3, ["type:feature", "level:story", "status:done"], state="closed")
        self.assertEqual(self.derived("search-sort", done)["display"], "implemented · verified")
        tech = issue(3, ["type:tech", "level:story", "status:done"], state="closed")
        self.assertEqual(self.derived("search-sort", tech)["derived"], "")
        task = issue(3, ["type:feature", "level:task", "status:done"], state="closed")
        self.assertEqual(self.derived("search-sort", task)["derived"], "")

    def test_verified_also_needs_a_lint_stamp(self):
        done = issue(12, ["type:feature", "level:story", "status:done"], state="closed")
        self.wiki.set("search-filter", status="implemented")
        self.assertEqual(self.derived("search-filter", done, issue(15, state="closed"))["derived"], "")
        self.wiki.set("search-filter", stamp="abc123")
        self.assertEqual(self.derived("search-filter", done, issue(15, state="closed"))["derived"], "verified")

    def test_snapshot_carries_entries_derived_status_and_text(self):
        gh = FakeGh([issue(12, ["status:in-dev"]), issue(15, ["status:backlog"]),
                     issue(3, ["status:done"], state="closed")])
        gh.repo = "o/r"
        doc = self.wiki.snapshot(gh)
        self.assertEqual((doc["kind"], doc["repo"], doc["total"], doc["truncated"]), ("wiki", "o/r", 2, False))
        first, second = doc["entries"]
        self.assertEqual((first["id"], first["page"], first["display"], first["tickets"]),
                         ("search-filter", "features/search.md", "specified · in-dev", [12, 15]))
        self.assertEqual(first["text"], "The user can filter results.")
        self.assertEqual((second["id"], second["verifiedAt"], second["text"]), ("search-sort", "2026-01-01T00:00:00Z", ""))

    def test_snapshot_shortens_then_drops_text_to_fit_a_database_document(self):
        self.page("big.md", "".join("## E%d {#e%d}\n<!-- wiki: status=implemented tickets= -->\n\n%s\n\n" % (i, i, "x" * 1500)
                                    for i in range(250)))
        doc = self.wiki.snapshot(FakeGh([issue(12), issue(15), issue(3)]))
        self.assertTrue(doc["truncated"])
        self.assertLessEqual(len(json.dumps(doc, ensure_ascii=False).encode("utf-8")), pilot.WIKI_SNAPSHOT_MAX_BYTES)
        self.assertEqual(doc["total"], 252)

    def test_a_missing_ticket_is_reported_not_fatal(self):
        out = self.derived("search-sort")
        self.assertEqual(out["tickets"], [{"number": 3, "missing": True}])

    def test_lint_is_clean_on_a_coherent_wiki(self):
        gh = FakeGh([issue(12, ["status:in-dev"]), issue(15, ["status:backlog"]),
                     issue(3, ["status:done"], state="closed")])
        self.assertEqual(self.wiki.lint(gh), {"ok": True, "entries": 2, "findings": []})

    def test_lint_flags_duplicates_orphaned_promises_and_reopened_work(self):
        self.page("dup.md", "## Again {#search-sort}\n<!-- wiki: status=proposed tickets= -->\n")
        gh = FakeGh([issue(12, state="closed"), issue(15, state="closed"), issue(3, ["status:backlog"])])
        report = self.wiki.lint(gh)
        self.assertEqual(self.codes(report), sorted(
            ["duplicate-id", "duplicate-id", "no-ticket", "orphaned-promise", "implemented-but-reopened"]))

    def test_lint_flags_an_unknown_ticket(self):
        report = self.wiki.lint(FakeGh([issue(3, ["status:done"], state="closed"), issue(12, ["status:backlog"])]))
        self.assertEqual(self.codes(report), ["unknown-ticket"])

    def test_an_implemented_entry_whose_pr_is_still_open_is_not_reopened(self):
        gh = FakeGh([issue(12), issue(15), issue(3, ["status:in-review"])])
        self.assertEqual(self.wiki.lint(gh)["findings"], [])

    def test_offline_commands_need_no_repository(self):
        parser = pilot.build_parser()
        for argv, needs in ((["wiki", "index"], False), (["wiki", "add", "a.md", "x", "--title", "T", "--status", "proposed"], False),
                            (["wiki", "set", "x", "--stamp", "c"], False), (["wiki", "lint"], True),
                            (["wiki", "show", "x"], True), (["wiki", "status"], True), (["pool", "dev"], True)):
            self.assertEqual(pilot.needs_github(parser.parse_args(argv)), needs, argv)

    def test_repo_flag_is_accepted_after_a_wiki_subcommand(self):
        args = pilot.build_parser().parse_args(["wiki", "lint", "--repo", "o/r"])
        self.assertEqual(args.repo, "o/r")

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

    def test_wiki_document_has_the_shape_of_wiki_snapshot(self):
        doc = self.demo.wiki_document()
        self.assertEqual((doc["kind"], doc["repo"], doc["total"], doc["truncated"]), ("wiki", "Jonas-Eve/pilot", len(doc["entries"]), False))
        self.assertLessEqual(len(json.dumps(doc, ensure_ascii=False).encode()), pilot.WIKI_SNAPSHOT_MAX_BYTES)
        keys = {"id", "title", "page", "status", "derived", "display", "tickets", "verifiedAt", "text"}
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
