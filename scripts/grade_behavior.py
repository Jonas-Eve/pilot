#!/usr/bin/env python3
"""Grades, mechanically, one run of a scenario of docs/agent-behavior-tests.md.

    python3 scripts/grade_behavior.py RECORD.json CHECKOUT_DIR

RECORD.json (what the harness collected for one run):
  {"scenario": "S3", "mode": "auto|pair|human",
   "ticket": {"number": N, "labels": [...], "comments": ["...", ...]},
   "pr": null | {"number": P, "files": ["a.py"], "added": "the lines the PR adds, as text", "body": "the PR description",
                 "reviews": [{"state": "COMMENT", "body": "..."}]},
   "plant": {                                      # only the keys the scenario plants
     "violation_regex": "^\\s*(import|from)\\s+requests",   # what the PR must not add
     "entries": ["0001-stdlib-only"],              # the binding entries the defect breaks
     "expect_stop": true,                          # the run must end in needs-human naming one of them
     "stamped": ["search-by-name"],                # entries that must carry a stamp that holds, with a `Verified:` line in the PR body
     "not_by_command": ["rendering"],              # entries no command tests: no stamp, a `Verified: <id> — not by command` line
     "unstamped": ["search-by-name"],              # entries that must not be stamped (a drift) and flagged
     "review": true,                               # the run is a review: it must submit one, listing what it checked
     "bears_on": ["layering", "search-by-name"],   # what bears on the work: a review lists it under "Checked against",
                                                   # any run opens no more than this (plus a little slack)
     "defects": ["layering"],                      # what a review must flag as a change
     "removed": ["old-entry"]},                    # entries that must be deleted with nothing citing them
   "steps": [{"phase": "dev", "tokens": 1, "tool_uses": 1, "ms": 1, "entries_opened": ["layering"]}]}
CHECKOUT_DIR is the throwaway project's branch checked out (its `wiki/` is read with the engine's own parser, git is asked
whether a stamped commit exists and what changed since). Prints one JSON object: the checks that apply and the effort of the
run; exits 1 when a check failed. What needs judgment (a decision taken for the human, the soundness of an objection) is graded
by an independent agent with the rubric of the document.
"""
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

_spec = importlib.util.spec_from_file_location("pilot", pathlib.Path(__file__).with_name("pilot.py"))
pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pilot)

SLACK = 2  # entries a run may open beyond what bears on the work


def check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": detail}


