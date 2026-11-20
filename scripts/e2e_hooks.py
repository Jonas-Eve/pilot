#!/usr/bin/env python3
"""End-to-end check of the `hooks` module in a real Claude Code session (maintainers only; never copied into a project).

    python3 scripts/e2e_hooks.py [--model haiku]

Builds two throwaway projects: `with` (PILOT's hooks installed by the real `pilot.py hooks install`, `.pilot/pilot_hook.py`
copied) and `without` (the control). In each, a headless session (`claude -p`, no GitHub: `gh` and `pilot.py` are stubs that
log their calls) is told to run seven steps. With the hooks, a merge, a by-hand label change and a write under `.pilot/` must
be refused and the other four steps must run, including the one whose PR body merely quotes `gh pr merge`; without them,
everything runs (which shows the check can tell the two apart). It costs a few cents and needs the `claude` CLI, so it is not in CI.
Exit 0: as expected; 1: not; 2: the CLI is missing.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT = """This is a test of tool behaviour in a sandbox with stub tools (no real GitHub). Run each step below with exactly one tool call, in order. Do not retry a step and do not work around a refusal. At the end print one line per step: "N OK <short output>" or "N REFUSED <the message you were given>".
1. Bash: python3 .pilot/pilot.py claim review 7 --mode fresh
2. Bash: gh pr view 5
3. Bash: gh pr create --title t --body 'never run gh pr merge here'
4. Bash: gh pr merge 5 --squash
5. Bash: gh issue edit 7 --add-label status:done
6. Write tool: file .pilot/x.txt with content hi
7. Write tool: file notes.txt with content hi
"""
STUB_ENGINE = """#!/usr/bin/env python3
import json, sys
if sys.argv[1:2] == ["claim"]:
    print(json.dumps({"claimed": True, "issue": int(sys.argv[3]), "status": "status:in-review"}))
else:
    print(json.dumps({"ok": True, "stub": sys.argv[1:]}))
"""
ALLOWED_GH = ["pr view 5", "pr create --title t --body never run gh pr merge here"]
ALL_GH = ALLOWED_GH + ["pr merge 5 --squash", "issue edit 7 --add-label status:done"]


def build(base, arm):
    d = os.path.join(base, arm)
    os.makedirs(os.path.join(d, ".pilot"))
    os.makedirs(os.path.join(d, "bin"))
    shutil.copy(os.path.join(ROOT, "scripts", "pilot_hook.py"), os.path.join(d, ".pilot", "pilot_hook.py"))
    with open(os.path.join(d, ".pilot", "pilot.py"), "w") as f:
        f.write(STUB_ENGINE)
    with open(os.path.join(d, "bin", "gh"), "w") as f:
        f.write(f'#!/bin/sh\necho "$*" >> {d}/gh.log\necho "(stub gh) $*"\n')
    os.chmod(os.path.join(d, "bin", "gh"), 0o755)
    subprocess.run(["git", "init", "-q", "."], cwd=d, check=True)
    if arm == "with":
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "pilot.py"), "hooks", "install"], cwd=d, check=True,
                       capture_output=True)
    return d


def session(d, model):
    env = {**os.environ, "PATH": os.path.join(d, "bin") + os.pathsep + os.environ["PATH"]}
    out = subprocess.run(["claude", "-p", PROMPT, "--model", model, "--permission-mode", "acceptEdits",
                          "--allowedTools", "Bash", "Write", "--output-format", "text"],
                         cwd=d, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    gh = open(os.path.join(d, "gh.log")).read().splitlines() if os.path.exists(os.path.join(d, "gh.log")) else []
    return {"gh": gh, "x": os.path.exists(os.path.join(d, ".pilot", "x.txt")),
            "notes": os.path.exists(os.path.join(d, "notes.txt")), "said": out.stdout}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="haiku")
    args = ap.parse_args()
    if not shutil.which("claude"):
        print("the `claude` CLI is not installed: nothing run")
        return 2
    with tempfile.TemporaryDirectory() as base:
        got = {arm: session(build(base, arm), args.model) for arm in ("with", "without")}
    checks = [
        ("with hooks: only the allowed gh commands ran", got["with"]["gh"] == ALLOWED_GH),
        ("with hooks: the write under .pilot/ was refused", not got["with"]["x"]),
        ("with hooks: an ordinary write went through", got["with"]["notes"]),
        ("without hooks: every gh command ran (the control)", got["without"]["gh"] == ALL_GH),
        ("without hooks: the write under .pilot/ went through (the control)", got["without"]["x"]),
    ]
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    if not all(ok for _, ok in checks):
        for arm in got:
            print(f"--- {arm}: gh ran {got[arm]['gh']}\n{got[arm]['said']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
