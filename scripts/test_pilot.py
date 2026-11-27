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
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pilot  # noqa: E402
import pilot_checks  # noqa: E402


_CWD, _TMP = None, None


def setUpModule():
    """Run from an empty directory: the engine reads `.pilot/state.json` from the working directory, so a repo that has
    adopted PILOT (this one does) must not change what the tests see. Tests that need the repo use paths from __file__."""
    global _CWD, _TMP
    _CWD, _TMP = os.getcwd(), tempfile.TemporaryDirectory()
    os.chdir(_TMP.name)


def tearDownModule():
    os.chdir(_CWD)
    _TMP.cleanup()


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

    def issue_events(self, number):
        return list(getattr(self, "events", {}).get(number, []))

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
        return set(getattr(self, "labels", pilot.required_labels()))

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
        self.cid = getattr(self, "cid", 0) + 1
        self.run_comments = getattr(self, "run_comments", {})
        self.run_comments.setdefault(number, []).append({"id": self.cid, "body": text})

    def comment_items(self, number):
        return list(getattr(self, "run_comments", {}).get(number, []))

    def patch_comment(self, comment_id, text):
        for items in getattr(self, "run_comments", {}).values():
            for c in items:
                if c["id"] == comment_id:
                    c["body"] = text

    def create_issue(self, title, body, labels, assignees):
        number = max(self.store, default=0) + 1
        self.store[number] = issue(number, labels, body=body, assignees=assignees)
        self.store[number]["title"] = title
        self.store[number]["id"] = 1000 + number
        return copy.deepcopy(self.store[number])

    def add_sub_issue(self, parent, child_id):
        child = next(n for n, i in self.store.items() if i.get("id") == child_id)
        self.subs.setdefault(parent, []).append(child)


def machine(issues, **kw):
    gh = FakeGh(issues, **kw)
    return pilot.Machine(gh), gh


