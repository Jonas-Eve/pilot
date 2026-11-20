#!/usr/bin/env python3
"""Claude Code hooks for working on this repo (maintainers of PILOT only; never copied into a project).

  repo_hook.py guard   PreToolUse on Edit|Write: refuse an edit of a PILOT-owned copy (`.pilot/`, the synced workflow)
  repo_hook.py lint    PostToolUse on Edit|Write: after an edit of a file the linter covers, run scripts/lint_pilot.py
                       and hand its errors back to the model
  repo_hook.py review-track  PostToolUse on Agent: a run of the maintainer review (docs/maintainer-review.md) that ended
                       with `VERDICT: PASS` is recorded for the diff it saw
  repo_hook.py pr-gate PreToolUse on create_pull_request / `gh pr create`: refuse while the diff touches what projects copy
                       and no passing review of that exact diff is recorded

Reads the hook payload on stdin. Exit 2 = feedback to the model (stderr); any internal failure exits 0, never blocks.
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OWNED = (".pilot/", ".github/workflows/pilot-status-on-merge.yml")
LINTED = (".claude/skills/", ".claude/agents/", "assets/docs/", "assets/templates/", "scripts/pilot.py", "CLAUDE.md")


REVIEWED = (".claude/skills/", ".claude/agents/", "assets/", "scripts/pilot.py", "scripts/setup-github-labels.sh",
            "CLAUDE.md", "README.md", "VERSION")  # what a PR must have had reviewed
REVIEW_DOC = "docs/maintainer-review.md"


def git(root, *args):
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr)
    return out.stdout


def review_scope(root):
    """(changed paths that need the review, a key of the exact diff) against the merge-base with origin/main, or None when
    there is nothing to review or git cannot say."""
    base = git(root, "merge-base", "HEAD", "origin/main").strip()
    tracked = git(root, "diff", "--name-only", base).split()
    untracked = git(root, "ls-files", "--others", "--exclude-standard").split()
    changed = sorted(f for f in set(tracked) | set(untracked) if f.startswith(REVIEWED))
    if not changed:
        return None
    digest = hashlib.sha256(git(root, "diff", base).encode())
    for name in sorted(untracked):
        digest.update(name.encode())
        try:
            digest.update((pathlib.Path(root) / name).read_bytes())
        except OSError:
            pass
    return changed, digest.hexdigest()


def engine(root):
    """scripts/pilot.py of this checkout, for its shell-command parser (one implementation of "is this command run")."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pilot_engine", ROOT / "scripts" / "pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def review_marker(session_id):
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
    return pathlib.Path(tempfile.gettempdir()) / f"pilot-maint-review-{safe}.json"


def review_track(payload, root=ROOT):
    """After the review agent ended on `VERDICT: PASS`, remember the diff it reviewed (the last verdict line wins)."""
    params = payload.get("tool_input") or {}
    if payload.get("tool_name") != "Agent" or REVIEW_DOC not in str(params.get("prompt", "")):
        return 0
    verdicts = re.findall(r"VERDICT:\s*(PASS|FINDINGS)", json.dumps(payload.get("tool_response", "")))
    scope = review_scope(root)
    if not verdicts or scope is None:
        return 0
    review_marker(payload.get("session_id")).write_text(json.dumps({"key": scope[1], "verdict": verdicts[-1]}))
    return 0


def pr_gate(payload, root=ROOT):
    tool, params = payload.get("tool_name"), payload.get("tool_input") or {}
    if not ((str(tool).startswith("mcp__") and str(tool).lower().endswith("__create_pull_request"))
            or (tool == "Bash" and engine(root).runs_command(str(params.get("command", "")), "gh", "pr", "create"))):
        return 0
    scope = review_scope(root)
    if scope is None:
        return 0
    try:
        marker = json.loads(review_marker(payload.get("session_id")).read_text())
    except (OSError, ValueError):
        marker = {}
    if marker.get("key") == scope[1] and marker.get("verdict") == "PASS":
        return 0
    print(f"This change touches what projects copy ({', '.join(scope[0][:4])}{'…' if len(scope[0]) > 4 else ''}). "
          f"Before opening the PR, run the maintainer review: spawn an agent whose prompt says to read {REVIEW_DOC} and "
          "review the diff against origin/main (see that document), fix every finding, and run it again. "
          "The PR opens once a review of this exact diff returns VERDICT: PASS.", file=sys.stderr)
    return 2


def rel_path(payload):
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return None
    try:
        return pathlib.Path(raw).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def guard(rel):
    if rel and rel.startswith(OWNED):
        print(f"{rel} is a PILOT-owned copy, synced from main by /pilot-update, never edited here. "
              "Edit its source (assets/docs/, scripts/pilot.py, assets/github/) instead.", file=sys.stderr)
        return 2
    return 0


def lint(rel):
    if not rel or not rel.startswith(LINTED):
        return 0
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "lint_pilot.py")], capture_output=True, text=True, timeout=60)
    if out.returncode:
        print("scripts/lint_pilot.py reports errors (fix before finishing the change):\n" + out.stdout, file=sys.stderr)
        return 2
    return 0


def main_safe(payload, root):
    """The PR gate that never raises: a repo git cannot read (no origin/main, no history) is not blocked."""
    try:
        return pr_gate(payload, root)
    except Exception:
        return 0


def main():
    try:
        payload = json.load(sys.stdin)
        if sys.argv[1] == "review-track":
            return review_track(payload)
        if sys.argv[1] == "pr-gate":
            return main_safe(payload, ROOT)
        return {"guard": guard, "lint": lint}[sys.argv[1]](rel_path(payload))
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
