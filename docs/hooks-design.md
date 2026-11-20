# PILOT — hooks

Status: **implemented in v4.4.0**: `pilot_hook.py guard|track` (the lightweight entry point), `pilot.py hooks install|check|remove`, the opt-in `hooks`
module (`module enable hooks`; `/pilot-init` step 9d and `/pilot-update` step 5d run `install`; `doctor` checks it), and
`claim --merge` passed by the review skill. Not done: the guards for `wiki/` and `architecture/` PRs, a Stop hook, and the
prose the hooks make redundant (kept while the module is opt-in). This repo's own maintainer hooks are separate
(`.claude/settings.json`, `scripts/hooks/repo_hook.py`).

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

1. **One lightweight entry point, `pilot_hook.py`** (copied as `.pilot/pilot_hook.py`): `guard` and `track`, the hook payload on
   stdin. A hook runs on every tool call, so the file imports a handful of stdlib modules and nothing else (about 25 ms
   instead of about 88 ms when it was part of `pilot.py`, which is recompiled at each run). Decisions are code with offline tests
   (`scripts/test_pilot.py`), like every other mechanic. The installed command exits 0 when the file is missing: a Python that
   cannot open its script exits 2, which a hook reads as a refusal.
2. **Inert outside a PILOT run**, except the write guard on `.pilot/`, which always applies. A project's own work is
   never touched. No active run → exit 0.
3. **Fail open.** Missing script, bad payload, any exception → exit 0. A hook never blocks the project because
   PILOT is broken.
4. **A refusal always names the command to use instead** (`pilot.py set …`), so the model recovers by itself.
5. **Best effort, not security.** A hook that matches a command string can be bypassed (`gh api`, an alias). It matches a
   command that is *run* (quoted text and here-document bodies are not commands: a PR body quoting `gh pr merge` passes).
   It stops the model's habit, not an adversary; the doc says so wherever a hook is listed.
6. **Opt-in module.** Enabled like the others (`pilot.py module enable hooks`), asked at `/pilot-init` and
   `/pilot-update`. Off by default for existing projects.

## 4. The run marker

A hook must know a PILOT run is active, and whether it may merge.

- **Written by a hook, not by `claim`**: the `claim` process does not know the Claude session. `track`
  (PostToolUse on `Bash`) sees a successful `pilot.py claim` and writes `<tmpdir>/pilot-run-<session_id>.json`:
  `{phase, ticket, status, merge, at}`. `merge` is true when the command line carried `--merge` (the flag exists on
  `claim` for that purpose; the review skill must pass it).
- **Keyed by session**: a second Claude session on the same checkout has its own file, so is never guarded by
  another's run. A sub-agent's payload carries the **same `session_id`** as its parent (measured), plus `agent_id`
  and `agent_type`, so one file covers the whole run.
- **Ends** after a TTL of 4 h, or when a later `claim` replaces it. A `set` does not end it: the merge that follows a
  review's approving `set` must still be guarded. A marker lives outside the repository (nothing to git-ignore); a cloud session resumed in a new container
  loses it, which is the fail-open side.

## 5. Installation: merging into `settings.json`

`.claude/settings.json` belongs to the project; PILOT never replaces it.

`pilot.py hooks install|check|remove [--path P]`:
- Reads the file (absent → `{}`); **refuses** with `invalid-json` and leaves it untouched when it cannot be read.
- Drops every PILOT handler, then adds the current two: `PreToolUse` → `guard` on
  `Bash|Edit|Write|mcp__.*__(issue_write|merge_pull_request|enable_pr_auto_merge)` (any GitHub MCP server name),
  `PostToolUse` → `track` on `Bash`. A handler is PILOT's when its command holds
  `.pilot/pilot_hook.py`; every other key, group and handler is kept as it was.
- Idempotent; writes atomically; prints one JSON object (`changed`). `check` is read-only (`installed`).

`/pilot-init` (step 9d) installs when the module is chosen, and says it edits `.claude/settings.json` when asking;
`/pilot-update` (step 5d) refreshes the entries when the module is on and only mentions the module when it is off.

## 6. The guards

One handler, `guard`, decides by tool; all but the first act only during a run of this session.

| Guard | Tools | Refuses |
|---|---|---|
| owned | `Edit`, `Write` (always, run or not) | a write under `.pilot/` except `.pilot/state.json`; names `/pilot-update` |
| merge | `Bash` (`gh pr merge`), `mcp__github__merge_pull_request`, `mcp__github__enable_pr_auto_merge` | the merge, unless the run was claimed with `--merge` |
| status | `Bash` (`gh issue edit`, `gh api …/issues/N`, with a label or assignee flag), `mcp__github__issue_write` (`update` with `labels` or `assignees`) | a by-hand label or assignee change; names `pilot.py set`. Creating a ticket and editing its body stay allowed |

Not in the first slice: refusing a merge of a `wiki/` or `architecture/` PR outside a run (the wiki and architecture
skills never claim, so no marker exists), a Stop / SubagentStop hook (a Dev run does not end without a PR or a
`needs-human` with its comment), `PILOT_ACCOUNT_*` not echoed in `/pilot-flow`, reads under `wiki/` and
`architecture/` through `pilot.py wiki|arch` only.

## 7. What leaves the prose once it ships

Each hook that lands removes the sentence it enforces from the skills and docs, in the same PR: "no by-hand
fallback" and the by-hand label wording, "never merge" (about a dozen occurrences across dev, review, wiki,
architecture, flow), "`.pilot/` is never edited". A rule stays in prose only if the hook cannot see it.

## 8. Tests

- `test_pilot.py` (`HooksTests`, done): each hook against payload fixtures (no marker, matching marker, other session, expired,
  `merge` true/false, bad JSON, missing file); `hooks install` on an absent file, a file with the project's own
  hooks, a stale PILOT entry, invalid JSON, run twice.
- A real session check, once: install into a scratch project, run a claim, see the refusal.
- `lint_pilot.py`: the commands the hooks name exist in `pilot.py`'s argparse (`check_commands`, done).

## 9. Versioning

Shipped as **4.4.0** (minor: new commands and an opt-in module, inert until enabled).

## 10. Open questions

1. Mobile app and `claude -p` behaviour of `settings.json` hooks (the docs say a headless run treats the
   folder as trusted; interactive runs wait for the workspace-trust dialog).
2. Whether `if: "Bash(gh pr merge *)"` is worth using over matching in the script (one rule per handler, an
   unclear behaviour on chained commands); the script matches by default.
3. Where the marker lives when a cloud session is resumed in a new container (`.pilot/run.json` is lost; a
   resumed run then has no guard, which is the fail-open side).
