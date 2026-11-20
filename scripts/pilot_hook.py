#!/usr/bin/env python3
"""PILOT's hook entry point: what runs on a tool call during a PILOT run (design: docs/hooks-design.md).

  pilot_hook.py guard   PreToolUse: refuse an edit of `.pilot/`, and, during a run, a merge the run was not claimed with
                        --merge for and a by-hand change of a ticket's labels or assignees
  pilot_hook.py track   PostToolUse on Bash: a successful `pilot.py claim` opens the run of this Claude session

The payload is on stdin; exit 2 is a refusal the model reads on stderr. It fails open: any problem exits 0. Kept apart from
`pilot.py` on purpose: a hook runs on every tool call, so this file imports a handful of stdlib modules and nothing else.
`pilot.py hooks install` is what puts it in the project's `.claude/settings.json`.
"""
import json
import os
import re
import shlex
import sys
import tempfile
import time

RUN_TTL_SECONDS = 4 * 3600  # a run marker older than this is ignored; a new claim replaces it
OWNED_DIR = ".pilot/"
OWNED_EXEMPT = (".pilot/state.json",)  # the one file of that folder a skill may write by hand
LABEL_EDIT_FLAGS = ("--add-label", "--remove-label", "--add-assignee", "--remove-assignee")


def run_marker_path(session_id):
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
    return os.path.join(tempfile.gettempdir(), f"pilot-run-{safe}.json")


def read_run(session_id, now=None):
    """The active PILOT run of this Claude session (written by `hook track` when a `claim` succeeds), or None."""
    if not session_id:
        return None
    try:
        with open(run_marker_path(session_id), encoding="utf-8") as handle:
            run = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(run, dict) or (now or time.time()) - run.get("at", 0) > RUN_TTL_SECONDS:
        return None
    return run


def write_run(session_id, run):
    with open(run_marker_path(session_id), "w", encoding="utf-8") as handle:
        json.dump(run, handle)


def end_run(session_id):
    try:
        os.remove(run_marker_path(session_id))
    except OSError:
        pass


def command_words(command):
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


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


def runs_command(command, *prefix):
    return any(c[:len(prefix)] == list(prefix) for c in shell_commands(command))


def pilot_call(command):
    """(subcommand, args) when the Bash command runs `pilot.py <subcommand> ...`, else None."""
    words = command_words(command)
    for i, word in enumerate(words):
        if word.endswith("pilot.py") and i + 1 < len(words):
            return words[i + 1], words[i + 2:]
    return None


def refusal(message):
    return {"decision": "deny", "message": message}


def guard_decision(payload, now=None):
    """What the PreToolUse guard says about one tool call: None to let it through, or a refusal. Inert outside a PILOT run,
    except the write guard on `.pilot/`; never raises (a hook that breaks must not block the project)."""
    tool, params = payload.get("tool_name", ""), payload.get("tool_input") or {}
    if tool.startswith("mcp__"):  # the server's name varies (github, GitHub…): the tool is what counts
        tool = "mcp__github__" + tool.rsplit("__", 1)[-1].lower()
    if tool in ("Edit", "Write"):
        raw = str(params.get("file_path", ""))
        root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
        rel = os.path.relpath(os.path.abspath(os.path.join(root, raw)), root).replace(os.sep, "/")
        if rel.startswith(OWNED_DIR) and rel not in OWNED_EXEMPT:
            return refusal(f"{rel} is a PILOT-owned copy: /pilot-update replaces it from the published release. "
                           "Never edit it here; edit its source in the PILOT repository.")
        return None
    run = read_run(payload.get("session_id"), now)
    if run is None:
        return None
    command = str(params.get("command", "")) if tool == "Bash" else ""
    if tool == "mcp__github__merge_pull_request" or tool == "mcp__github__enable_pr_auto_merge" or (
            tool == "Bash" and runs_command(command, "gh", "pr", "merge")):
        if not run.get("merge"):
            return refusal("A PILOT run never merges a pull request unless it was started with --merge. "
                           "Leave the merge to the human.")
        return None
    if tool == "mcp__github__issue_write":
        if params.get("method") == "update" and ("labels" in params or "assignees" in params):
            return refusal("Do not change a ticket's labels or assignees by hand during a PILOT run: use "
                           "`python3 .pilot/pilot.py set` (or claim / flag / unflag), which also keeps the status chain valid.")
        return None
    if tool == "Bash":
        for words in shell_commands(command):
            edits = words[:3] == ["gh", "issue", "edit"] and any(w.split("=")[0] in LABEL_EDIT_FLAGS for w in words)
            api = words[:2] == ["gh", "api"] and any(re.search(r"issues/\d+", w) for w in words) and any(
                re.search(r"labels|assignees", w) for w in words)
            if edits or api:
                return refusal("Do not change a ticket's labels or assignees by hand during a PILOT run: use "
                               "`python3 .pilot/pilot.py set` (or claim / flag / unflag).")
    return None


def track_run(payload, now=None):
    """PostToolUse on Bash: a successful `pilot.py claim` opens this session's run (a later claim replaces it); nothing ends it
    but the TTL, so the merge that follows a review's approving `set` is still guarded. Returns what it did (for the tests)."""
    session = payload.get("session_id")
    command = str((payload.get("tool_input") or {}).get("command", ""))
    call = pilot_call(command)
    if not session or not call:
        return None
    sub, rest = call
    if sub == "claim":
        out = payload.get("tool_response")
        text = out.get("stdout", "") if isinstance(out, dict) else str(out or "")
        try:
            result = json.loads(text.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return None
        if not isinstance(result, dict) or not result.get("claimed"):
            return None
        phase = rest[0] if rest else None
        write_run(session, {"phase": phase, "ticket": result.get("issue"), "status": result.get("status"),
                            "merge": "--merge" in rest, "at": now or time.time()})
        return "start"
    return None


def run_hook(name):
    """Entry point of a hook (`pilot_hook.py guard|track`), payload on stdin. Fails open: any problem exits 0."""
    try:
        payload = json.load(sys.stdin)
        if name == "guard":
            verdict = guard_decision(payload)
            if verdict:
                print(verdict["message"], file=sys.stderr)
                return 2
        elif name == "track":
            track_run(payload)
    except Exception:  # a hook never blocks the project because PILOT could not read a payload
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(run_hook(sys.argv[1] if len(sys.argv) > 1 else ""))