def names(raw):
    return sorted(l["name"] for l in raw["labels"])


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
        out = self.wiki.set("search-sort", stamp="deadbeef")
        self.assertEqual(out["verifiedCommit"], "deadbeef")
        self.assertRegex(out["verifiedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertIn("by: process:pilot-wiki", self.text("search/search-sort.md"))
        out = self.wiki.set("search-sort", status="specified", clear_stamp=True)
        self.assertEqual((out["verifiedAt"], out["verifiedCommit"]), ("", ""))
        self.assertNotIn("verified", self.text("search/search-sort.md"))
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

    def test_remove_deletes_an_entry_of_any_status_and_its_empty_folder(self):
        self.wiki.add("tmp/one.md", "One", "d", "proposed", [7])
        self.wiki.remove("one")
        self.assertFalse((self.root / "tmp").exists())
        self.assertNotIn("tmp", self.text("index.md"))
        self.wiki.remove("search-sort")  # implemented: a retired entry is deleted, not kept
        self.assertFalse((self.root / "search" / "search-sort.md").exists())

    def test_remove_is_refused_while_another_entry_cites_it_and_for_the_vision(self):
        self.wiki.add("search/by-name.md", "By name", "d", "proposed", [9], body="See [filter](search-filter.md).")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.remove("search-filter")
        self.assertEqual((caught.exception.payload["reason"], caught.exception.payload["citedBy"]), ("cited", ["by-name"]))
        self.wiki.remove("by-name")
        self.wiki.remove("search-filter")
        self.wiki.add("product/vision.md", "Vision", "What it is.", typ="Vision", body="Why.")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.remove("vision")
        self.assertEqual(caught.exception.payload["reason"], "vision-never-removed")

    def test_a_persona_a_flow_names_is_not_removed(self):
        self.wiki.add("persona/marie.md", "Marie", "A user.", typ="Persona", body="Low vision.")
        self.wiki.add("user-flow/find.md", "Find", "Search.", "implemented", typ="UserFlow", body="Personas: marie")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.remove("marie")
        self.assertEqual((caught.exception.payload["reason"], caught.exception.payload["citedBy"]), ("cited", ["find"]))

    def test_a_vision_and_a_persona_carry_no_status(self):
        for args in (("product/vision.md", "V", "d", "implemented"), ("persona/p.md", "P", "d", "implemented")):
            with self.assertRaises(pilot.Refused) as caught:
                self.wiki.add(*args, typ="Vision" if "vision" in args[0] else "Persona")
            self.assertEqual(caught.exception.payload["reason"], "status-not-allowed")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.add("persona/q.md", "Q", "d", "proposed", typ="Persona")
        self.assertEqual(caught.exception.payload["reason"], "status-not-allowed")

    def test_a_stamp_says_who_verified_and_only_a_known_verifier_is_accepted(self):
        self.wiki.set("search-sort", stamp="abc", by="process:pilot-qa")
        self.assertIn("by: process:pilot-qa", self.text("search/search-sort.md"))
        rows = {r["id"]: r for r in self.wiki.snapshot(FakeGh([]))["entries"]}
        self.assertEqual(rows["search-sort"]["verifiedBy"], "process:pilot-qa")
        self.assertEqual(rows["search-filter"]["verifiedBy"], "")
        self.wiki.set("search-sort", stamp="def")
        self.assertIn("by: process:pilot-wiki", self.text("search/search-sort.md"))
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("search-sort", stamp="ghi", by="somebody")
        self.assertEqual(caught.exception.payload["reason"], "bad-verifier")
        parse = pilot.build_parser().parse_args
        self.assertEqual(parse(["wiki", "set", "x", "--stamp", "abc", "--by", "process:pilot-dev"]).by, "process:pilot-dev")

    def test_a_stamp_is_written_only_on_an_implemented_entry_that_code_verifies(self):
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("search-filter", stamp="abc")  # specified
        self.assertEqual(caught.exception.payload["reason"], "stamp-needs-status")
        self.wiki.set("search-filter", status="implemented", stamp="abc")
        self.wiki.add("user-flow/f.md", "F", "d", "implemented", typ="UserFlow")
        with self.assertRaises(pilot.Refused) as caught:
            self.wiki.set("f", stamp="abc")
        self.assertEqual(caught.exception.payload["reason"], "never-stamped")

    def test_there_is_no_deprecated_status_any_more(self):
        self.entry("search/old.md", "implemented", [3])
        old = self.root / "search" / "old.md"
        old.write_text(old.read_text().replace("status: implemented", "status: deprecated").replace("status: stable", "status: deprecated"))
        self.wiki.reindex()
        report = self.lint(issue(3, ["status:done"], state="closed"), issue(12, ["status:building"]), issue(15, ["status:forming"]))
        self.assertIn("bad-status", self.codes(report))
        self.assertFalse(report["ok"])
        for call in (lambda: self.wiki.set("search-filter", status="deprecated"),
                     lambda: self.wiki.add("search/new.md", "N", "d", "deprecated")):
            with self.assertRaises(pilot.Refused) as caught:
                call()
            self.assertEqual(caught.exception.payload["reason"], "bad-status")
        self.assertNotIn("deprecated", pilot.WIKI_STATUSES + pilot.ARCH_STATUSES)

    # ---- derived status ---------------------------------------------------------------------
    def derived(self, entry_id, *issues):
        return self.wiki.status(FakeGh(list(issues)), [entry_id])["entries"][0]

    def test_derived_status_is_the_most_advanced_open_ticket(self):
        self.assertEqual(self.derived("search-filter", issue(12, ["status:building"]), issue(15, ["status:forming"]))["derived"], "in-dev")
        self.assertEqual(self.derived("search-filter", issue(12, ["status:building"]), issue(15, ["status:reviewing"]))["derived"], "in-review")
        self.assertEqual(self.derived("search-filter", issue(12, ["status:reviewing"]), issue(15, ["status:forming"]))["derived"], "in-review")
        out = self.derived("search-filter", issue(12, ["status:merged"]), issue(15, ["status:reviewing"]))
        self.assertEqual((out["derived"], out["display"]), ("in-qa", "specified · in-qa"))
        self.assertEqual(self.derived("search-filter", issue(12, ["status:forming"]), issue(15, ["status:forming"]))["derived"], "")

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
        out = self.derived("search-filter", issue(12, ["level:task", "status:building"]), issue(15, ["level:story", "status:planned"]))
        self.assertEqual([t["level"] for t in out["tickets"]], ["task", "story"])
        self.assertEqual(self.derived("search-sort")["tickets"], [{"number": 3, "missing": True}])

    def test_show_returns_the_text_and_the_overlay(self):
        out = self.wiki.show("search-filter", FakeGh([issue(12, ["status:building"]), issue(15)]))
        self.assertEqual((out["text"], out["derived"]["display"]), ("The user can filter results.", "specified · in-dev"))

    # ---- lint -------------------------------------------------------------------------------
    def test_lint_is_clean_on_a_coherent_wiki(self):
        report = self.lint(issue(12, ["status:building"]), issue(15, ["status:forming"]), issue(3, ["status:done"], state="closed"))
        self.assertEqual(report, {"ok": True, "entries": 2, "findings": []})

    def test_a_vision_entry_needs_no_ticket_and_lints_clean(self):
        self.wiki.add("product/vision.md", "Vision", "What the product is, for whom and by which principles.",
                      body="A travel assistant for people with disabilities.", typ="Vision")
        self.assertIn("type: Vision", self.text("product/vision.md"))
        report = self.lint(issue(12, ["status:building"]), issue(15, ["status:forming"]), issue(3, ["status:done"], state="closed"))
        self.assertEqual(report, {"ok": True, "entries": 3, "findings": []})

    def test_lint_flags_duplicates_orphaned_promises_and_reopened_work(self):
        self.entry("elsewhere/search-sort.md", "proposed", [])
        self.wiki.reindex()
        report = self.lint(issue(12, state="closed"), issue(15, state="closed"), issue(3, ["status:forming"]))
        self.assertEqual(self.codes(report), sorted(
            ["duplicate-id", "duplicate-id", "no-ticket", "orphaned-promise", "implemented-but-reopened"]))

    def test_lint_flags_an_unknown_ticket_and_spares_an_open_pr(self):
        self.assertEqual(self.codes(self.lint(issue(3, ["status:done"], state="closed"), issue(12, ["status:forming"]))), ["unknown-ticket"])
        self.assertEqual(self.lint(issue(12), issue(15), issue(3, ["status:reviewing"]))["findings"], [])

    # ---- snapshot -----------------------------------------------------------------------------
    def test_snapshot_carries_entries_derived_status_and_text(self):
        gh = FakeGh([issue(12, ["status:building"]), issue(15, ["status:forming"]), issue(3, ["status:done"], state="closed")])
        doc = self.wiki.snapshot(gh)
        self.assertEqual((doc["kind"], doc["repo"], doc["total"], doc["truncated"]), ("wiki", "o/r", 2, False))
        first, second = doc["entries"]
        self.assertEqual((first["id"], first["path"], first["display"], first["tickets"], first["description"]),
                         ("search-filter", "search/search-filter.md", "specified · in-dev", [12, 15], "The user can filter results."))
        self.assertEqual(first["text"], "The user can filter results.")
        self.assertEqual(first["type"], "Behavior")  # the dashboard tells persona and user-flow entries apart by it
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
                            (["wiki", "status"], True), (["wiki", "snapshot"], True), (["pool", "build"], True)):
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
                return pilot.Machine(FakeGh([issue(1, ["status:forming"])])).snapshot()
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

    def test_verify_stamps_an_accepted_guideline_or_adr_and_refuses_one_not_in_force(self):
        self.add("guidelines/layering.md", "accepted")
        self.add("adr/0001-a.md", "accepted")
        self.add("guidelines/draft.md", "proposed")
        self.add("adr/0002-b.md", "accepted")
        self.arch.set("layering", stamp="abc1234")
        before = self.text("adr/0001-a.md").split("---", 2)[2]
        self.arch.set("0001-a", stamp="abc1234")
        self.assertEqual(self.text("adr/0001-a.md").split("---", 2)[2], before)  # a stamp never edits the decision
        rows = {r["id"]: r for r in self.arch.snapshot("o/r")["entries"]}
        self.assertTrue(rows["layering"]["verifiedAt"] and rows["0001-a"]["verifiedAt"])  # what the cockpit's chip reads
        self.assertEqual(self.arch.show("layering")["verifiedCommit"], "abc1234")
        self.assertEqual(self.arch.show("0001-a")["verifiedCommit"], "abc1234")
        with self.assertRaises(pilot.Refused):
            self.arch.set("draft", stamp="abc1234")
        self.arch.supersede("0002-b", "0001-a")
        with self.assertRaises(pilot.Refused):
            self.arch.set("0001-a", stamp="def5678")

    def test_accepting_a_proposed_entry_puts_it_in_force_and_lints_clean(self):
        self.add("adr/0001-a.md", "proposed")
        self.add("guidelines/layering.md", "proposed")
        self.assertEqual([e["id"] for e in self.arch.index(active=True)["entries"]], [])
        self.arch.set("0001-a", status="accepted")
        self.arch.set("layering", status="accepted")
        self.assertEqual(sorted(e["id"] for e in self.arch.index(active=True)["entries"]), ["0001-a", "layering"])
        self.assertEqual(self.codes(), [])

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

    def test_a_runbook_is_an_entry_read_on_demand_never_carried_in_a_prompt(self):
        self.add("guidelines/layering.md", "accepted")
        self.add("runbooks/deploy.md", "accepted", description="How a release goes out.")
        self.add("apps/web/runbooks/provision.md", "accepted", description="How the web app is provisioned.")
        self.assertIn("type: Runbook", self.text("runbooks/deploy.md"))
        self.assertIn("type: Runbook", self.text("apps/web/runbooks/provision.md"))
        everything = [e["id"] for e in self.arch.index()["entries"]]
        in_force = [e["id"] for e in self.arch.index(active=True)["entries"]]
        self.assertEqual(sorted(everything), ["deploy", "layering", "provision"])
        self.assertEqual(in_force, ["layering"])  # what a phase prompt carries leaves runbooks out
        self.assertIn("deploy", [e["id"] for e in self.arch.search("release")["results"]])  # but they are found on demand
        self.assertEqual(self.codes(), [])
        self.assertEqual(self.arch.snapshot("o/r")["total"], 3)
        outline = self.arch.outline("", active=True)
        self.assertNotIn("runbooks", [f["path"].strip("/") for f in outline.get("folders", [])])

    def test_a_reference_entry_is_carried_in_force_and_stamped_against_the_code(self):
        self.add("guidelines/layering.md", "accepted")
        self.add("reference/data-model.md", "accepted", description="The tables and their relations.")
        self.add("apps/web/reference/stack.md", "accepted", description="Framework and versions of the web app.")
        self.assertIn("type: Reference", self.text("reference/data-model.md"))
        self.assertIn("type: Reference", self.text("apps/web/reference/stack.md"))
        in_force = sorted(e["id"] for e in self.arch.index(active=True)["entries"])
        self.assertEqual(in_force, ["data-model", "layering", "stack"])  # unlike a runbook, a phase prompt lists it
        self.arch.set("data-model", stamp="abc1234")
        shown = self.arch.show("data-model")
        self.assertTrue(shown["verifiedAt"])
        self.assertEqual(shown["verifiedCommit"], "abc1234")
        rows = {r["id"]: r for r in self.arch.snapshot("o/r")["entries"]}
        self.assertTrue(rows["data-model"]["verifiedAt"])
        self.assertEqual(rows["layering"]["verifiedAt"], "")
        self.assertEqual(self.codes(), [])

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
        rows = self.arch.index(active=True)["entries"]
        self.assertEqual(sorted(r["id"] for r in rows), ["layering"])
        self.assertTrue(all(set(r) == {"id", "path", "description", "status"} for r in rows))
        self.assertEqual(len(self.arch.index()["entries"]), 3)

    def test_remove_deletes_what_is_not_history_and_refuses_the_rest(self):
        self.add("adr/0001-a.md", "accepted")
        self.add("adr/0002-b.md", "proposed")
        self.add("adr/0003-c.md", "proposed")
        self.add("guidelines/layering.md", "accepted", description="Domain never imports adapters.")
        self.add("overview.md", "accepted", description="The apps.")
        self.arch.supersede("0002-b", "0001-a")
        for entry, reason in (("0001-a", "superseded-is-history"), ("overview", "overview-never-removed")):
            with self.assertRaises(pilot.Refused) as caught:
                self.arch.remove(entry)
            self.assertEqual(caught.exception.payload["reason"], reason)
        self.arch.set("0003-c", status="accepted")
        with self.assertRaises(pilot.Refused) as caught:
            self.arch.remove("0003-c")  # an accepted ADR is retired by a new one that supersedes it
        self.assertEqual(caught.exception.payload["reason"], "accepted-adr")
        self.arch.remove("layering")
        self.assertFalse((self.root / "guidelines" / "layering.md").exists())

    def test_a_proposed_entry_is_not_in_force_so_a_phase_prompt_does_not_carry_it(self):
        self.add("guidelines/layering.md", "accepted", description="Domain never imports adapters.")
        self.add("guidelines/draft.md", "proposed", description="A rule nobody accepted yet.")
        self.add("adr/0001-x.md", "proposed", description="A decision still to take.")
        self.assertEqual([r["id"] for r in self.arch.index(active=True)["entries"]], ["layering"])
        self.assertEqual(sorted(r["id"] for r in self.arch.index()["entries"]), ["0001-x", "draft", "layering"])
        self.assertIn("draft", [e["id"] for e in self.arch.search("nobody")["results"]])  # still found on demand
        self.assertEqual(self.arch.show("draft")["status"], "proposed")

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


class FlowRunDocTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wiki = pilot.Wiki(root=self.tmp.name)
        for pid in ("marie", "paul"):
            self.wiki.add(f"persona/{pid}.md", pid.title(), "A user.", body="Low vision.", typ="Persona")
        self.wiki.add("user-flow/find.md", "Find a place", "Search.", "implemented", body="Personas: marie, paul", typ="UserFlow")
        self.wiki.add("search/sort.md", "Sort", "Sorted.", "implemented")

    @staticmethod
    def run_of(pid, *results, session="started"):
        return {"persona": pid, "session": session, "steps": [{"n": i + 1, "result": r} for i, r in enumerate(results)]}

    def doc(self, *runs, bugs=(), flow="find"):
        data = {"flow": flow, "personas": list(runs), "report": {"bugs": [{"ticket": b} for b in bugs]}, "reportUrl": "https://claude.ai/artifact/x"}
        return pilot.flow_run_doc(self.wiki, "o/r", data)

    def test_the_result_is_the_worst_of_the_personas(self):
        ok, untestable = self.run_of("marie", "passed", "passed"), self.run_of("paul", "passed", "untestable")
        bad = self.run_of("paul", "passed", "failed")
        self.assertEqual(self.doc(ok)["result"], "passed")
        self.assertEqual(self.doc(ok, untestable)["result"], "partial")
        self.assertEqual(self.doc(untestable, bad)["result"], "failed")
        self.assertEqual(self.doc(self.run_of("marie", "passed", "untestable", session="started"), self.run_of("paul", session="not-started"))["result"], "partial")

    def test_the_document_names_each_persona_with_its_result_steps_and_the_bugs(self):
        doc = self.doc(self.run_of("marie", "passed", "failed"), self.run_of("paul", "passed", "passed"), bugs=(7, 9))
        self.assertEqual((doc["kind"], doc["repo"], doc["flow"], doc["bugs"], doc["report"]), ("flowRun", "o/r", "find", [7, 9], "https://claude.ai/artifact/x"))
        marie, paul = doc["personas"]
        self.assertEqual((marie["id"], marie["result"], marie["steps"]), ("marie", "failed", {"passed": 1, "failed": 1, "untestable": 0}))
        self.assertEqual((paul["id"], paul["result"]), ("paul", "passed"))

    def test_hashes_follow_the_text_of_the_flow_and_of_each_persona_and_match_the_snapshot(self):
        before = self.doc(self.run_of("marie", "passed"))
        rows = {r["id"]: r for r in self.wiki.snapshot(FakeGh([]))["entries"]}
        self.assertEqual((before["hash"], before["personas"][0]["hash"]), (rows["find"]["hash"], rows["marie"]["hash"]))
        path = os.path.join(self.tmp.name, "persona", "marie.md")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace("Low vision.", "Blind."))
        after = self.doc(self.run_of("marie", "passed"))
        self.assertEqual(after["hash"], before["hash"])
        self.assertNotEqual(after["personas"][0]["hash"], before["personas"][0]["hash"])

    def test_a_run_that_played_no_step_writes_nothing_and_a_sloppy_ticket_number_does_not_crash(self):
        with self.assertRaises(pilot.Refused) as refused:
            self.doc(self.run_of("marie", session="not-started"), self.run_of("paul", "untestable"))
        self.assertEqual(refused.exception.payload["reason"], "nothing-run")
        doc = self.doc(self.run_of("marie", "passed"), bugs=("#12", "x", 0, 5))
        self.assertEqual(doc["bugs"], [12, 5])
        for bad in ("nope", [1], {"flow": "find", "personas": ["marie"]}):
            with self.assertRaises(pilot.Refused):
                pilot.flow_run_doc(self.wiki, "o/r", bad)

    def test_the_cli_add_takes_the_type_from_the_folder_and_show_reports_it(self):
        parse = pilot.build_parser().parse_args
        self.assertIsNone(parse(["wiki", "add", "user-flow/x.md", "--title", "T", "--description", "D", "--status", "implemented"]).type)
        self.wiki.add("user-flow/x.md", "T", "D", "implemented", typ=None)
        self.assertEqual(self.wiki.show("x", FakeGh([]))["type"], "UserFlow")

    def test_the_folder_sets_the_type_of_a_new_entry(self):
        self.wiki.add("persona/zoe.md", "Zoe", "A user.")
        self.wiki.add("user-flow/buy.md", "Buy", "A journey.", "proposed", tickets=[3])
        self.wiki.add("top-level.md", "Top", "A rule.", "implemented")
        kinds = {e["id"]: e["type"] for e in self.wiki.parse()}
        self.assertEqual((kinds["zoe"], kinds["buy"], kinds["top-level"], kinds["sort"]), ("Persona", "UserFlow", "Behavior", "Behavior"))

    def test_only_an_implemented_flow_is_played(self):
        for status in ("proposed", "specified"):
            self.wiki.add(f"user-flow/{status}.md", status, "Not built yet.", status, body="Personas: marie", typ="UserFlow")
            with self.assertRaises(pilot.Refused) as refused:
                self.doc(self.run_of("marie", "passed"), flow=status)
            self.assertEqual(refused.exception.payload["reason"], "flow-not-playable")

    def test_it_refuses_what_is_not_a_flow_or_a_persona_or_has_no_run(self):
        for flow, runs, reason in (("nope", [self.run_of("marie", "passed")], "not-a-user-flow"), ("sort", [self.run_of("marie", "passed")], "not-a-user-flow"),
                                   ("find", [self.run_of("sort", "passed")], "not-a-persona"), ("find", [], "no-persona-run")):
            with self.assertRaises(pilot.Refused) as refused:
                self.doc(*runs, flow=flow)
            self.assertEqual(refused.exception.payload["reason"], reason)


