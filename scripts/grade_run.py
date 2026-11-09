#!/usr/bin/env python3
"""Grades one end-to-end run of the engine comparison (docs/engine-comparison.md), mechanically.

    python3 scripts/grade_run.py RECORD.json CHECKOUT_DIR

RECORD.json (what the harness collected for one run):
  {"arm": "old|engine", "rep": 1,
   "ticket": {"number": N, "state": "open", "labels": [...]},
   "pr": {"number": P, "title": "...", "body": "...", "merged": false, "commits": ["feat(cli): ..."],
          "files": ["accessplaces/cli.py"], "reviews": ["APPROVED"], "additions": 6, "deletions": 0},
   "transitions": ["status:in-spec", "status:dev-ready", ...],   # the ticket's status labels, in order
   "steps": [{"phase": "spec", "tokens": 1, "tool_uses": 1, "ms": 1}, ...]}
CHECKOUT_DIR is the PR branch checked out. Prints one JSON object: the engine's orchestration, the run's time and
tokens, the respect of the project's docs, and the mechanical part of the output quality. What needs judgment (spec,
code and review relevance) is graded by an independent agent with the rubric in docs/engine-comparison.md.
"""
import ast
import json
import os
import re
import subprocess
import sys

CHAIN = ["status:draft", "status:backlog", "status:in-spec", "status:dev-ready", "status:in-dev", "status:review-ready",
         "status:in-review", "status:approved"]  # the lean chain (no QA, no e2e)
CONVENTIONAL = re.compile(r"^(feat|fix|docs|refactor|test|style|chore|perf)(\([\w.-]+\))?!?: \S")
NETWORK = re.compile(r"\b(socket|urllib|requests|http\.client|httpx|aiohttp)\b")


def check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": detail}


def orchestration(record):
    ticket, pr = record["ticket"], record["pr"]
    statuses = [l for l in ticket["labels"] if l.startswith("status:")]
    seq = [s for s in record.get("transitions", []) if s in CHAIN]
    positions = [CHAIN.index(s) for s in seq]
    return [
        check("one-status-label", len(statuses) == 1, ", ".join(statuses)),
        check("ends-approved-with-the-pr-open", statuses == ["status:approved"] and not pr.get("merged") and ticket["state"] == "open",
              f"{statuses}, merged={pr.get('merged')}, state={ticket['state']}"),
        check("no-flag-left", not {"needs-human", "on-hold"} & set(ticket["labels"]), ""),
        check("statuses-in-chain-order", bool(seq) and positions == sorted(positions) and len(set(seq)) == len(seq), " > ".join(seq)),
        check("every-working-status-passed", {"status:in-dev", "status:review-ready", "status:in-review", "status:approved"} <= set(seq),
              " > ".join(seq)),
        check("pr-closes-the-ticket", re.search(rf"\bCloses #{ticket['number']}\b", pr.get("body", "")) is not None, ""),
        check("a-review-was-submitted", bool(pr.get("reviews")), str(pr.get("reviews"))),  # GitHub refuses to approve one's own PR: it lands as a COMMENTED review, the verdict is the ticket's label
    ]


def effort(record):
    steps = record.get("steps", [])
    total = lambda key: sum(s.get(key, 0) for s in steps)
    return {"tokens": total("tokens"), "tool_uses": total("tool_uses"), "seconds": round(total("ms") / 1000, 1),
            "per_phase": {s["phase"]: {k: s.get(k, 0) for k in ("tokens", "tool_uses", "ms")} for s in steps}}


def changed(record, checkout, suffix):
    return [p for p in record["pr"].get("files", []) if p.endswith(suffix) and os.path.exists(os.path.join(checkout, p))]


def docs(record, checkout):
    pr, out = record["pr"], []
    bad = []
    for path in changed(record, checkout, ".py"):  # architecture: stdlib-only and one-way layers
        tree = ast.parse(open(os.path.join(checkout, path), encoding="utf-8").read())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else [])
            bad += [f"{path}: {n}" for n in names if n.split(".")[0] not in sys.stdlib_module_names and n.split(".")[0] != "accessplaces"]
    out.append(check("stdlib-only", not bad, "; ".join(bad)))
    search = os.path.join(checkout, "accessplaces", "search.py")
    out.append(check("search-never-imports-cli", not os.path.exists(search) or not re.search(r"\bcli\b", " ".join(
        l for l in open(search, encoding="utf-8") if l.startswith(("import ", "from ")))), ""))
    tests = [p for p in changed(record, checkout, ".py") if p.startswith("tests/")]
    out.append(check("tests-offline", not any(NETWORK.search(open(os.path.join(checkout, p), encoding="utf-8").read()) for p in tests),
                     ", ".join(tests)))
    out.append(check("e2e-test-per-story", any(re.match(r"tests/test_e2e_.*\.py$", f) for f in pr.get("files", [])), "guideline tests-unit-and-e2e"))
    out.append(check("conventional-commits", bool(pr.get("commits")) and all(CONVENTIONAL.match(c) for c in pr["commits"]), "; ".join(pr.get("commits", []))))
    out.append(check("conventional-pr-title", bool(CONVENTIONAL.match(pr.get("title", ""))), pr.get("title", "")))
    out.append(check("pr-template-sections", all(h in pr.get("body", "") for h in ("## Summary", "## Test plan")), ""))
    out.append(check("docs-mention-the-change", any(p.endswith((".md",)) for p in pr.get("files", [])), "README/docs/wiki updated"))
    return out


def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def quality(record, checkout):
    pr = record["pr"]
    code, shown = run([sys.executable, "-m", "accessplaces", "--version"], checkout)
    tcode, tout = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], checkout)
    outside = [p for p in pr.get("files", []) if not p.startswith(("accessplaces/", "tests/", "docs/", "wiki/", "architecture/")) and p != "README.md"]
    return [
        check("version-flag-works", code == 0 and "accessplaces" in shown.lower(), shown[:80]),
        check("existing-behaviour-kept", run([sys.executable, "-m", "accessplaces", "--json", "x"], checkout)[0] == 0, ""),
        check("tests-pass", tcode == 0, tout.splitlines()[-1] if tout else ""),
        check("a-test-covers-it", any("version" in open(os.path.join(checkout, p), encoding="utf-8").read().lower()
                                      for p in changed(record, checkout, ".py") if p.startswith("tests/")), ""),
        check("small-diff", pr.get("additions", 0) + pr.get("deletions", 0) <= 80,
              f"{len(pr.get('files', []))} files, +{pr.get('additions', 0)} -{pr.get('deletions', 0)}"),
        check("nothing-outside-the-scope", not outside, ", ".join(outside)),
    ]


def main(argv):
    record = json.load(open(argv[1], encoding="utf-8"))
    checkout = argv[2]
    report = {"arm": record["arm"], "rep": record.get("rep"), "effort": effort(record),
              "orchestration": orchestration(record), "docs": docs(record, checkout), "quality": quality(record, checkout)}
    for section in ("orchestration", "docs", "quality"):
        passed = sum(c["ok"] for c in report[section])
        report[section + "_score"] = f"{passed}/{len(report[section])}"
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if all(c["ok"] for s in ("orchestration", "docs", "quality") for c in report[s]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
