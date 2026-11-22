# Hooks: what was measured, and why none ships to projects

Human-only; read by no skill or agent, not copied into a project. A project-side `hooks` module (PILOT's guards merged into a
project's `.claude/settings.json`) was built and then dropped; this keeps what was learned.

## Measured, in Claude Code cloud sessions

| Hook source | Fires for the main session | Fires inside a sub-agent (`Agent` tool) |
|---|---|---|
| Project `.claude/settings.json` | yes | yes (same `session_id`, plus `agent_id` and `agent_type`) |
| Frontmatter of a skill | yes, for the rest of the session | no |
| Frontmatter of an agent (`.claude/agents/*.md`) | n/a | no (three variants tried) |

A new agent file is only seen at session start; a skill is discovered live. `CLAUDE_PROJECT_DIR` is set.

In a real headless session with the guards installed, a merge, a by-hand label change and a write under `.pilot/` were refused and
the other steps ran, including a PR body that merely quotes `gh pr merge`; a control project without them ran everything. A hook
costs about 88 ms when it is part of a large script (the interpreter recompiles it each run) and about 30 ms as its own small file.

## Why it was dropped

- **It cannot be scoped to PILOT.** A `settings.json` hook sees every tool call of the project; it does not know which skill runs.
  PILOT's scope was a per-session run marker opened by `pilot.py claim`, which then applies to the project's own skills in that
  session until a timeout. A project skill that merges or edits labels there would be refused.
- **The label guard is too broad.** An `issue_write` replaces the whole label set, so a guard cannot tell PILOT's labels from the
  project's: it refused every update that carried labels or assignees, and had to be worked around in two skills.
- **It shrinks nothing.** Optional hooks cannot replace prose that projects without them still need, so the context agents read grew
  (about 1.8 KB) instead of shrinking. The rules a hook would enforce (never merge, no by-hand labels) are about 1 KB of prose.
- **A single user.** One project uses PILOT, so an opt-in module bought little and cost a second code path.

What stays: this repo's own maintainer hooks (`.claude/settings.json`, `scripts/hooks/repo_hook.py`).

## If it comes back

Scope the run to the skill (track the `Skill` tool and clear the marker when a non-PILOT skill starts; not verified that a hook sees
that tool), narrow the guard to the merge and `.pilot/` only, run `/pilot-update` in a real session first, then make it default
rather than a module so the prose can go.
