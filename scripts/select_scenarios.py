#!/usr/bin/env python3
"""Picks the scenarios of docs/agent-behavior-tests.md that a change can have affected.

    python3 scripts/select_scenarios.py BASE CANDIDATE [--repo DIR] [--changed PATH ...]

BASE and CANDIDATE are git revisions (the version in use and the one to ship); `--changed` replaces the git diff. A scenario
depends on its skill's files: the SKILL.md, the docs it cites with `.pilot/pilot-*.md` (task docs, link docs, the process), the
personas it names, and the link docs those link docs cite — never the task docs a link doc mentions, which another skill
injects. Prints one JSON object:
  selected   the scenario ids to replay on BASE and on CANDIDATE, in manifest order
  reasons    for each, the changed files that selected it
  all        true when the engine (scripts/pilot.py) changed: every scenario is selected
  untested   changed prompt files no scenario covers: a change there is not checked at all
  unclassified  changed files that are neither a dependency, ignored, nor listed untested: the smoke set is selected for them
`scripts/behavior-scenarios.json` holds the scenarios, the smoke set, the engine files, what is ignored and what is untested.
"""
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys

PERSONAS = "pm|architect|techlead|dev|e2e|qa|designer"
PROMPT_GLOBS = (".claude/skills/*/SKILL.md", ".claude/agents/*.md", "assets/docs/*.md")


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as handle:
        return handle.read()


def doc_refs(root, rel):
    found = {"assets/docs/" + m.group(1) for m in re.finditer(r"\.pilot/(pilot-[a-z0-9-]+\.md)", read(root, rel))}
    return {p for p in found if os.path.exists(os.path.join(root, p))}


def persona_refs(root, rel):
    found = {f".claude/agents/pilot-{m.group(1)}.md" for m in re.finditer(rf"\bpilot-({PERSONAS})\b", read(root, rel))}
    return {p for p in found if os.path.exists(os.path.join(root, p))}


def closure(root, skill):
    """The files a scenario of `skill` depends on."""
    start = f".claude/skills/{skill}/SKILL.md"
    seen = {start} | doc_refs(root, start) | persona_refs(root, start)
    todo = [p for p in seen if os.path.basename(p).startswith("pilot-link-")]
    while todo:
        for ref in doc_refs(root, todo.pop()):
            if os.path.basename(ref).startswith("pilot-link-") and ref not in seen:
                seen.add(ref)
                todo.append(ref)
    return seen


def prompt_files(root):
    return sorted(p for g in PROMPT_GLOBS for p in (os.path.relpath(x, root) for x in glob.glob(os.path.join(root, g))))


def load_manifest(root):
    with open(os.path.join(root, "scripts", "behavior-scenarios.json"), encoding="utf-8") as handle:
        return json.load(handle)


def matches(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def select(root, changed, manifest=None):
    manifest = manifest or load_manifest(root)
    ids = [s["id"] for s in manifest["scenarios"]]
    deps = {s["id"]: closure(root, s["skill"]) for s in manifest["scenarios"]}
    reasons, untested, unclassified = {}, [], []
    everything = False
    for path in changed:
        if matches(path, manifest["engine"]):
            everything = True
            for sid in ids:
                reasons.setdefault(sid, []).append(path)
            continue
        hit = [sid for sid in ids if path in deps[sid]]
        for sid in hit:
            reasons.setdefault(sid, []).append(path)
        if hit or matches(path, manifest["ignored"]):
            continue
        if path in manifest["untested"]:
            untested.append(path)
        else:
            unclassified.append(path)  # a new or removed prompt file, or a file nobody classified
    for path in unclassified:
        for sid in manifest["smoke"]:
            reasons.setdefault(sid, []).append(path)
    return {"selected": [sid for sid in ids if sid in reasons], "reasons": {sid: sorted(set(reasons[sid])) for sid in ids if sid in reasons},
            "all": everything, "untested": sorted(untested), "unclassified": sorted(unclassified)}


def changed_files(root, base, candidate):
    proc = subprocess.run(["git", "-C", root, "diff", "--name-only", base, candidate], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "git diff failed")
    return [line for line in proc.stdout.splitlines() if line]


def main(argv):
    args, root, changed, mode = argv[1:], os.getcwd(), None, None
    revs = []
    while args:
        a = args.pop(0)
        if a == "--repo":
            root = args.pop(0)
        elif a == "--changed":
            changed = []
            while args and not args[0].startswith("--"):
                changed.append(args.pop(0))
        else:
            revs.append(a)
    if changed is None and len(revs) != 2:
        print(__doc__)
        return 2
    files = changed if changed is not None else changed_files(root, revs[0], revs[1])
    print(json.dumps({"base": revs[0] if revs else None, "candidate": revs[1] if len(revs) > 1 else None, "changed": files,
                      **select(root, files)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