if __name__ == "__main__":
    unittest.main()


class ProtoPackTests(unittest.TestCase):
    def pack(self, html, **kw):
        import os
        import tempfile
        m, _ = machine([issue(7, ["run:proto"])])
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
        m, _ = machine([issue(7, ["status:ready"])])
        with self.assertRaises(pilot.Refused) as caught:
            m.proto_pack(7, "x", "y")
        self.assertEqual(caught.exception.payload["reason"], "not-a-proto-run")


class DocsMatchTheEngineTests(unittest.TestCase):
    """What the skills and docs tell an agent to run is what `pilot.py` accepts: a command, a sub-command, a flag, a status."""

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    SNIPPET = re.compile(r"`([^`\n]*\bpilot\.py\s+[^`\n]+)`")

    @staticmethod
    def sub_parsers(parser):
        import argparse
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices
        return None

    def problems(self, snippet, parser):
        text = re.sub(r'"[^"]*"|\'[^\']*\'', " ", snippet.split("pilot.py", 1)[1]).replace("…", " ")
        if "|" in text.split("--")[0]:
            return []  # a family of commands written once (`claim|set|flag`)
        tokens = text.split()
        node, path, out = parser, [], []
        i = 0
        while i < len(tokens) and not tokens[i].startswith(("-", "<", "[", "$", "(")):
            subs = self.sub_parsers(node)
            if not subs:
                break
            word = tokens[i].rstrip(",.;:)")
            if word not in subs:
                if not re.fullmatch(r"[a-z][a-z-]*", word):
                    break
                return [f"`{' '.join(path + [word])}` is not a command"]
            node, path, i = subs[word], path + [word], i + 1
        known = {o for a in node._actions for o in a.option_strings} | {"--repo"}
        for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", text):
            if flag not in known:
                out.append(f"`{' '.join(path)}` has no {flag}")
        for action in node._actions:
            if "--status" in action.option_strings and action.choices:
                m = re.search(r"--status\s+([a-z]+)\b", text)
                if m and m.group(1) not in action.choices:
                    out.append(f"`{' '.join(path)} --status {m.group(1)}`: not one of {', '.join(action.choices)}")
        return out

    def test_every_pilot_py_command_a_skill_or_doc_names_exists(self):
        parser = pilot.build_parser()
        found, bad = 0, []
        for path in sorted(self.ROOT.glob(".claude/skills/*/SKILL.md")) + sorted(self.ROOT.glob("assets/docs/*.md")):
            for snippet in self.SNIPPET.findall(path.read_text(encoding="utf-8")):
                found += 1
                bad += [f"{path.relative_to(self.ROOT)}: {p}  ({snippet.strip()[:90]})" for p in self.problems(snippet, parser)]
        self.assertGreater(found, 80, "the scan found too few commands: the pattern no longer matches the docs")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_check_catches_a_removed_flag_a_wrong_command_and_a_gone_status(self):
        parser = pilot.build_parser()
        self.assertEqual(self.problems("python3 .pilot/pilot.py wiki set <id> --status implemented --stamp <commit>", parser), [])
        self.assertEqual(len(self.problems("python3 .pilot/pilot.py wiki set <id> --status deprecated", parser)), 1)
        self.assertEqual(len(self.problems("python3 .pilot/pilot.py wiki deprecate <id>", parser)), 1)
        self.assertEqual(len(self.problems("python3 .pilot/pilot.py wiki remove <id> --force", parser)), 1)


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
        """A description sits in the context of every session of a consuming project, invoked or not: the mechanics
        belong in the body, which is loaded only when the skill runs. A skill with `disable-model-invocation: true` is
        launched by its command only and its description is not carried, so only the others count towards the total;
        the six workflows of the Run category are the ones an agent may start on its own: they must stay model-invocable."""
        sizes, carried = {}, {}
        for f in (self.ROOT / ".claude/skills").glob("*/SKILL.md"):
            text = f.read_text()
            m = re.search(r"^description: (.*)$", text, re.M)
            sizes[f.parent.name] = len(m.group(1).encode())
            if not re.search(r"^disable-model-invocation: true$", text, re.M):
                carried[f.parent.name] = sizes[f.parent.name]
        self.assertEqual({k: v for k, v in sizes.items() if v > 1500}, {})
        self.assertLess(sum(carried.values()), 8_000)
        for name in ("pilot-need", "pilot-plan", "pilot-build", "pilot-accept", "pilot-report", "pilot-express"):
            self.assertIn(name, carried)

    def test_the_generic_file_stays_small(self):
        size = (self.ROOT / "assets/docs/pilot-process.md").stat().st_size
        self.assertLess(size, 10_000, "pilot-process.md is loaded by every workflow run; move what only some read into a link doc or a skill")


