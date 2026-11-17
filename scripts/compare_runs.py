#!/usr/bin/env python3
"""Compares the graded runs of two versions, scenario by scenario (docs/agent-behavior-tests.md).

    python3 scripts/compare_runs.py BASE_DIR CANDIDATE_DIR [--cost-threshold 1.25]

Each directory holds the reports `scripts/grade_behavior.py` printed, one JSON file per run (three runs per scenario and per mode).
For every scenario present in both, it prints, per check, the share of runs that passed on the base and on the candidate, and the
median tokens of a run on each side. A **regression** is a check the candidate fails in more runs than the base by more than a third
of the runs (two of three: one failure is noise); a **cost alert** is a candidate whose median tokens exceed the base's by more than
the threshold (1.25 = 25 % more). Exits 1 when there is a regression or a cost alert.
"""
import glob
import json
import os
import statistics
import sys


def load(directory):
    reports = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
        if isinstance(report, dict) and "checks" in report:
            reports.append(report)
    return reports


def group(reports):
    out = {}
    for r in reports:
        out.setdefault((r.get("scenario"), r.get("mode")), []).append(r)
    return out


def rates(reports):
    seen = {}
    for r in reports:
        for c in r["checks"]:
            ok, n = seen.get(c["name"], (0, 0))
            seen[c["name"]] = (ok + (1 if c["ok"] else 0), n + 1)
    return {name: ok / n for name, (ok, n) in seen.items()}


def median_tokens(reports):
    values = [r.get("effort", {}).get("tokens", 0) for r in reports]
    return statistics.median(values) if values else 0


def compare(base, candidate, cost_threshold=1.25):
    b, c = group(base), group(candidate)
    rows, regressions, alerts = [], [], []
    for key in sorted(set(b) | set(c), key=lambda k: (str(k[0]), str(k[1]))):
        name = f"{key[0]}/{key[1]}"
        if key not in b or key not in c:
            rows.append({"scenario": name, "only_in": "candidate" if key in c else "base"})
            continue
        base_rates, cand_rates = rates(b[key]), rates(c[key])
        checks = {n: {"base": base_rates.get(n), "candidate": cand_rates.get(n)} for n in sorted(set(base_rates) | set(cand_rates))}
        for n, v in checks.items():
            if v["base"] is not None and v["candidate"] is not None and v["base"] - v["candidate"] > 1 / 3 + 1e-9:
                regressions.append(f"{name}: {n} passes {v['base']:.0%} of runs on the base, {v['candidate']:.0%} on the candidate")
        tb, tc = median_tokens(b[key]), median_tokens(c[key])
        ratio = round(tc / tb, 2) if tb else None
        if ratio is not None and ratio > cost_threshold:
            alerts.append(f"{name}: median tokens x{ratio} ({int(tb)} -> {int(tc)})")
        rows.append({"scenario": name, "runs": {"base": len(b[key]), "candidate": len(c[key])}, "checks": checks,
                     "median_tokens": {"base": tb, "candidate": tc, "ratio": ratio}})
    return {"scenarios": rows, "regressions": regressions, "cost_alerts": alerts, "ok": not regressions and not alerts}


def main(argv):
    args, threshold, dirs = argv[1:], 1.25, []
    while args:
        a = args.pop(0)
        if a == "--cost-threshold":
            threshold = float(args.pop(0))
        else:
            dirs.append(a)
    if len(dirs) != 2:
        print(__doc__)
        return 2
    report = compare(load(dirs[0]), load(dirs[1]), threshold)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
