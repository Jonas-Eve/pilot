#!/usr/bin/env python3
"""Claude Code hooks for working on this repo (maintainers of PILOT only; never copied into a project).

  repo_hook.py guard   PreToolUse on Edit|Write: refuse an edit of a PILOT-owned copy (`.pilot/`, the synced workflow)
  repo_hook.py lint    PostToolUse on Edit|Write: after an edit of a file the linter covers, run scripts/lint_pilot.py
                       and hand its errors back to the model
  repo_hook.py review-track  PostToolUse on Agent: a run of the maintainer review (docs/maintainer-review.md) that ended
                       with `VERDICT: PASS` is recorded for the diff it saw
  repo_hook.py pr-gate PreToolUse on create_pull_request / `gh pr create` / `gh api` POST to repos/…/pulls: refuse while the diff touches what projects copy
                       and no passing review of that exact diff is recorded

Reads the hook payload on stdin. Exit 2 = feedback to the model (stderr); any internal failure exits 0, never blocks.
"""
import hashlib
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OWNED = (".pilot/", ".github/workflows/pilot-status-on-merge.yml")
LINTED = (".claude/skills/", ".claude/agents/", "assets/docs/", "assets/templates/", "scripts/pilot.py", "CLAUDE.md")


REVIEWED = (".claude/skills/", ".claude/agents/", "assets/", "scripts/pilot.py",
            "scripts/setup-github-labels.sh")  # what projects copy: what a PR must have had reviewed
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


def shell_commands(command):
    """The simple commands of a Bash command line, each a list of words. Quoted text stays one word and the body of a
    here-document is not a command, so a PR body that quotes `gh pr merge` is not one."""
    lines, closing = [], None
    for line in command.splitlines():
        if closing is not None:
            if line.strip() == closing:
                closing = None
            continue
        lines.append(line)
        opened = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if opened:
            closing = opened.group(1)
    try:
        lexer = shlex.shlex(" ; ".join(lines), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return []
    commands, current = [], []
    for word in words:
        if word and all(c in ";&|" for c in word):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(word)
    if current:
        commands.append(current)
    return commands


def simple_commands(command, depth=0):
    """The commands really run: `shell_commands`, minus a leading `VAR=value`, `env`, `command` or `exec`, and with the string
    of a `bash|sh|zsh -c '<cmd>'` looked through (two levels at most)."""
    found = []
    for words in shell_commands(command):
        while words and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]) or words[0] in ("env", "command", "exec")):
            words = words[1:]
        if not words:
            continue
        if words[0] in ("bash", "sh", "zsh") and "-c" in words[:-1] and depth < 2:
            found += simple_commands(words[words.index("-c") + 1], depth + 1)
        else:
            found.append(words)
    return found


def runs_command(command, *prefix):
    return any(c[:len(prefix)] == list(prefix) for c in simple_commands(command))


def review_marker(session_id):
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
    return pathlib.Path(tempfile.gettempdir()) / f"pilot-maint-review-{safe}.json"


def answer_texts(response):
    """The texts an Agent call can carry its answer in, best first: `handbackReport.text` (the answer, when the harness hands
    the report back as a message and leaves only a notice in `content`), then `content`, then a bare string."""
    if not isinstance(response, dict):
        return [str(response)]
    texts = []
    report = response.get("handbackReport")
    if isinstance(report, dict) and isinstance(report.get("text"), str):
        texts.append(report["text"])
    content = response.get("content", response.get("text", ""))
    if isinstance(content, list):
        texts.append("\n".join(c.get("text", "") for c in content if isinstance(c, dict)))
    elif content:
        texts.append(str(content))
    return texts


def review_track(payload, root=ROOT):
    """After the review agent answered, remember the diff it reviewed and its verdict, read from the first line of the answer
    only (docs/maintainer-review.md): a later line that quotes `VERDICT: PASS` counts for nothing."""
    params = payload.get("tool_input") or {}
    if payload.get("tool_name") != "Agent" or REVIEW_DOC not in str(params.get("prompt", "")):
        return 0
    verdict = None
    for text in answer_texts(payload.get("tool_response", "")):
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        verdict = re.fullmatch(r"VERDICT:\s*(PASS|FINDINGS)", first)
        if verdict:
            break
    scope = review_scope(root)
    if not verdict or scope is None:
        return 0
    review_marker(payload.get("session_id")).write_text(json.dumps({"key": scope[1], "verdict": verdict.group(1)}))
    return 0


FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field", "--input")


def creates_pr_with_api(command):
    """`gh api` POSTing to `repos/<owner>/<repo>/pulls` (the REST route that creates a PR, now that `gh pr` and the GitHub MCP
    server are unavailable): the method is POST, or a field flag is given and the method is not stated (gh then POSTs)."""
    for words in simple_commands(command):
        if words[:2] != ["gh", "api"]:
            continue
        if not any(re.fullmatch(r"/?repos/[^/\s]+/[^/\s]+/pulls/?", w.split("?")[0]) for w in words[2:]):
            continue
        method = next((words[i + 1].upper() for i, w in enumerate(words[:-1]) if w in ("-X", "--method")), None)
        method = method or next((w.split("=", 1)[1].upper() for w in words if w.startswith("--method=")), None)
        if method == "POST" or (method is None and any(w in FIELD_FLAGS or w.startswith("--field=") for w in words)):
            return True
    return False


def pr_gate(payload, root=ROOT):
    tool, params = payload.get("tool_name"), payload.get("tool_input") or {}
    command = str(params.get("command", ""))
    if not ((str(tool).startswith("mcp__") and str(tool).lower().endswith("__create_pull_request"))
            or (tool == "Bash" and (runs_command(command, "gh", "pr", "create") or creates_pr_with_api(command)))):
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
          "review the diff against origin/main (see that document), run in the foreground (run_in_background false), fix every "
          "finding, and run it again. "
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