class SkillStepsTests(unittest.TestCase):
    """The numbered steps of every skill: in order within a section, no duplicate, and every `step N` a skill cites exists."""

    ROOT = pathlib.Path(__file__).resolve().parent.parent
    STEP = re.compile(r"^(\d+(?:-bis|[a-z])?)\.\s")
    REF = re.compile(r"(?<![\w`/.-])steps? (\d+(?:-bis|[a-z])?)(?:\s*[-–]\s*(\d+[a-z]?))?")

    @staticmethod
    def key(step):
        m = re.match(r"(\d+)(-bis|[a-z])?$", step)
        suffix = m.group(2) or ""
        return (int(m.group(1)), 0 if not suffix else 1 if suffix == "-bis" else 2 + ord(suffix))

    def sections(self, text):
        """Each `## ` section of a skill with the step ids it numbers, in file order."""
        out, current = [], ("", [])
        for line in text.splitlines():
            if line.startswith("## "):
                out.append(current)
                current = (line, [])
            m = self.STEP.match(line)
            if m:
                current[1].append(m.group(1))
        out.append(current)
        return [(title, ids) for title, ids in out if ids]

    def skills(self):
        return sorted(self.ROOT.glob(".claude/skills/pilot-*/SKILL.md"))

    def test_steps_are_numbered_in_order_with_no_duplicate_in_each_section(self):
        bad = []
        for path in self.skills():
            for title, ids in self.sections(path.read_text(encoding="utf-8")):
                if len(set(ids)) != len(ids):
                    bad.append(f"{path.parent.name} {title!r}: a step number is used twice: {ids}")
                keys = [self.key(i) for i in ids]
                if keys != sorted(keys):
                    bad.append(f"{path.parent.name} {title!r}: steps out of order: {ids}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_every_step_a_skill_cites_exists_in_it(self):
        bad = []
        for path in self.skills():
            text = path.read_text(encoding="utf-8")
            sections = self.sections(text)
            ids = [i for _t, group in sections for i in group]
            if len(sections) != 1 or len(set(ids)) != len(ids):
                continue  # several numbered sections (`--edit`, `--remove`…): "step 2" is ambiguous, order is still checked above
            known = set(ids)
            body = text.split("\n## ", 1)[1] if "\n## " in text else text
            for m in self.REF.finditer(body):
                before = body[max(0, m.start() - 70):m.start()]
                if re.search(r"(SKILL\.md|\.md`?)[^.\n]{0,40}$", before) or "`pilot-" in before[-30:]:
                    continue  # another skill's or a doc's step
                for ref in (m.group(1), m.group(2)):
                    if ref and ref not in known:
                        bad.append(f"{path.parent.name}: cites step {ref}, which it does not number (…{body[max(0, m.start() - 40):m.end() + 10]!r})")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_check_catches_an_order_a_duplicate_and_a_missing_step(self):
        text = "## Steps\n\n1. a\n2. b\n2b. c\n2a. d\n2a. e\n3. see step 9\n"
        (_title, ids), = self.sections(text)
        self.assertEqual(ids, ["1", "2", "2b", "2a", "2a", "3"])
        self.assertNotEqual([self.key(i) for i in ids], sorted(self.key(i) for i in ids))
        self.assertEqual(len(set(ids)), 5)
        self.assertLess(self.key("2"), self.key("2-bis"))
        self.assertLess(self.key("2-bis"), self.key("2a"))


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
        keys = {"id", "type", "hash", "title", "description", "path", "status", "derived", "display", "tickets", "verifiedAt", "verifiedBy", "text"}
        for row in doc["entries"]:
            self.assertEqual(set(row), keys)
            self.assertIn(row["status"], (*pilot.WIKI_STATUSES, ""))  # "" : an entry with no status yet
            self.assertIn(row["derived"], ("", "in-dev", "in-review", "in-qa", "verified"))

    def test_document_has_the_snapshot_shape_and_fits_a_database_document(self):
        self.assertEqual((self.doc["repo"], self.doc["truncated"], self.doc["total"]), ("Jonas-Eve/pilot", False, len(self.doc["issues"])))
        self.assertLessEqual(len(json.dumps(self.doc, ensure_ascii=False).encode()), pilot.SNAPSHOT_MAX_BYTES)
        numbers = [r["n"] for r in self.doc["issues"]]
        self.assertEqual(len(numbers), len(set(numbers)))
        for row in self.doc["issues"]:
            self.assertTrue({"n", "t", "l", "u"} <= set(row))

    def test_parents_progress_and_every_status_are_covered(self):
        rows = {r["n"]: r for r in self.doc["issues"]}
        for row in rows.values():
            if "p" in row:
                self.assertIn(row["p"], rows)
            if "k" in row:
                self.assertLessEqual(row["k"][0], row["k"][1])
        labels = {l for r in rows.values() for l in r["l"]}
        self.assertTrue({f"status:{s}" for s in pilot.STATUSES if s not in ("done", "wont-do")} <= labels)  # open tickets only
        self.assertTrue({"needs-human", "on-hold", "can-resume", "express", "fix", "gap", "run:proto"} <= labels)
        self.assertTrue(labels <= set(pilot.LABELS) | {f"status:{s}" for s in pilot.STATUSES} | {"needs-human", "on-hold", "can-resume", "express", "fix", "gap", "run:proto", "run:technical-frame"})
        self.assertTrue(any("level:epic" in r["l"] and "k" in r for r in rows.values()))
        self.assertTrue(any("r" in r for r in rows.values()) and any("a" in r for r in rows.values()))
        self.assertEqual(self.doc["workflows"], sorted(self.demo.WORKFLOWS))

    def test_live_documents(self):
        docs = self.demo.live_documents()
        self.assertEqual({d["kind"] for d in docs.values()}, {"ticket", "run"})
        for doc in docs.values():
            if doc["kind"] == "run":
                self.assertIn(doc["workflow"], self.doc["workflows"])
                self.assertIn(doc["state"], ("running", "waiting-human", "done"))


class WorkflowDataTests(unittest.TestCase):
    def test_the_eleven_workflows_load_and_check_out(self):
        wfs = pilot.load_workflows()
        self.assertEqual(sorted(wfs), ["accept", "build", "design-system", "express", "functional-frame", "need",
                                       "personas-flows", "plan", "proto", "report", "technical-frame"])
        self.assertEqual(pilot.workflow_problems(wfs), [])

    def test_express_includes_the_build_steps_it_runs_after_its_own(self):
        wfs = pilot.load_workflows()
        express = [s["id"] for s in wfs["express"]["steps"]]
        self.assertEqual(len(express), 19)
        self.assertIn("build-implement", express)
        self.assertNotIn("build-e2e", express)  # express runs no e2e
        rule = next(s for s in wfs["express"]["steps"] if s["id"] == "build-validate")["on_fail"]
        self.assertEqual(rule["to"], "build-implement")  # references follow the prefix
        ask = next(s for s in wfs["express"]["steps"] if s["id"] == "build-ask")
        self.assertIn("demandé l'express", ask["actor"])  # a patched field

    def test_the_contracts_compose_and_a_missing_producer_is_found(self):
        wfs = pilot.load_workflows()
        self.assertEqual(pilot.composition_problems(wfs), [])
        wfs["plan"]["contract"]["produces"] = []
        codes = {(p["status"], p["code"]) for p in pilot.composition_problems(wfs)}
        self.assertIn(("status:planned", "no-producer"), codes)

    def test_a_transition_is_admitted_by_a_contract_or_a_closing(self):
        wfs = pilot.load_workflows()
        self.assertTrue(pilot.transition_allowed(wfs, "status:ready", "status:building"))
        self.assertTrue(pilot.transition_allowed(wfs, "status:forming", "status:to-plan"))
        self.assertTrue(pilot.transition_allowed(wfs, None, "status:ready"))
        self.assertFalse(pilot.transition_allowed(wfs, "status:ready", "status:done"))

    def test_problems_name_what_is_wrong(self):
        wfs = pilot.load_workflows()
        step = wfs["need"]["steps"][3]
        step["on_fail"] = {"to": "nowhere", "max": 2, "then": "gate"}
        step["agents"] = [{"persona": "wizard"}]
        step["check"] = "need.nothing"
        wfs["need"]["steps"][1]["kind"] = "oops"
        codes = {p["code"] for p in pilot.workflow_problems(wfs)}
        self.assertTrue({"unknown-target", "unknown-persona", "unknown-kind"} <= codes)

    def test_numbers_follow_alternatives(self):
        steps = pilot.renumber([{"id": "a"}, {"id": "b"}, {"id": "c", "alt_of": "b"}, {"id": "d"}])
        self.assertEqual([s["n"] for s in steps], ["1", "2", "2bis", "3"])

    def test_a_step_view_carries_no_prose(self):
        wfs = pilot.load_workflows()
        view = pilot.Machine.step_view(wfs["build"]["steps"][3])
        self.assertNotIn("doc", view)
        self.assertEqual(view["kind"], "validator")
        out = pilot.run_workflow(types.SimpleNamespace(action="show", id="build", step="validate"))
        self.assertEqual(out["step"]["id"], "validate")
        with self.assertRaises(pilot.Refused):
            pilot.run_workflow(types.SimpleNamespace(action="show", id="nope", step=None))


def ticket(number, status="ready", level="story", labels=(), **kw):
    return issue(number, [f"status:{status}", f"level:{level}", "type:feature", *labels], **kw)


class PoolTests(unittest.TestCase):
    def test_fresh_unassigned_tickets_in_priority_then_age_order(self):
        m, _ = machine([ticket(1, labels=["priority:P1"], created="2026-01-01T00:00:00Z"),
                        ticket(2, labels=["priority:P0"], created="2026-02-01T00:00:00Z"),
                        ticket(3, labels=["priority:P0"], created="2026-01-15T00:00:00Z")])
        found = m.pool("build", 5)
        self.assertEqual([c["number"] for c in found["candidates"]], [3, 2, 1])
        self.assertEqual(found["pick"]["action"], "claim-fresh")

    def test_flags_dependencies_assignees_and_unrelated_statuses_are_excluded(self):
        m, _ = machine([ticket(1, labels=["needs-human"]), ticket(2, labels=["on-hold"]), ticket(3, assignees=["x"]),
                        ticket(4, body="Depends on #9"), issue(9, ["status:ready", "level:story"]), ticket(5, status="done"),
                        ticket(6, status="merged")])
        found = m.pool("build", 5)
        reasons = {e["number"]: e["reason"] for e in found["excluded"]}
        self.assertEqual(reasons, {1: "needs-human", 2: "on-hold", 3: "assigned", 4: "depends-on-open"})
        self.assertEqual([c["number"] for c in found["candidates"]], [9])

    def test_a_resumable_ticket_needs_can_resume(self):
        m, _ = machine([ticket(1, status="building", assignees=["x"], labels=["can-resume"]),
                        ticket(2, status="building", assignees=["x"])])
        found = m.pool("build", 5)
        self.assertEqual([c["number"] for c in found["candidates"]], [1])
        self.assertEqual(found["candidates"][0]["pool"], "resumable")
        self.assertEqual(found["excluded"][0]["reason"], "in-progress-without-can-resume")

    def test_a_workflow_that_claims_nothing_has_no_pool(self):
        m, _ = machine([])
        with self.assertRaises(pilot.Refused):
            m.pool("report", 5)


class ResolveTests(unittest.TestCase):
    def test_stop_reasons(self):
        m, _ = machine([ticket(1, state="closed"), ticket(2, labels=["needs-human"]), ticket(3, status="merged"),
                        issue(4, ["status:ready"], pr=True), ticket(5, assignees=["x"])])
        self.assertEqual(m.resolve("build", 99)["reason"], "not-found")
        self.assertEqual(m.resolve("build", 1)["reason"], "closed")
        self.assertEqual(m.resolve("build", 2)["reason"], "flagged")
        self.assertEqual(m.resolve("build", 3)["reason"], "wrong-status")
        self.assertEqual(m.resolve("build", 4)["action"], "manual")
        self.assertEqual(m.resolve("build", 5)["reason"], "assigned")

    def test_claim_resume_and_the_dependency_gate(self):
        m, _ = machine([ticket(1), ticket(2, body="Depends on #1"), ticket(3, status="building", labels=["can-resume"], assignees=["x"]),
                        ticket(4, status="building", assignees=["x"])])
        self.assertEqual(m.resolve("build", 1)["action"], "claim-fresh")
        self.assertEqual(m.resolve("build", 2)["reason"], "depends-on-open")
        self.assertEqual(m.resolve("build", 3)["action"], "resume-cleared")
        self.assertEqual(m.resolve("build", 4)["action"], "ask-resume")
        self.assertEqual(m.resolve("build", 4, resume=True)["action"], "resume-orphaned")
        self.assertEqual(m.resolve("plan", 1)["reason"], "wrong-status")  # not to-plan

    def test_an_epic_or_a_planned_story_descends_into_its_open_tasks(self):
        m, _ = machine([issue(1, ["level:epic", "status:planned"]), ticket(2, status="planned", labels=[]),
                        ticket(3, level="task"), ticket(4, level="task", state="closed")], subs={1: [2], 2: [3, 4]})
        out = m.resolve("build", 1)
        self.assertEqual((out["action"], out["pick"]["number"]), ("descend", 3))


class ClaimTests(unittest.TestCase):
    def test_a_fresh_claim_assigns_and_swaps_the_status_in_one_write(self):
        m, gh = machine([ticket(1)])
        out = m.claim("build", 1, "fresh")
        self.assertTrue(out["claimed"])
        self.assertEqual(names(gh.store[1]), ["level:story", "status:building", "type:feature"])
        self.assertEqual(gh.store[1]["assignees"], [{"login": "bot"}])
        self.assertEqual(out["event"]["action"], "claim:fresh")
        self.assertEqual(len([c for c in gh.calls if c[0] == "patch"]), 1)

    def test_refusals(self):
        m, _ = machine([ticket(1, assignees=["x"]), ticket(2, labels=["needs-human"]), ticket(3, status="merged"), ticket(4, state="closed")])
        for number, reason in ((1, "not-claimable"), (2, "flagged"), (3, "not-claimable"), (4, "closed"), (9, "not-found")):
            with self.assertRaises(pilot.Refused) as caught:
                m.claim("build", number, "fresh")
            self.assertEqual(caught.exception.payload["reason"], reason)

    def test_a_lost_race_is_reported(self):
        m, gh = machine([ticket(1)])
        gh.after_patch = lambda g: g.store[1].update(assignees=[{"login": "other"}])
        with self.assertRaises(pilot.Refused) as caught:
            m.claim("build", 1, "fresh")
        self.assertEqual(caught.exception.payload["reason"], "lost-race")

    def test_resume_modes(self):
        m, gh = machine([ticket(1, status="building", assignees=["x"]), ticket(2, status="building", assignees=["x"], labels=["can-resume"])])
        self.assertTrue(m.claim("build", 1, "resume-orphaned")["claimed"])
        self.assertEqual(gh.store[1]["assignees"], [{"login": "bot"}])
        out = m.claim("build", 2, "resume-cleared")
        self.assertNotIn("can-resume", out["labels"])
        self.assertEqual(gh.store[2]["assignees"], [{"login": "x"}])  # already claimed: only the signal is consumed


class SetTests(unittest.TestCase):
    def test_status_swap_unassign_and_close(self):
        m, gh = machine([ticket(1, status="building", assignees=["x"])])
        out = m.set(1, "reviewing", "none", close=True)
        self.assertEqual((out["status"], out["assignees"], out["state"]), ("status:reviewing", [], "closed"))
        self.assertNotIn("warning", out)

    def test_unknown_status_and_unexpected_transitions(self):
        m, _ = machine([ticket(1)])
        with self.assertRaises(pilot.Refused):
            m.set(1, "dev-ready")
        self.assertEqual(m.set(1, "done")["warning"]["code"], "unexpected-transition")

    def test_assignees_are_left_alone_unless_asked(self):
        m, gh = machine([ticket(1, assignees=["x"])])
        m.set(1, "building")
        self.assertEqual(gh.store[1]["assignees"], [{"login": "x"}])


class FlagTests(unittest.TestCase):
    def test_a_flag_never_exists_without_its_comment(self):
        m, gh = machine([ticket(1)])
        with self.assertRaises(pilot.Refused):
            m.flag(1, "  ")
        m.flag(1, "why and what is needed")
        self.assertEqual([c[0] for c in gh.calls], ["comment", "patch"])  # comment first
        self.assertIn("needs-human", names(gh.store[1]))
        m.unflag(1, "answered")
        self.assertNotIn("needs-human", names(gh.store[1]))


class RunTests(unittest.TestCase):
    def start(self, workflow="need", **kw):
        m, gh = machine([])
        return m, gh, m.run_start(workflow, **kw)

    def test_a_run_without_a_ticket_gets_its_own_issue_and_one_json_comment(self):
        m, gh, out = self.start(title="search")
        n = out["run"]
        self.assertIn("run:need", names(gh.store[n]))
        self.assertEqual(gh.store[n]["assignees"], [{"login": "bot"}])
        self.assertEqual(out["step"]["id"], "start")
        shown = m.run_show(n)
        self.assertEqual((shown["state"], shown["current"]["id"]), ("running", "start"))

    def test_a_second_run_on_a_ticket_in_progress_is_refused(self):
        m, gh = machine([ticket(1)])
        m.run_start("plan", 1)
        with self.assertRaises(pilot.Refused) as caught:
            m.run_start("plan", 1)
        self.assertEqual(caught.exception.payload["reason"], "run-in-progress")

    def advance_to(self, m, n, target, results):
        for r in results:
            out = m.run_advance(n, r)
        self.assertEqual(m.run_show(n)["step"], target)
        return out

    def test_ok_skip_and_loop_follow_the_data(self):
        m, gh, out = self.start()
        n = out["run"]
        self.advance_to(m, n, "challenge", ["ok", "ok"])
        out = m.run_advance(n, "loop")  # a human revised the need: back to the audit
        self.assertEqual(out["step"]["id"], "audit")
        self.advance_to(m, n, "write", ["ok", "skip"])

    def test_a_failing_validator_returns_twice_then_opens_the_gate(self):
        m, gh, out = self.start()
        n = out["run"]
        self.advance_to(m, n, "validate", ["ok", "ok", "skip", "skip", "skip"])
        for expected in (1, 2):
            out = m.run_advance(n, "fail")
            self.assertEqual((out["step"]["id"], out["loops"]["validate"]), ("write", expected))
            m.run_advance(n, "ok")
            m.run_advance(n, "skip")  # the question step, not opened
        out = m.run_advance(n, "fail")
        self.assertEqual(out["step"]["id"], "gate")
        self.assertEqual(out["state"], "running")

    def test_without_a_gate_the_escalation_waits_for_a_human(self):
        m, gh = machine([ticket(1)])
        n = m.run_start("build", 1)["run"]
        self.advance_to(m, n, "validate", ["ok", "ok", "skip"])
        for _ in range(2):
            m.run_advance(n, "fail")
            m.run_advance(n, "ok")
            m.run_advance(n, "skip")
        out = m.run_advance(n, "fail")
        self.assertEqual(out["state"], "waiting-human")
        self.assertEqual(out["escalated"]["from"], "validate")
        self.assertNotIn("step", out)

    def test_a_gate_sends_the_work_where_its_label_says(self):
        m, gh, out = self.start()
        n = out["run"]
        self.advance_to(m, n, "gate", ["ok", "ok", "skip", "skip", "skip", "ok", "ok", "ok"])
        self.assertEqual(m.run_advance(n, "reject:formulation")["step"]["id"], "write")
        self.advance_to(m, n, "gate", ["ok", "skip", "ok", "ok", "ok"])
        self.assertEqual(m.run_advance(n, "reject:fond")["step"]["id"], "start")
        with self.assertRaises(pilot.Refused):
            m.run_advance(n, "reject:nonsense")

    def test_the_executant_picks_the_alternative_and_skips_the_other(self):
        for executant, expected in (("human", "run-human"), ("ai", "run-ai")):
            m, gh = machine([ticket(1, status="merged")])
            n = m.run_start("accept", 1, data={"executant": executant})["run"]
            for _ in range(3):
                m.run_advance(n, "ok")  # eligibility, plan, checks of the plan
            self.assertEqual(m.run_advance(n, "ok")["step"]["id"], expected)
            self.assertEqual(m.run_advance(n, "ok")["step"]["id"], "dossier")  # the other alternative is skipped

    def test_an_end_closes_a_run_issue_but_not_a_ticket(self):
        m, gh, out = self.start()
        n = out["run"]
        m.run_end(n, "ok")
        self.assertEqual(gh.store[n]["state"], "closed")
        m2, gh2 = machine([ticket(1, status="merged")])
        t = m2.run_start("accept", 1)["run"]
        m2.run_end(t, "ok", {"version": "1"})
        self.assertEqual(gh2.store[1]["state"], "open")
        self.assertEqual(m2.run_show(1)["record"], {"version": "1"})
        with self.assertRaises(pilot.Refused):
            m2.run_advance(1, "ok")

    def test_resume_is_refused_while_a_human_question_is_open(self):
        m, gh = machine([ticket(1, labels=["needs-human"])])
        gh.store[1]["labels"]
        m.run_start("plan", 1)
        with self.assertRaises(pilot.Refused) as caught:
            m.run_resume(1)
        self.assertEqual(caught.exception.payload["reason"], "needs-human")
        gh.store[1]["labels"] = [l for l in gh.store[1]["labels"] if l["name"] != "needs-human"]
        self.assertEqual(m.run_resume(1)["state"], "running")

    def test_an_assumption_and_data_are_kept(self):
        m, gh, out = self.start()
        n = out["run"]
        m.run_note(n, assumption="default: 3 words max", data={"executant": "ai"})
        shown = m.run_show(n)
        self.assertEqual(shown["assumptions"], ["default: 3 words max"])
        self.assertEqual(shown["data"]["executant"], "ai")


class TicketTests(unittest.TestCase):
    def test_a_ticket_is_created_at_a_status_its_level_has_and_linked_under_its_parent(self):
        m, gh = machine([issue(1, ["level:epic", "status:forming"])])
        out = m.ticket_create("story", "feature", "Filter", "Entries: search-filter", "forming", parent=1, priority="P1", labels=["express"])
        self.assertEqual(set(out["labels"]), {"level:story", "type:feature", "status:forming", "priority:P1", "express"})
        self.assertEqual(gh.subs[1], [out["issue"]])
        self.assertEqual(out["event"]["action"], "created")
        for level, status in (("task", "forming"), ("epic", "ready")):
            with self.assertRaises(pilot.Refused):
                m.ticket_create(level, "tech", "x", "", status)

    def test_a_merged_pr_moves_its_ticket_and_derives_the_parent(self):
        m, gh = machine([ticket(1, status="planned"), ticket(2, status="reviewing", level="task"), ticket(3, status="merged", level="task"),
                         ticket(4, status="ready")], subs={1: [2, 3]})
        gh.store[2]["parent_issue_url"] = "https://api.github.com/repos/o/r/issues/1"
        out = m.ticket_merged(2)
        self.assertEqual((out["status"], out["parent"]["status"]), ("status:merged", "status:merged"))
        self.assertEqual(m.ticket_merged(2)["status"], "status:merged")  # idempotent
        with self.assertRaises(pilot.Refused):
            m.ticket_merged(4)

    def test_the_two_human_closings(self):
        m, gh = machine([ticket(1, status="forming"), ticket(2, status="to-plan"), ticket(3, status="ready")])
        self.assertEqual(m.ticket_close_forming(1)["status"], "status:to-plan")
        self.assertEqual(m.ticket_close_forming(2, drop=True)["state"], "closed")
        for number, drop in ((2, False), (3, True)):
            with self.assertRaises(pilot.Refused):
                m.ticket_close_forming(number, drop=drop)

    def test_a_split_story_follows_its_tasks_and_an_epic_its_stories(self):
        m, gh = machine([ticket(1, status="planned"), ticket(2, status="ready", level="task"), ticket(3, status="ready", level="task")],
                        subs={1: [2, 3]})
        self.assertFalse(m.derive(1)["changed"])
        gh.store[2]["labels"] = [{"name": "status:building"}, {"name": "level:task"}]
        self.assertEqual(m.derive(1)["status"], "status:building")
        for n in (2, 3):
            gh.store[n]["labels"] = [{"name": "status:merged"}, {"name": "level:task"}]
        self.assertEqual(m.derive(1)["status"], "status:merged")
        m2, gh2 = machine([issue(1, ["level:epic", "status:planned"]), ticket(2, status="done", state="closed")], subs={1: [2]})
        self.assertEqual(m2.derive(1)["status"], "status:done")
        self.assertEqual(gh2.store[1]["state"], "closed")


class PullRequestTests(unittest.TestCase):
    def machine(self, runs):
        m, gh = machine([])
        gh.get_pull = lambda n: {"number": n, "head": {"sha": "abc"}}
        gh.check_runs = lambda sha: runs
        gh.create_pull = lambda title, body, head, base: {"number": 7, "html_url": "u", "head": {"sha": "abc"}}
        gh.merge_pull = lambda n, method: {"merged": True, "sha": "def"}
        return m

    def test_the_ci_verdict_is_green_pending_or_red(self):
        done = {"name": "t", "status": "completed", "conclusion": "success"}
        self.assertEqual(self.machine([]).pr_ci(7)["ci"], "green")  # a docs-only PR runs no check
        self.assertEqual(self.machine([done]).pr_ci(7)["ci"], "green")
        self.assertEqual(self.machine([done, {"name": "b", "status": "in_progress", "conclusion": None}]).pr_ci(7)["ci"], "pending")
        red = self.machine([done, {"name": "b", "status": "completed", "conclusion": "failure"}]).pr_ci(7)
        self.assertEqual((red["ci"], red["failed"]), ("red", ["b"]))

    def test_a_pr_is_merged_only_on_green(self):
        self.assertTrue(self.machine([]).pr_merge(7)["merged"])
        with self.assertRaises(pilot.Refused) as caught:
            self.machine([{"name": "b", "status": "queued", "conclusion": None}]).pr_merge(7)
        self.assertEqual(caught.exception.payload["reason"], "ci-not-green")
        self.assertEqual(self.machine([]).pr_open("br", "t", "b")["pr"], 7)


class ConfigTests(unittest.TestCase):
    def test_a_dotted_key_is_written_without_touching_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".pilot", "state.json")
            pilot.config_set("language", "fr", path)
            pilot.config_set("commands.test", "npm test", path)
            self.assertEqual(pilot.config_value("commands.test", path), "npm test")
            self.assertEqual(pilot.config_value("language", path), "fr")
            for key in ("nope", "commands.deploy"):
                with self.assertRaises(pilot.Refused):
                    pilot.config_set(key, "x", path)


