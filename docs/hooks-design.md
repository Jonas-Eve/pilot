# PILOT — hooks (design proposal)

Status: **proposal; nothing implemented in consuming projects**. Only this repo's own maintainer hooks exist
(`.claude/settings.json`, `scripts/hooks/repo_hook.py`). Human-only document: no skill or agent reads it, and it
is not copied into consuming projects.

## 1. Goal

A skill explains; it does not constrain. A hook is code the harness runs on a tool call, and it can refuse the
call and tell the model why. Hooks make a rule deterministic where prose only asks for it (CLAUDE.md §3,
"Deterministic first"): fewer rules in the LLM-read files, no drift between the rule and what actually happens.

Scope: the **project side** (what the agents running a PILOT phase may do). Not this repo's maintainer hooks.

## 2. What was measured

Tested in Claude Code cloud sessions (the surface that motivated the "plain repo" distribution model).

| Hook source | Fires for the main session | Fires inside a sub-agent (`Agent` tool) |
|---|---|---|
| Project `.claude/settings.json` | yes | **yes** (payload carries `agent_id`, `agent_type`) |
| Frontmatter of a skill | yes, for the rest of the session | **no** |
| Frontmatter of an agent (`.claude/agents/*.md`) | not applicable | **no** (three variants tried: with `${CLAUDE_PROJECT_DIR}`, relative path, bare `touch`) |

Also observed: `CLAUDE_PROJECT_DIR` is set and `CLAUDE_CODE_REMOTE=true`; a skill is discovered live but a new
agent file only at session start.

Consequence: judgment, and therefore the code that must be constrained, runs in sub-agents. Only
`settings.json` reaches them. The frontmatter route is a dead end for personas (cause not established: refused
by default in cloud, or workspace trust never accepted; the outcome is the same). Not tested: the mobile app,
`claude -p`.

## 3. Principles

1. **One entry point, in `pilot.py`**: `python3 .pilot/pilot.py hook <name>`, reads the hook payload on stdin.
   Decisions are code with offline tests (`scripts/test_pilot.py`), like every other mechanic.
2. **Inert outside a PILOT run.** A project's own work is never touched. No active run → exit 0.
3. **Fail open.** Missing script, bad payload, any exception → exit 0. A hook never blocks the project because
   PILOT is broken.
4. **A refusal always names the command to use instead** (`pilot.py set …`), so the model recovers by itself.
5. **Best effort, not security.** A hook that matches a command string can be bypassed (`gh api`, an alias).
   It stops the model's habit, not an adversary; the doc says so wherever a hook is listed.
6. **Opt-in module.** Enabled like the others (`pilot.py module enable hooks`), asked at `/pilot-init` and
   `/pilot-update`. Off by default for existing projects.

## 4. The run marker

A hook must know a PILOT run is active, for which phase, and what it is allowed to do.

- `pilot.py claim` writes `.pilot/run.json` (git-ignored): `{session_id, phase, ticket, mode, merge, at}`.
  `set` to a terminal status, `unflag`, or an explicit `pilot.py run end` removes it. A marker older than a
  TTL (12 h) is ignored.
- A hook acts only when the payload's `session_id` equals the marker's. This also keeps a second Claude session
  on the same checkout out of it.
- `merge` is true only when the phase was started with `--merge` (review).

A sub-agent's payload carries the **same `session_id`** as its parent (measured), plus `agent_id` and
`agent_type`; the match needs nothing more.

## 5. Installation: merging into `settings.json`

`.claude/settings.json` belongs to the project; PILOT never replaces it.

`pilot.py hooks install|check|remove`:
- Reads the file (absent → `{}`); **refuses and reports** if it is not valid JSON.
- Adds the PILOT entries under `hooks.PreToolUse` etc., leaving every other key and entry untouched. An entry
  is PILOT's when its command starts with `python3 "$CLAUDE_PROJECT_DIR/.pilot/pilot.py" hook`.
- Idempotent: running it twice changes nothing. A later release's `install` updates PILOT's entries in place
  and removes the ones it no longer ships.
- Writes atomically; prints one JSON object (added, updated, removed, unchanged), like every command.
- `check` is read-only and feeds `doctor` (module on but entries missing or stale → reported).

`/pilot-init` and `/pilot-update` ask before running `install`, since it edits a project-owned file.
`/pilot-update` also runs it silently when the module is on, to keep entries current.

## 6. First set of hooks

| Hook | Event / matcher | Acts when | Refuses |
|---|---|---|---|
| `status-guard` | PreToolUse: `Bash` (`gh issue edit`, `gh api …issues`), `mcp__github__issue_write` | a run is active | a by-hand change of a `status:` label or of the assignee; names `pilot.py set` / `claim` |
| `merge-guard` | PreToolUse: `Bash` (`gh pr merge`), `mcp__github__merge_pull_request` | a run is active and `merge` is false; always for a PR whose head starts with `wiki/` or `architecture/` | the merge |
| `owned-guard` | PreToolUse: `Edit`, `Write` | always | a write under `.pilot/`; names `/pilot-update` |

Possible later: a Stop / SubagentStop hook (a Dev run does not end without a PR or a `needs-human` with its
comment), `PILOT_ACCOUNT_*` not echoed in `/pilot-flow`, reads under `wiki/` and `architecture/` through
`pilot.py wiki|arch` only.

## 7. What leaves the prose once it ships

Each hook that lands removes the sentence it enforces from the skills and docs, in the same PR: "no by-hand
fallback" and the by-hand label wording, "never merge" (about a dozen occurrences across dev, review, wiki,
architecture, flow), "`.pilot/` is never edited". A rule stays in prose only if the hook cannot see it.

## 8. Tests

- `test_pilot.py`: each hook against payload fixtures (no marker, matching marker, other session, expired,
  `merge` true/false, bad JSON, missing file); `hooks install` on an absent file, a file with the project's own
  hooks, a stale PILOT entry, invalid JSON, run twice.
- A real session check, once: install into a scratch project, run a claim, see the refusal.
- `lint_pilot.py`: the commands the hooks name exist in `pilot.py`'s argparse.

## 9. Versioning

`VERSION`: **minor** (a backward-compatible capability; the module is off until a project enables it). The
first release that makes `/pilot-update` edit `settings.json` is documented in the PR.

## 10. Open questions

1. Mobile app and `claude -p` behaviour of `settings.json` hooks (the docs say a headless run treats the
   folder as trusted; interactive runs wait for the workspace-trust dialog).
2. Whether `if: "Bash(gh pr merge *)"` is worth using over matching in the script (one rule per handler, an
   unclear behaviour on chained commands); the script matches by default.
3. Where the marker lives when a cloud session is resumed in a new container (`.pilot/run.json` is lost; a
   resumed run then has no guard, which is the fail-open side).
