#!/usr/bin/env python3
"""A laboratory for the prompts of PILOT: one model call per trial, the facts given, a decision graded mechanically.

    python3 scripts/lab.py run --base REV --cand REV|WORKTREE [--cases L-S3,L-S4 | --select] [--n 10] [--model sonnet]
                               [--arms base,cand|cand] [--workers 4] [--max-cost 3.00] [--out DIR]
    python3 scripts/lab.py plan --base REV --cand REV|WORKTREE [--cases ...] [--n 10]   # what is already kept, what would run, what it would cost
    python3 scripts/lab.py report DIR
    python3 scripts/lab.py regrade DIR                         # the saved answers graded again with the current checks, no model call
    python3 scripts/lab.py show CASE --arm REV|WORKTREE        # the assembled prompt, to read it

A case (`scripts/lab/cases/<id>.json`) names a persona, the docs a skill passes into that persona's call, the situation (what the
agent has already read) and a question, with a JSON schema for the answer and declarative checks on it. A trial assembles the
prompt exactly as the skill would from the files **at a git revision** (`git show REV:path`, or the working tree), calls the model
headless (`claude -p`, no tools, no repository, the persona's identity as the system prompt, the answer forced into the schema)
and grades the structured answer. Nothing needs an API key: the Claude Code CLI is the backend, and it reports each call's cost.

Per case and arm it prints, for each check, the passing share with a 95 % Wilson interval, and between the two arms the
difference with a Newcombe interval and a plain verdict (worse / better / no detectable difference: with ten trials only a large
change is detectable). `--select` keeps the cases whose scenario depends on a file that changed between the two revisions
(scripts/select_scenarios.py). `--max-cost` stops the run when the calls made now have cost that much.

Answers are kept in `scripts/lab/results/<case>/<model>/<fingerprint>.json`, the fingerprint being a hash of what the model reads
(persona, docs, situation, question, schema) and the model: a case whose prompt did not change is read back, not asked again, and only the
missing samples are run; two arms with the same prompt share their answers. The checks are applied on every run, so a corrected rubric
costs no call, and a judged result is reused while rubric and answer are unchanged. `--refresh` asks again.
"""
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CASES = os.path.join(HERE, "lab", "cases")
WORKTREE = "WORKTREE"