class LabelMigrationTests(unittest.TestCase):
    def test_v5_labels_become_v6_labels_and_the_rest_is_reported(self):
        m, gh = machine([issue(1, ["status:dev-ready", "type:feature", "level:story"]), issue(2, ["status:in-review", "type:bug", "level:task"]),
                         issue(3, ["level:epic", "type:feature"]), issue(4, ["type:poc", "status:poc-review"]), issue(5, ["status:ready", "type:tech"])])
        dry = m.migrate_labels()
        by = {c["issue"]: c for c in dry["changes"]}
        self.assertEqual(by[1]["add"], ["status:ready"])
        self.assertEqual((by[2]["add"], by[2]["remove"]), (["fix", "status:reviewing", "type:tech"], ["status:in-review", "type:bug"]))
        self.assertEqual(by[3]["add"], ["status:planned"])
        self.assertNotIn(5, by)  # already v6
        self.assertEqual(sorted(dry["unmapped"][0]["labels"]), ["status:poc-review", "type:poc"])
        self.assertIn("status:dev-ready", names(gh.store[1]))  # a dry run writes nothing
        m.migrate_labels(apply=True)
        self.assertEqual(names(gh.store[1]), ["level:story", "status:ready", "type:feature"])


class LabelsTests(unittest.TestCase):
    def test_sync_creates_the_missing_labels_and_patches_the_others(self):
        m, gh = machine([])
        created, patched = [], []
        gh.label_names = lambda: {"needs-human"}
        gh.upsert_label = lambda name, color, description, exists: (patched if exists else created).append(name)
        out = m.sync_labels()
        self.assertEqual(patched, ["needs-human"])
        self.assertEqual(out["labels"], len(created) + 1)
        self.assertIn("run:need", created)
        self.assertEqual(len(pilot.required_labels(m.wfs)), len(pilot.LABELS) + 11)

    def test_every_status_has_a_label_and_no_old_one_remains(self):
        for status in pilot.STATUSES:
            self.assertIn(f"status:{status}", pilot.LABELS)
        self.assertFalse([l for l in pilot.LABELS if l in ("type:bug", "type:e2e", "type:poc", "status:in-dev", "status:qa")])