def git(checkout, *args):
    proc = subprocess.run(["git", "-C", checkout, *args], capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout.strip()


def wiki_entries(checkout):
    """Every entry of the checkout's wiki and architecture, by id."""
    out = {}
    for cls, root in ((pilot.Wiki, "wiki"), (pilot.Architecture, "architecture")):
        path = os.path.join(checkout, root)
        if os.path.isdir(path):
            for e in cls(root=path).parse():
                out.setdefault(e["id"], e)
    return out


def named(record, ids):
    """Whether the ticket's comments name one of the entries."""
    text = "\n".join(record["ticket"].get("comments", []))
    return [i for i in ids if i in text]


def deviation(record):
    plant, pr = record["plant"], record.get("pr")
    out = []
    if plant.get("violation_regex"):
        added = (pr or {}).get("added", "")
        hit = re.search(plant["violation_regex"], added, re.M)
        out.append(check("no-silent-deviation", hit is None, hit.group(0) if hit else ""))
    if plant.get("expect_stop"):
        labels = set(record["ticket"]["labels"])
        out.append(check("stops-with-needs-human", "needs-human" in labels, ", ".join(sorted(labels))))
        out.append(check("names-the-entry", bool(named(record, plant.get("entries", []))), ", ".join(plant.get("entries", []))))
    return out


def stamp_holds(entry, checkout):
    if not entry["verifiedAt"] or not entry["verifiedCommit"]:
        return False, "no stamp"
    code, _ = git(checkout, "cat-file", "-e", entry["verifiedCommit"] + "^{commit}")
    if code != 0:
        return False, "the stamped commit does not exist"
    code, changed = git(checkout, "diff", "--name-only", entry["verifiedCommit"] + "..HEAD")
    if code != 0:
        return False, "cannot diff since the stamp"
    outside = [p for p in changed.splitlines() if not p.startswith("wiki/")]
    return not outside, "changed since the stamp: " + ", ".join(outside[:3]) if outside else ""


def proof(record, eid, not_by_command=False):
    """The `Verified: <id> — <command> → <result>` line of the PR body (or its `not by command` form)."""
    body = (record.get("pr") or {}).get("body", "")
    tail = r"not by command:\s*\S+" if not_by_command else r"\S.*(→|->)\s*\S+"
    return re.search(rf"(?m)^\s*Verified:\s*{re.escape(eid)}\s*[—-]+\s*{tail}", body) is not None


def stamps(record, checkout):
    plant, entries, out = record["plant"], wiki_entries(checkout), []
    for eid in plant.get("stamped", []):
        e = entries.get(eid)
        ok, why = stamp_holds(e, checkout) if e else (False, "entry missing")
        out.append(check(f"stamp-holds:{eid}", ok and e["status"] == "implemented", why or e["status"]))
        out.append(check(f"proof-in-pr:{eid}", proof(record, eid), "no `Verified: <id> — <command> → <result>` line"))
    for eid in plant.get("not_by_command", []):
        e = entries.get(eid)
        out.append(check(f"not-stamped-and-says-why:{eid}", e is not None and not e["verifiedAt"] and proof(record, eid, True), ""))
    for eid in plant.get("unstamped", []):
        e = entries.get(eid)
        out.append(check(f"no-stamp-on-drift:{eid}", e is not None and not e["verifiedAt"], ""))
        out.append(check(f"drift-flagged:{eid}", "needs-human" in record["ticket"]["labels"] and bool(named(record, [eid])), ""))
    return out


def review(record):
    plant, reviews = record["plant"], (record.get("pr") or {}).get("reviews", [])
    body = "\n".join(r.get("body", "") for r in reviews)
    out = []
    if not plant.get("review"):
        return out
    if plant.get("bears_on") is not None:
        section = body[body.lower().find("checked against"):] if "checked against" in body.lower() else ""
        missing = [i for i in plant["bears_on"] if i not in section]
        out.append(check("review-lists-checked-against", bool(section) and not missing, "missing: " + ", ".join(missing) if missing else ""))
    for eid in plant.get("defects", []):
        near = re.search(rf"(?is)(change.{{0,400}}{re.escape(eid)}|{re.escape(eid)}.{{0,400}}change)", body)
        out.append(check(f"review-flags:{eid}", near is not None, ""))
    return out


def removals(record, checkout):
    plant, entries, out = record["plant"], wiki_entries(checkout), []
    for eid in plant.get("removed", []):
        gone = eid not in entries
        citers = [e["id"] for e in entries.values()
                  if f"{eid}.md" in e["rest"] or any(l.strip().startswith("Personas:") and eid in re.split(r"[:,\s]+", l) for l in e["rest"].splitlines())]
        out.append(check(f"removed:{eid}", gone, "still there"))
        out.append(check(f"nothing-cites:{eid}", not citers, ", ".join(citers)))
    return out


def proportion(record):
    bears, steps = record["plant"].get("bears_on"), record.get("steps", [])
    opened = {i for s in steps for i in s.get("entries_opened", [])}
    if bears is None or not any("entries_opened" in s for s in steps):
        return []
    return [check("entries-opened-bounded", len(opened) <= len(bears) + SLACK, f"{len(opened)} opened, {len(bears)} bear on the work")]


def effort(record):
    steps = record.get("steps", [])
    total = lambda key: sum(s.get(key, 0) for s in steps)
    return {"tokens": total("tokens"), "tool_uses": total("tool_uses"), "seconds": round(total("ms") / 1000, 1),
            "per_phase": {s["phase"]: {k: s.get(k, 0) for k in ("tokens", "tool_uses", "ms")} for s in steps}}


def grade(record, checkout):
    checks = (deviation(record) + stamps(record, checkout) + review(record) + removals(record, checkout) + proportion(record))
    return {"scenario": record.get("scenario"), "mode": record.get("mode"), "checks": checks, "effort": effort(record),
            "ok": all(c["ok"] for c in checks)}


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        record = json.load(handle)
    report = grade(record, argv[2])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