# ---- cases and prompts ------------------------------------------------------------------------------------------
def load_case(case_id):
    with open(os.path.join(CASES, case_id + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def all_cases():
    return [load_case(n[:-5]) for n in sorted(os.listdir(CASES)) if n.endswith(".json")]


def read_at(repo, rev, path):
    """A file at a git revision, or from the working tree; None when it does not exist there."""
    if rev == WORKTREE:
        full = os.path.join(repo, path)
        if not os.path.exists(full):
            return None
        with open(full, encoding="utf-8") as handle:
            return handle.read()
    proc = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True, text=True, timeout=60)
    return proc.stdout if proc.returncode == 0 else None


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def assemble(case, repo, rev):
    """(system prompt, user prompt): the persona's identity, then what the skill injects, then the situation."""
    if case.get("system"):  # no persona: the orchestrating session itself (a skill's own steps)
        persona = case["system"]
    else:
        persona = read_at(repo, rev, f".claude/agents/{case['persona']}.md")
        if persona is None:
            raise SystemExit(f"{case['persona']} does not exist at {rev}")
    parts, missing = [], []
    for path in case["docs"]:
        body = read_at(repo, rev, path)
        if body is None:
            missing.append(path)
        else:
            parts.append(f"## {path.replace('assets/docs/', '.pilot/')}\n\n{body.strip()}")
    user = ("# Your duty and the documents your caller passes you\n\n" + "\n\n".join(parts)
            + "\n\n# The situation\n\n" + case["situation"].strip() + "\n\n# What you decide now\n\n" + case["question"].strip()
            + "\n\nYou have no tools here: everything you need is above. Answer only through the structured output.")
    return strip_frontmatter(persona).strip(), user, missing


# ---- the model --------------------------------------------------------------------------------------------------
def call_claude(system, user, schema, model, timeout=300):
    """One headless call: no tools, no repository, one turn. Returns the answer and what it cost."""
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "", "--system-prompt", system,
           "--max-turns", "1", "--no-session-persistence", "--json-schema", json.dumps(schema)]
    with tempfile.TemporaryDirectory() as cwd:  # no CLAUDE.md, no project settings to leak into the prompt
        proc = subprocess.run(cmd, input=user, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return {"output": None, "cost": 0.0, "error": (proc.stderr or proc.stdout)[:300]}
    usage = data.get("usage") or {}
    return {"output": data.get("structured_output"), "cost": float(data.get("total_cost_usd") or 0), "ms": data.get("duration_ms", 0),
            "tokens": {k: usage.get(k, 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")},
            "error": data.get("result") if data.get("is_error") else None}


# ---- checks -----------------------------------------------------------------------------------------------------
def dig(value, path):
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def text_of(value):
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value


def matches(item, want):
    return isinstance(item, dict) and all(item.get(k) == v for k, v in want.items())


def run_check(check, output):
    """One declarative check on the structured answer: equals, contains, regex, any, all_of."""
    if check.get("not"):
        return not run_check({k: v for k, v in check.items() if k != "not"}, output)
    value = (output if check["path"] == "$" else dig(output, check["path"])) if output is not None else None
    if "equals" in check:
        return value == check["equals"]
    if "in" in check:
        return value in check["in"]
    if "contains" in check:
        return check["contains"].lower() in text_of(value).lower()
    if "regex" in check:
        return re.search(check["regex"], text_of(value) if value is not None else "", re.I | re.S) is not None
    if "order" in check:  # each pattern matches some item, and the first matches come in the order given
        items = [text_of(i) for i in value] if isinstance(value, list) else []
        last = -1
        for pattern in check["order"]:
            hits = [n for n, item in enumerate(items) if re.search(pattern, item, re.I | re.S)]
            if not hits or hits[0] <= last:
                return False
            last = hits[0]
        return True
    if "sequence" in check:  # matchers on an item's `step` and/or `action`; their first matches come in this order
        items = value if isinstance(value, list) else []
        last = -1
        for m in check["sequence"]:
            hits = [n for n, i in enumerate(items) if isinstance(i, dict)
                    and (not m.get("step") or re.search(m["step"], str(i.get("step", "")), re.I))
                    and (not m.get("action") or re.search(m["action"], str(i.get("action", "")), re.I | re.S))]
            if not hits or hits[0] < last:  # two matchers may land on one item: a plan often merges two steps into a line
                return False
            last = hits[0]
        return True
    if "any" in check:
        return isinstance(value, list) and any(matches(i, check["any"]) for i in value)
    if "all_of" in check:
        return isinstance(value, list) and all(any(matches(i, w) for i in value) for w in check["all_of"])
    raise ValueError("unknown check " + json.dumps(check))


def call_judge(case, output, criterion, model="haiku", backend=call_claude):
    """A small model decides one question of meaning about the answer, where a pattern cannot. Returns (pass, cost, reason)."""
    system = "You are a strict grader of one criterion. Answer only through the structured output."
    user = (f"The agent was asked:\n{case['question']}\n\nIts answer (JSON):\n{json.dumps(output, ensure_ascii=False)}\n\n"
            f"Criterion: {criterion}\n\nSet pass to true only when the criterion is met by what the answer actually says.")
    schema = {"type": "object", "properties": {"pass": {"type": "boolean"}, "reason": {"type": "string"}}, "required": ["pass", "reason"]}
    result = backend(system, user, schema, model)
    verdict_ = result.get("output") or {}
    return bool(verdict_.get("pass")), float(result.get("cost") or 0), str(verdict_.get("reason") or "")


def grade(case, output, judge=None):
    """Every check of the case on one answer; a `judge` check is put to `judge(case, output, check) -> (pass, cost, reason)`."""
    graded = {}
    for c in case["checks"]:
        if "judge" in c:
            graded[c["name"]] = bool(output is not None and judge is not None and judge(case, output, c)[0])
        else:
            graded[c["name"]] = bool(run_check(c, output))
    return graded


# ---- statistics -------------------------------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe(k1, n1, k2, n2):
    """The 95 % interval of p2 - p1 (the candidate minus the base)."""
    if n1 == 0 or n2 == 0:
        return (-1.0, 1.0)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    return (p2 - p1 - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), p2 - p1 + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2))


def verdict(low, high):
    return "worse" if high < 0 else "better" if low > 0 else "no detectable difference"


def summarize(trials, arms):
    """trials: dicts with case, arm, checks, cost, tokens. -> per case, per arm: n, cost, per check rate and interval; and the arms' difference."""
    out = {}
    for t in trials:
        cell = out.setdefault(t["case"], {}).setdefault(t["arm"], {"n": 0, "errors": 0, "cost": 0.0, "cached": 0, "checks": {}})
        cell["cost"] += t.get("cost", 0)
        cell["cached"] += 1 if t.get("cached") else 0
        if t.get("error") or t.get("output") is None:
            cell["errors"] += 1
            continue
        cell["n"] += 1
        for name, ok in t["checks"].items():
            cell["checks"][name] = cell["checks"].get(name, 0) + (1 if ok else 0)
    report = {}
    for case, by_arm in out.items():
        rows = {}
        for arm, cell in by_arm.items():
            rows[arm] = {"n": cell["n"], "errors": cell["errors"], "cached": cell["cached"], "cost_usd": round(cell["cost"], 4),
                         "cost_per_trial": round(cell["cost"] / max(1, cell["n"] + cell["errors"]), 4),
                         "checks": {name: {"passed": k, "rate": round(k / cell["n"], 3) if cell["n"] else None,
                                           "ci95": [round(x, 3) for x in wilson(k, cell["n"])]} for name, k in sorted(cell["checks"].items())}}
        diff = {}
        if len(arms) == 2 and all(a in by_arm for a in arms):
            b, c = by_arm[arms[0]], by_arm[arms[1]]
            for name in sorted(set(b["checks"]) | set(c["checks"])):
                low, high = newcombe(b["checks"].get(name, 0), b["n"], c["checks"].get(name, 0), c["n"])
                diff[name] = {"candidate_minus_base": round((c["checks"].get(name, 0) / c["n"] if c["n"] else 0) - (b["checks"].get(name, 0) / b["n"] if b["n"] else 0), 3),
                              "ci95": [round(low, 3), round(high, 3)], "verdict": verdict(low, high)}
        report[case] = {"arms": rows, "difference": diff}
    return report


# ---- a run ------------------------------------------------------------------------------------------------------
def fingerprint(system, user, schema, model):
    """What the model's answer depends on: the prompt, the schema and the model. Same fingerprint, same answers worth keeping."""
    h = hashlib.sha256()
    for part in (system, user, json.dumps(schema, sort_keys=True), model):
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def judge_key(check, output):
    """A judged result is reusable while the rubric and the answer are the same."""
    return hashlib.sha256((check["judge"] + "\0" + json.dumps(output, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()[:16]


def cache_file(results, case_id, model, fp):
    return os.path.join(results, case_id, model, fp + ".json")


def load_cache(results, case_id, model, fp):
    try:
        with open(cache_file(results, case_id, model, fp), encoding="utf-8") as handle:
            return json.load(handle)["trials"]
    except (OSError, ValueError, KeyError):
        return []


def save_cache(results, case_id, model, fp, trials):
    path = cache_file(results, case_id, model, fp)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"case": case_id, "model": model, "fingerprint": fp, "trials": trials}, handle, indent=1, ensure_ascii=False)
        handle.write("\n")


def run_trials(cases, revs, n, model, repo, workers, max_cost, backend=call_claude, judge_model="haiku", results=None, refresh=False):
    """Answers for every (case, arm), n each. With a `results` directory the raw answers are kept by fingerprint of the prompt: an arm
    whose prompt did not change is read back, not asked again; only the missing samples are run (the first of each prompt first, alone
    with its siblings, because it writes the prompt cache the others read); arms with the same prompt share their answers. The checks
    are applied afterwards, so a corrected rubric costs no model call, and a judged result is reused while rubric and answer are unchanged.
    Returns (trials, new spend): the spend counts only calls made now, and stops new calls once max_cost is reached."""
    prompts = {(c["id"], arm): assemble(c, repo, rev) for c in cases for arm, rev in revs.items()}
    fps = {key: fingerprint(system, user, next(c for c in cases if c["id"] == key[0])["schema"], model) for key, (system, user, _m) in prompts.items()}
    cases_by_id = {c["id"]: c for c in cases}
    stored = {}
    for (cid, arm), fp in fps.items():
        if (cid, fp) not in stored:
            stored[(cid, fp)] = [] if (results is None or refresh) else load_cache(results, cid, model, fp)
    jobs = []
    for (cid, fp), have in stored.items():
        arm = next(a for (c, a), f in fps.items() if c == cid and f == fp)
        jobs += [(cases_by_id[cid], arm, fp, i) for i in range(len(have), n)]
    before = {key: len(have) for key, have in stored.items()}
    errors = []
    spent = [0.0]

    def one(job):
        c, arm, fp, i = job
        system, user, _ = prompts[(c["id"], arm)]
        result = backend(system, user, c["schema"], model)
        return job, result

    def phase(pending):
        pending, running = list(pending), set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            while pending or running:
                while pending and len(running) < workers and (max_cost is None or spent[0] < max_cost):
                    running.add(pool.submit(one, pending.pop(0)))
                if not running:
                    break
                done, running = concurrent.futures.wait(running, return_when=concurrent.futures.FIRST_COMPLETED)
                for f in done:
                    job, result = f.result()
                    spent[0] += float(result.get("cost") or 0)
                    if result.get("output") is not None:
                        stored[(job[0]["id"], job[2])].append({"output": result["output"], "cost": float(result.get("cost") or 0), "tokens": result.get("tokens", {}),
                                                              "ms": result.get("ms", 0), "judged": {}})
                    else:  # an error is reported, not kept: it is asked again next time
                        errors.append((job[0]["id"], job[2], float(result.get("cost") or 0), str(result.get("error") or "no answer")))
                if max_cost is not None and spent[0] >= max_cost:
                    pending = []

    first = {}
    for j in jobs:
        first.setdefault((j[0]["id"], j[2]), j)
    phase(list(first.values()))
    done_first = set(id(x) for x in first.values())
    phase([j for j in jobs if id(j) not in done_first])
    # the checks, applied now; a judged check not yet judged for this rubric and answer is put to the judge
    todo = []
    for (cid, fp), have in stored.items():
        for t in have[:n]:
            for check in cases_by_id[cid]["checks"]:
                if "judge" in check and judge_key(check, t["output"]) not in t["judged"]:
                    todo.append((cases_by_id[cid], check, t))

    def judge_one(item):
        case, check, t = item
        ok, cost, reason = call_judge(case, t["output"], check["judge"], judge_model, backend)
        return item, ok, cost, reason
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for (case, check, t), ok, cost, reason in pool.map(judge_one, todo):
            t["judged"][judge_key(check, t["output"])] = {"pass": ok, "cost": cost, "reason": reason}
            spent[0] += cost
    if results is not None:
        for (cid, fp), have in stored.items():
            if have:
                save_cache(results, cid, model, fp, have)
    out = []
    new_counts = {}
    for (cid, arm), fp in fps.items():
        for i, t in enumerate(stored[(cid, fp)][:n]):
            case = cases_by_id[cid]
            graded, reasons, cost = {}, {}, t["cost"]
            for check in case["checks"]:
                if "judge" in check:
                    j = t["judged"][judge_key(check, t["output"])]
                    graded[check["name"]], reasons[check["name"]] = j["pass"], j["reason"]
                    cost += j["cost"]
                else:
                    graded[check["name"]] = bool(run_check(check, t["output"]))
            out.append({"case": cid, "arm": arm, "sample": i, "checks": graded, "judged": reasons, "output": t["output"], "cost": cost,
                        "tokens": t.get("tokens", {}), "ms": t.get("ms", 0), "cached": i < before[(cid, fp)]})
        out += [{"case": cid, "arm": arm, "sample": -1, "checks": {}, "output": None, "error": e, "cost": c, "cached": False} for (ecid, efp, c, e) in errors if (ecid, efp) == (cid, fp)]
    return out, spent[0]


def select_cases(cases, repo, base, cand):
    """The cases whose scenario depends on a file that changed between the two revisions."""
    spec = importlib.util.spec_from_file_location("select_scenarios", os.path.join(HERE, "select_scenarios.py"))
    sel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sel)
    if cand == WORKTREE:
        proc = subprocess.run(["git", "-C", repo, "diff", "--name-only", base], capture_output=True, text=True, timeout=60)
        changed = [l for l in proc.stdout.splitlines() if l]
    else:
        changed = sel.changed_files(repo, base, cand)
    chosen = set(sel.select(repo, changed)["selected"])
    return [c for c in cases if c.get("scenario") in chosen]


def regrade(case_index, data):
    """The saved trials graded again with the cases' current checks: no model call. A judged check keeps its saved result."""
    trials = []
    for t in data["trials"]:
        case = case_index.get(t["case"])
        if case is None or t.get("output") is None:
            trials.append(t)
            continue
        old = t.get("checks", {})
        graded = {}
        for c in case["checks"]:
            graded[c["name"]] = bool(old.get(c["name"], False)) if "judge" in c else bool(run_check(c, t["output"]))
        trials.append({**t, "checks": graded})
    return trials


def print_report(report):
    for case, data in report.items():
        print(f"\n== {case}")
        for arm, row in data["arms"].items():
            print(f"  {arm}: n={row['n']} ({row['cached']} read from the cache) errors={row['errors']} cost={row['cost_usd']}$ ({row['cost_per_trial']}$/trial)")
            for name, c in row["checks"].items():
                print(f"     {name}: {c['passed']}/{row['n']} = {c['rate']}  95% [{c['ci95'][0]}, {c['ci95'][1]}]")
        for name, d in data["difference"].items():
            print(f"  candidate - base, {name}: {d['candidate_minus_base']:+}  95% [{d['ci95'][0]}, {d['ci95'][1]}]  -> {d['verdict']}")


def main(argv):
    args = argv[1:]
    if not args or args[0] not in ("run", "report", "show", "regrade", "plan"):
        print(__doc__)
        return 2
    cmd, args, opt, rest = args[0], args[1:], {}, []
    while args:
        a = args.pop(0)
        if a == "--select":
            opt["select"] = True
        elif a in ("--refresh", "--no-cache"):
            opt["refresh"] = True
        elif a.startswith("--"):
            opt[a[2:]] = args.pop(0)
        else:
            rest.append(a)
    repo = ROOT
    if cmd == "report":
        with open(os.path.join(rest[0], "trials.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        print_report(summarize(data["trials"], data["arms"]))
        return 0
    if cmd == "regrade":
        path = os.path.join(rest[0], "trials.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        data["trials"] = regrade({c["id"]: c for c in all_cases()}, data)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1, ensure_ascii=False)
        print_report(summarize(data["trials"], data["arms"]))
        return 0
    if cmd == "show":
        system, user, missing = assemble(load_case(rest[0]), repo, opt.get("arm", WORKTREE))
        print("--- system ---\n" + system + "\n--- user ---\n" + user + (f"\n--- missing docs: {missing}" if missing else ""))
        return 0
    base, cand = opt.get("base"), opt.get("cand", WORKTREE)
    if not base:
        print(__doc__)
        return 2
    cases = [load_case(c) for c in opt["cases"].split(",")] if "cases" in opt else all_cases()
    if opt.get("select"):
        cases = select_cases(cases, repo, base, cand)
        print(f"selected by the diff: {[c['id'] for c in cases] or 'nothing'}", file=sys.stderr)
    if not cases:
        return 0
    arms = opt["arms"].split(",") if "arms" in opt else ["base", "cand"]
    model, n = opt.get("model", "sonnet"), int(opt.get("n", 10))
    revs = {a: {"base": base, "cand": cand}[a] for a in arms}
    results = opt.get("results", os.path.join(HERE, "lab", "results"))
    if cmd == "plan":
        total = 0
        for c in cases:
            seen = set()
            for arm, rev in revs.items():
                system, user, _m = assemble(c, repo, rev)
                fp = fingerprint(system, user, c["schema"], model)
                have = len(load_cache(results, c["id"], model, fp))
                note = "same prompt as another arm" if (c["id"], fp) in seen else ""
                missing = 0 if (c["id"], fp) in seen else max(0, n - have)
                seen.add((c["id"], fp))
                total += missing
                print(f"{c['id']:<16} {arm:<5} {fp}  cached {have:>2}  to run {missing:>2}  {note}")
        print(f"\n{total} calls to make, about {total * 0.03:.2f}$ on sonnet (0.0015$ per call on haiku)")
        return 0
    trials, spent = run_trials(cases, revs, n, model, repo, int(opt.get("workers", 4)), float(opt["max-cost"]) if "max-cost" in opt else None,
                               results=results, refresh=bool(opt.get("refresh")))
    out = opt.get("out")
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "trials.json"), "w", encoding="utf-8") as handle:
            json.dump({"base": base, "cand": cand, "model": opt.get("model", "sonnet"), "arms": arms, "trials": trials}, handle, indent=1, ensure_ascii=False)
    print_report(summarize(trials, arms))
    print(f"\ncost of the calls made now: {spent:.4f}$ ({sum(1 for t in trials if t.get('cached'))} of {len(trials)} trials read from the cache)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
