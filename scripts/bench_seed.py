#!/usr/bin/env python3
"""Seeds, and resets, the throwaway project of docs/agent-behavior-tests.md (needs `gh` and `git`).

    python3 scripts/bench_seed.py seed SCENARIO --arm base|cand --run N --repo OWNER/REPO --dir CLONE [--dry-run]
    python3 scripts/bench_seed.py reset --repo OWNER/REPO --dir CLONE [--dry-run]

`seed` creates what one run of a scenario (`scripts/bench/scenarios/<id>.json`) starts from: the ticket, a run branch off the
arm's branch (`arm-base`, `arm-cand`) carrying the scenario's fixture files when it has any, and the pull request when the scenario
reviews one. It prints one JSON object: the ticket and PR numbers, the branch the session must start from (`source_revision`),
the branch its pull requests target, and the prompt to start the session with. `reset` closes every bench ticket and pull request
and deletes the `bench/` branches. `--dry-run` prints the commands instead of running them.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = os.path.join(HERE, "bench", "scenarios")


def load_scenario(scenario_id):
    with open(os.path.join(SCENARIOS, scenario_id + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def all_scenarios():
    return [load_scenario(n[:-5]) for n in sorted(os.listdir(SCENARIOS)) if n.endswith(".json")]


def render(text, **values):
    """Replaces `{key}` for the given keys only: the fixtures hold Python and YAML braces that must stay."""
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def names(scenario, arm, run):
    base = f"bench/{scenario['id']}-{arm}-r{run}"
    needs_branch = bool(scenario.get("fixtures") or scenario.get("pr"))
    return {"label": f"bench {scenario['id']} {arm} r{run}", "arm_branch": f"arm-{arm}",
            "run_branch": base if needs_branch else f"arm-{arm}", "pr_branch": base + "-pr"}


def ticket_payload(scenario, arm, run):
    spec = scenario.get("ticket")
    if not spec:
        return None
    label = names(scenario, arm, run)["label"]
    return {"title": render(spec["title"], run=label), "body": render(spec["body"], run=label), "labels": list(spec["labels"])}


def fixtures(scenario, ticket, base_sha):
    return {path: render(content, ticket=ticket, base_sha=base_sha) for path, content in scenario.get("fixtures", {}).items()}


def pr_payload(scenario, ticket, base_sha=""):
    spec = scenario.get("pr")
    if not spec:
        return None
    return {"title": spec["title"], "body": render(spec["body"], ticket=ticket),
            "files": {p: render(c, ticket=ticket, base_sha=base_sha) for p, c in spec["files"].items()}}


def session_prompt(scenario, ticket, pr, target):
    text = render(scenario["prompt"], ticket=ticket or "", pr=pr or "")
    return text + f"\n\nBench run: any pull request you open targets the branch `{target}`, never `main`."


class Runner:
    def __init__(self, cwd, repo, dry=False):
        self.cwd, self.repo, self.dry = cwd, repo, dry

    def run(self, cmd, stdin=None):
        if self.dry:
            print("+ " + " ".join(cmd), file=sys.stderr)
            return ""
        proc = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True, input=stdin, timeout=300)
        if proc.returncode != 0:
            raise SystemExit(f"{' '.join(cmd)} failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    def gh(self, *args, stdin=None):
        return self.run(["gh", "api", *args], stdin=stdin)

    def git(self, *args):
        return self.run(["git", "-c", "user.email=bench@example.invalid", "-c", "user.name=bench", *args])

    def write(self, files):
        for path, content in files.items():
            target = os.path.join(self.cwd, path)
            if not self.dry:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8") as handle:
                    handle.write(content)


def seed(scenario, arm, run, runner):
    n = names(scenario, arm, run)
    ticket = pr = None
    payload = ticket_payload(scenario, arm, run)
    if payload:
        args = ["-X", "POST", f"repos/{runner.repo}/issues", "-f", f"title={payload['title']}", "-f", f"body={payload['body']}"]
        for label in payload["labels"]:
            args += ["-f", f"labels[]={label}"]
        out = runner.gh(*args, "--jq", ".number")
        ticket = int(out) if out else 0
    base_sha = ""
    if n["run_branch"] != n["arm_branch"] or scenario.get("pr"):
        runner.git("fetch", "-q", "origin", n["arm_branch"])
        runner.git("checkout", "-q", "-B", n["run_branch"], "origin/" + n["arm_branch"])
        base_sha = runner.git("rev-parse", "HEAD")
        files = fixtures(scenario, ticket, base_sha)
        if files:
            runner.write(files)
            runner.git("add", "-A")
            runner.git("commit", "-q", "-m", f"bench: fixtures of {scenario['id']}")
        runner.git("-c", "push.negotiate=true", "push", "-q", "-u", "origin", n["run_branch"])
    spec = pr_payload(scenario, ticket, base_sha)
    if spec:
        runner.git("checkout", "-q", "-B", n["pr_branch"], n["run_branch"])
        runner.write(spec["files"])
        runner.git("add", "-A")
        runner.git("commit", "-q", "-m", spec["title"])
        runner.git("-c", "push.negotiate=true", "push", "-q", "-u", "origin", n["pr_branch"])
        out = runner.gh("-X", "POST", f"repos/{runner.repo}/pulls", "-f", f"title={spec['title']}", "-f", f"body={spec['body']}",
                        "-f", f"head={n['pr_branch']}", "-f", f"base={n['run_branch']}", "--jq", ".number")
        pr = int(out) if out else 0
        runner.git("checkout", "-q", n["run_branch"])
    return {"scenario": scenario["id"], "arm": arm, "run": run, "ticket": ticket, "pr": pr, "base_sha": base_sha,
            "source_revision": n["run_branch"], "pr_target": n["run_branch"], "prompt": session_prompt(scenario, ticket, pr, n["run_branch"])}


def reset(runner):
    closed = []
    page = runner.gh(f"repos/{runner.repo}/issues?state=open&per_page=100", "--jq",
                     '.[] | select(.pull_request == null) | select(.title | contains("(bench ")) | .number')
    for number in [int(x) for x in page.split()] if page else []:
        runner.gh("-X", "PATCH", f"repos/{runner.repo}/issues/{number}", "-f", "state=closed")
        closed.append(number)
    pulls = runner.gh(f"repos/{runner.repo}/pulls?state=open&per_page=100", "--jq", '.[] | select(.head.ref | startswith("bench/")) | .number')
    for number in [int(x) for x in pulls.split()] if pulls else []:
        runner.gh("-X", "PATCH", f"repos/{runner.repo}/pulls/{number}", "-f", "state=closed")
    refs = runner.gh(f"repos/{runner.repo}/git/matching-refs/heads/bench/", "--jq", ".[].ref")
    for ref in refs.split() if refs else []:
        runner.git("push", "origin", "--delete", ref.replace("refs/heads/", "", 1))
    return {"closed_tickets": closed}


def main(argv):
    args = argv[1:]
    if not args or args[0] not in ("seed", "reset"):
        print(__doc__)
        return 2
    cmd, args, opt, rest = args[0], args[1:], {}, []
    while args:
        a = args.pop(0)
        if a in ("--arm", "--run", "--repo", "--dir"):
            opt[a[2:]] = args.pop(0)
        elif a == "--dry-run":
            opt["dry"] = True
        else:
            rest.append(a)
    if "repo" not in opt or "dir" not in opt or (cmd == "seed" and (len(rest) != 1 or opt.get("arm") not in ("base", "cand") or "run" not in opt)):
        print(__doc__)
        return 2
    runner = Runner(opt["dir"], opt["repo"], opt.get("dry", False))
    result = seed(load_scenario(rest[0]), opt["arm"], int(opt["run"]), runner) if cmd == "seed" else reset(runner)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
