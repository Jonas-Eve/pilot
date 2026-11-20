#!/usr/bin/env python3
"""Claude Code hooks for working on this repo (maintainers of PILOT only; never copied into a project).

  repo_hook.py guard   PreToolUse on Edit|Write: refuse an edit of a PILOT-owned copy (`.pilot/`, the synced workflow)
  repo_hook.py lint    PostToolUse on Edit|Write: after an edit of a file the linter covers, run scripts/lint_pilot.py
                       and hand its errors back to the model

Reads the hook payload on stdin. Exit 2 = feedback to the model (stderr); any internal failure exits 0, never blocks.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OWNED = (".pilot/", ".github/workflows/pilot-status-on-merge.yml")
LINTED = (".claude/skills/", ".claude/agents/", "assets/docs/", "assets/templates/", "scripts/pilot.py", "CLAUDE.md")


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


def main():
    try:
        payload = json.load(sys.stdin)
        rel = rel_path(payload)
        return {"guard": guard, "lint": lint}[sys.argv[1]](rel)
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