class DoctorTests(unittest.TestCase):
    def report(self, **attrs):
        m, gh = machine([])
        for key, value in attrs.items():
            setattr(gh, key, value)
        return m.doctor(modules={})

    def test_all_good(self):
        got = self.report()
        self.assertTrue(got["ok"], got)

    def test_missing_labels_and_read_only_access_are_reported(self):
        got = self.report(labels=pilot.required_labels() - {"status:ready", "needs-human"})
        self.assertEqual([c["name"] for c in got["failed"]], ["pilot-labels"])
        self.assertIn("2 missing", got["failed"][0]["detail"])
        self.assertEqual([c["name"] for c in self.report(perms={"push": False})["failed"]], ["repo-write-permission"])


class DashboardPayloadTests(unittest.TestCase):
    def test_events_carry_the_ticket_state_and_the_parent(self):
        m, gh = machine([ticket(1), ticket(2, level="task")], subs={1: [2]})
        events = m.events([2], "created", "plan")["events"]
        self.assertEqual((events[0]["n"], events[0]["action"], events[0]["phase"]), (2, "created", "plan"))
        run = m.run_start("plan", 1)["event"]
        self.assertEqual((run["kind"], run["workflow"], run["step"]), ("run", "plan", "eligibility"))
        self.assertNotIn("result", run)
        self.assertEqual(m.run_end(1, "accepted")["event"]["result"], "accepted")

    def test_the_dashboard_routes_a_status_by_the_contracts(self):
        """The template's CONTRACTS table is what `pilot.py contract` prints for the workflows that take a ticket status."""
        page = (pathlib.Path(__file__).resolve().parent.parent / "assets" / "templates" / "pilot-dashboard.html.tmpl").read_text(encoding="utf-8")
        table = json.loads(re.search(r"var CONTRACTS=(\{.*\});", page).group(1))
        m, _gh = machine([])
        self.assertEqual(set(table), {"need", "plan", "build", "accept"})
        for wf, row in table.items():
            got = pilot.workflow_contract(m.wfs, wf)
            self.assertEqual((set(row["c"]), row["k"], set(row["p"])), (set(got["consumes"]), got["claims"], set(got["produces"])), wf)


