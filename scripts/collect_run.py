#!/usr/bin/env python3
"""Builds the RECORD.json of one run for scripts/grade_behavior.py, from GitHub and the session's record.

    python3 scripts/collect_run.py SCENARIO --arm base|cand --run N --repo OWNER/REPO --session SESSION.json
                                   [--ticket N] [--pr M] [--out FILE]

SESSION.json is the session's record as `get_session` returns it (the `ccr` object or the whole reply): its usage and its
created/updated times give the effort of the run. The ticket's labels and comments, and the pull request's description, added
lines, files and reviews, are read with `gh api`. Prints the record (or writes it to `--out`).
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_seed  # noqa: E402


def session_object(data):
    """The `ccr` object, wherever the harness saved it from."""
    if isinstance(data, dict) and "ccr" in data:
        return data["ccr"]
    return data


def parse_time(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def effort_step(phase, session):
    usage = (session.get("external_metadata") or {}).get("usage") or {}
    tokens = sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"))
    ms = 0
    if session.get("created_at") and session.get("updated_at"):
        ms = int((parse_time(session["updated_at"]) - parse_time(session["created_at"])).total_seconds() * 1000)
    return {"phase": phase, "tokens": tokens, "cost_usd": float(usage.get("cost_usd") or 0), "ms": ms}


def label_names(labels):
    return sorted(l["name"] if isinstance(l, dict) else str(l) for l in labels or [])


def added_lines(files):
    out = []
    for f in files or []:
        for line in str(f.get("patch") or "").splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                out.append(line[1:])
    return "\n".join(out)


def build_record(scenario, arm, run, issue, comments, pr, pr_files, reviews, session):
    plant = dict(scenario.get("plant", {}))
    record = {"scenario": scenario["id"], "mode": scenario.get("mode"), "arm": arm, "run": run,
              "ticket": {"number": issue.get("number"), "labels": label_names(issue.get("labels")),
                         "comments": [c.get("body", "") for c in comments or []]},
              "pr": None, "plant": plant, "steps": [effort_step(scenario.get("phase", ""), session_object(session))]}
    if pr:
        record["pr"] = {"number": pr.get("number"), "body": pr.get("body") or "", "files": [f["filename"] for f in pr_files or []],
                        "added": added_lines(pr_files), "reviews": [{"state": r.get("state"), "body": r.get("body") or ""} for r in reviews or []]}
    return record


def gh_json(repo, path):
    proc = subprocess.run(["gh", "api", f"repos/{repo}/{path}"], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise SystemExit(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def main(argv):
    args, opt, rest = argv[1:], {}, []
    while args:
        a = args.pop(0)
        if a in ("--arm", "--run", "--repo", "--session", "--ticket", "--pr", "--out"):
            opt[a[2:]] = args.pop(0)
        else:
            rest.append(a)
    if len(rest) != 1 or opt.get("arm") not in ("base", "cand") or not {"run", "repo", "session"} <= set(opt):
        print(__doc__)
        return 2
    scenario = bench_seed.load_scenario(rest[0])
    with open(opt["session"], encoding="utf-8") as handle:
        session = json.load(handle)
    issue, comments = {}, []
    if "ticket" in opt:
        issue = gh_json(opt["repo"], f"issues/{opt['ticket']}")
        comments = gh_json(opt["repo"], f"issues/{opt['ticket']}/comments?per_page=100")
    pr = files = reviews = None
    if "pr" in opt:
        pr = gh_json(opt["repo"], f"pulls/{opt['pr']}")
        files = gh_json(opt["repo"], f"pulls/{opt['pr']}/files?per_page=100")
        reviews = gh_json(opt["repo"], f"pulls/{opt['pr']}/reviews?per_page=100")
    record = build_record(scenario, opt["arm"], int(opt["run"]), issue, comments, pr, files, reviews, session)
    text = json.dumps(record, indent=2, ensure_ascii=False)
    if "out" in opt:
        with open(opt["out"], "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