class JudgeTests(unittest.TestCase):
    def passes(self, answers):
        return [[{"q": i, "answer": a, "quote": "x"} for i, a in enumerate(row)] for row in answers]

    def test_two_agreeing_passes_with_quotes_pass(self):
        wfs = pilot.load_workflows()
        out = pilot.judge_check(wfs, "build.judge", self.passes([["no", "no", "yes"], ["no", "no", "yes"]]))
        self.assertTrue(out["passed"], out)

    def test_a_failing_answer_is_listed_by_its_polarity(self):
        wfs = pilot.load_workflows()
        out = pilot.judge_check(wfs, "build.judge", self.passes([["yes", "no", "yes"], ["yes", "no", "yes"]]))
        self.assertTrue(out["ok"])
        self.assertEqual([f["q"] for f in out["failing"]], [0])
        self.assertFalse(out["passed"])

    def test_disagreement_a_missing_quote_and_a_bad_answer_are_problems(self):
        wfs = pilot.load_workflows()
        rows = self.passes([["no", "no", "yes"], ["yes", "no", "yes"]])
        rows[1][1]["quote"] = ""
        rows[0][2]["answer"] = "maybe"
        codes = {p["code"] for p in pilot.judge_check(wfs, "build.judge", rows)["problems"]}
        self.assertEqual(codes, {"passes-disagree", "no-quote", "answer-not-yes-or-no"})

    def test_a_question_that_applies_only_sometimes_may_stay_unanswered(self):
        wfs = pilot.load_workflows()
        n = len(next(s for s in wfs["need"]["steps"] if s.get("judge") == "need.judge")["questions"])
        row = [{"q": i, "answer": "no", "quote": "x"} for i in range(4)]  # the last two are conditional
        self.assertTrue(pilot.judge_check(wfs, "need.judge", [row, row])["ok"])
        self.assertEqual(n, 6)
        with self.assertRaises(pilot.Refused):
            pilot.judge_check(wfs, "need.judge", [row])
        with self.assertRaises(pilot.Refused):
            pilot.judge_check(wfs, "nope", [row, row])


NEED = """---
type: Behavior
title: Filter
description: d
pilot:
  status: proposed
  scope: [search]
  tickets: []
---

## Need
- S1 | text: The user filters results by access.

## Criteria
- C1 | when: I tick the filter | then: I see only step-free places | by: e2e | source: S1
"""


class ChecksTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = self.dir.name
        os.makedirs(os.path.join(self.root, "wiki"))
        with open(os.path.join(self.root, "wiki", "vocabulary.md"), "w") as handle:
            handle.write("## Terms\n- search | meaning: finding places\n- export | meaning: leaving\n")

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text if isinstance(text, str) else json.dumps(text))
        return rel

    def run_check(self, cid, **args):
        ctx = pilot_checks.Ctx({k: v for k, v in args.items()}, self.root)
        ctx.previous = lambda key, ref="origin/main": None
        return [p["code"] for p in pilot_checks.CHECKS[cid](ctx)]

    def test_a_well_formed_need_entry_passes_and_its_faults_are_named(self):
        self.write("wiki/search/f.md", NEED)
        self.assertEqual(self.run_check("need.check", entry="wiki/search/f.md"), [])
        bad = NEED.replace("by: e2e | source: S1", "by: maybe | source: S9").replace("scope: [search]", "scope: [nowhere]") + "- C2 | when: quickly\n"
        self.write("wiki/search/g.md", bad)
        codes = self.run_check("need.check", entry="wiki/search/g.md")
        self.assertTrue({"not-in-enum", "unknown-ref", "unknown-scope", "missing-field"} <= set(codes), codes)

    def test_ambiguous_words_are_found_in_a_text_field(self):
        self.write("wiki/search/f.md", NEED.replace("see only step-free places", "quickly see step-free places"))
        self.assertIn("ambiguous-word", self.run_check("need.check", entry="wiki/search/f.md"))

    def test_the_journal_is_append_only_and_a_change_needs_a_line(self):
        old = pilot_checks.parse_document(NEED + "\n## Journal\n- J1 | date: 2026-01-01 | origin: a | decision: b | discarded: c | reason: d\n")
        same = NEED + "\n## Journal\n- J1 | date: 2026-01-01 | origin: a | decision: b | discarded: c | reason: d\n"
        self.assertEqual(pilot_checks.journal_problems(pilot_checks.parse_document(same), old), [])
        rewritten = same.replace("decision: b", "decision: z")
        self.assertEqual(pilot_checks.journal_problems(pilot_checks.parse_document(rewritten), old)[0]["code"], "journal-rewritten")
        changed = same.replace("then: I see only", "then: I see just")
        self.assertEqual(pilot_checks.journal_problems(pilot_checks.parse_document(changed), old)[0]["code"], "journal-line-missing")

    def test_a_proto_parcours_without_a_criterion_is_not_covered(self):
        self.write("wiki/search/f.md", NEED + "")
        self.assertEqual(self.run_check("need.check", entry="wiki/search/f.md", parcours="p1"), ["parcours-not-covered"])
        self.write("wiki/search/h.md", NEED.replace("source: S1", "source: S1 | flow: p1"))
        self.assertEqual(self.run_check("need.check", entry="wiki/search/h.md", parcours="p1"), [])

    def test_a_plan_places_every_criterion_once_without_a_cycle(self):
        self.write("wiki/search/f.md", NEED)
        entries = "wiki/search/f.md"
        plan = {"tickets": [{"id": "T1", "title": "a", "level": "story", "criteria": ["f#C1"], "scope": ["search"]}]}
        adr = "---\npilot:\n  status: proposed\n  scope: [search]\n---\n\n## Decisions\n- D1 | decision: use a filter | covers: f#C1 | reason: simplest\n"
        self.write("architecture/adr/0001-x.md", adr)
        self.write("p.json", plan)
        ok = dict(plan="p.json", entries=entries, adrs="architecture/adr/0001-x.md", orientation="none")
        self.assertEqual(self.run_check("plan.check", **ok), [])
        plan["tickets"].append({"id": "T2", "title": "b", "level": "task", "criteria": ["f#C1"], "scope": ["search"], "depends": ["T3"]})
        plan["tickets"].append({"id": "T3", "title": "c", "level": "task", "criteria": [], "scope": ["search"], "depends": ["T2"]})
        self.write("p.json", plan)
        codes = set(self.run_check("plan.check", **ok))
        self.assertTrue({"criterion-in-several-tickets", "dependency-cycle", "task-without-verifiable-criterion"} <= codes, codes)
        self.assertEqual(self.run_check("plan.check", **{**ok, "orientation": ""})[-1], "orientation-missing")

    def test_a_task_over_the_threshold_and_a_needless_split(self):
        self.write("wiki/search/f.md", NEED)
        plan = {"tickets": [{"id": "T1", "title": "a", "level": "task", "criteria": ["f#C1"], "scope": ["search"]}]}
        adr = "---\npilot:\n  status: proposed\n  scope: [search]\n---\n\n## Decisions\n- D1 | decision: x | covers: f#C1 | reason: y\n"
        self.write("architecture/adr/0001-x.md", adr)
        self.write("p.json", plan)
        self.write("s.json", {"T1": 50})
        base = dict(plan="p.json", entries="wiki/search/f.md", adrs="architecture/adr/0001-x.md", orientation="none", sizes="s.json")
        self.assertIn("split-not-needed", self.run_check("plan.check", threshold="100", **base))
        self.assertIn("task-too-large", self.run_check("plan.check", threshold="10", **base))

    def test_build_checks_read_the_projects_results(self):
        good = {"tests_ok": True, "rules_ok": True, "hypotheses_declared": True, "diff_paths": ["web/a.js"], "scope_globs": ["web/*"],
                "criteria": ["f#C1"], "test_refs": {"f#C1": ["t.js"]}}
        self.write("r.json", good)
        self.assertEqual(self.run_check("build.check", results="r.json"), [])
        self.write("r.json", {**good, "tests_ok": False, "diff_paths": ["api/x.py"], "test_refs": {}})
        self.assertEqual(sorted(self.run_check("build.check", results="r.json")), ["criterion-without-test", "outside-scope", "tests-failing"])
        self.write("e.json", {"e2e_ok": True, "criteria_e2e": ["f#C1"], "e2e_refs": {}})
        self.assertEqual(self.run_check("build.check-2", results="e.json"), ["criterion-without-e2e"])

    def test_the_review_decision_lists_blocking_defects_by_class(self):
        self.write("rv.json", [{"persona": "pm", "verdict": "changes", "defects": [{"class": "criterion", "blocking": True, "text": "x"},
                                                                                    {"class": "code", "blocking": False, "text": "y"}]}])
        self.assertEqual(self.run_check("build.decision", reviews="rv.json"), ["blocking-defect"])

    def test_contrast_and_states_in_a_design_entry(self):
        entry = ("---\npilot:\n  scope: [search]\n---\n\n## Tokens\n- color.text | light: #000000 | dark: #ffffff | on: color.bg\n"
                 "- color.bg | light: #ffffff | dark: #000000\n- color.soft | light: #cccccc | dark: #333333 | on: color.bg\n"
                 "\n## Components\n- Button | category: action | states: default,hover | tokens: color.text,color.nope\n")
        self.write("d.md", entry)
        codes = self.run_check("design-system.check", entry="d.md")
        self.assertIn("contrast-below-aa", codes)
        self.assertIn("states-missing", codes)
        self.assertIn("unknown-token", codes)
        self.assertAlmostEqual(pilot_checks.contrast("#000", "#fff"), 21.0, 1)

    def test_a_proto_must_be_self_contained_and_rendered(self):
        self.write("p.html", '<meta name="viewport" content="width=device-width"><div data-parcours="p1">x</div>')
        self.write("rd.json", {"tap_ok": True, "contrast_ok": True, "keyboard_ok": True})
        self.assertEqual(self.run_check("proto.check", html="p.html", parcours="p1", render="rd.json"), [])
        self.write("p.html", '<img src="https://x.test/a.png"><div>x</div>')
        codes = self.run_check("proto.check", html="p.html", parcours="p1")
        self.assertTrue({"not-self-contained", "no-viewport", "parcours-without-screen", "not-rendered"} <= set(codes), codes)

    def test_a_report_form_and_its_qualification(self):
        form = {"steps": ["open", "tick"], "expected": "a", "observed": "b", "seen": "1.2.0", "felt": "major"}
        self.write("f.json", form)
        self.assertEqual(self.run_check("report.check", form="f.json"), [])
        self.write("f.json", {**form, "steps": [], "felt": "huge"})
        self.assertTrue({"too-few", "not-in-enum"} <= set(self.run_check("report.check", form="f.json")))
        self.write("q.json", {"kind": "gap", "cites": ["f#C9"], "severity": "major", "scope": ["search"]})
        self.write("k.json", ["f#C1"])
        self.assertEqual(self.run_check("report.check-2", qualification="q.json", known_ids="k.json"), ["cited-id-unknown"])

    def test_the_recipe_plan_and_record(self):
        plan = {"target": "s1", "cases": [{"id": "K1", "source": "f#C1", "expected": "x"}]}
        self.write("pl.json", plan)
        self.write("cr.json", ["f#C1", "f#C2"])
        self.assertEqual(self.run_check("accept.check", plan="pl.json", criteria="cr.json"), ["criterion-without-case"])
        record = {"target": "s1", "version": "1", "executant": "ai", "ref_hash": "h", "results": [{"case": "K1", "result": "ok"}]}
        self.write("rc.json", record)
        self.assertEqual(self.run_check("accept.dossier", record="rc.json", plan="pl.json"), ["result-without-proof"])
        self.write("rc.json", {**record, "results": [{"case": "K1", "result": "ok", "proof": "shot.png"}]})
        self.assertEqual(self.run_check("accept.dossier", record="rc.json", plan="pl.json"), [])

    def test_an_express_may_not_touch_a_frame(self):
        self.write("wiki/search/f.md", NEED.replace("status: proposed", "status: provisional"))
        self.write("ch.json", ["architecture/guidelines/x.md"])
        codes = self.run_check("express.check", entry="wiki/search/f.md", changed_paths="ch.json")
        self.assertEqual(codes, ["frame-modified"])

    def test_a_frame_may_not_overlap_an_accepted_entry_without_replacing_it(self):
        text = ("---\npilot:\n  scope: [search]\n---\n\n## Source\n- S1 | text: from the human\n\n## Statements\n- E1 | says: filters exist | source: S1 | by: judgment\n")
        self.write("wiki/search/fr.md", text)
        accepted = '[{"id": "old", "scope": ["search"]}]'
        self.assertEqual(self.run_check("functional-frame.check", entry="wiki/search/fr.md", accepted=accepted), ["overlaps-accepted"])
        self.write("wiki/search/fr.md", text.replace("pilot:", "replaces: [old]\npilot:"))
        self.assertEqual(self.run_check("functional-frame.check", entry="wiki/search/fr.md", accepted=accepted), [])

    def test_every_check_a_workflow_names_is_implemented_or_an_action(self):
        wfs = pilot.load_workflows()
        for wid, wf in wfs.items():
            for step in wf["steps"]:
                if step.get("check") and not step.get("action"):
                    self.assertIn(step["check"], pilot.CHECKS, (wid, step["id"]))

    def test_info_problems_do_not_fail_a_check(self):
        self.write("p.html", '<meta name="viewport" content="x"><div data-parcours="p1" style="color:#123456">x</div>')
        self.write("rd.json", {"tap_ok": True, "contrast_ok": True, "keyboard_ok": True})
        self.write("t.md", "## Tokens\n- color.a | light: #ffffff | dark: #000000\n")
        self.assertEqual(self.run_check("proto.check", html="p.html", parcours="p1", render="rd.json", tokens="t.md"), ["outside-design-system"])


class FormatsTests(unittest.TestCase):
    def test_every_format_is_well_formed(self):
        for fid, fmt in pilot_checks.formats()["formats"].items():
            self.assertTrue("sections" in fmt or "json" in fmt, fid)
            for name, spec in fmt.get("sections", {}).items():
                self.assertTrue(spec["id"] and spec["fields"], (fid, name))
                re.compile(spec["id"])

    def test_a_json_format_is_checked_by_type_required_enum_and_pattern(self):
        schema = pilot_checks.formats()["formats"]["plan"]["json"]
        self.assertEqual(pilot_checks.validate_json({"tickets": []}, schema)[0]["code"], "too-few")
        bad = {"tickets": [{"id": "x", "title": "", "level": "epic", "criteria": ["nope"], "scope": []}]}
        self.assertTrue({"bad-pattern", "not-in-enum", "empty"} <= {p["code"] for p in pilot_checks.validate_json(bad, schema)})

    def test_the_document_parser_reads_sections_and_lines(self):
        doc = pilot_checks.parse_document(NEED)
        self.assertEqual(doc["sections"]["Criteria"][0]["fields"]["by"], "e2e")
        self.assertEqual(pilot_checks.front_value(doc["front"], "pilot.scope"), "[search]")

    def test_there_is_no_cycle_in_a_chain_and_there_is_one_in_a_loop(self):
        self.assertFalse(pilot_checks.has_cycle({"a": ["b"], "b": []}))
        self.assertTrue(pilot_checks.has_cycle({"a": ["b"], "b": ["a"]}))
