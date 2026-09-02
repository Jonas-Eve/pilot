# PILOT link — Phase 5 review consensus

`pilot-review/SKILL.md` reads this in full for its own orchestration (step 3's reviewer
set, step 5's tag contract) but injects only the "`change`/`decision` tags" section into
each reviewer's task-doc prompt — a reviewer needs the shared verdict format, never the
orchestration logic that picked it. `docs/pilot-task-implement.md`/`-implement-e2e.md`
cite "Reviewer set" for which personas cover a reclaimed ticket, and read a
`change`-tagged verdict back off "`change`/`decision` tags" on reclaim. Not read directly
by any other skill, and never by `.claude/agents/pilot-*.md` — those carry only identity
now. See `docs/pilot-process.md` §2/§3/§4 for the generic labels, states, and claim
protocol this builds on.

## Reviewer set

Decided by **the ticket's own `type:`** (`docs/pilot-process.md` §2 "`type:` is never
inherited" — a `level:task` under a `type:feature` story can itself be `type:tech`, and is
reviewed as `type:tech`, never as if it inherited `type:feature` from its parent):
- `type:feature`/`type:e2e` → `pilot-pm` + `pilot-architect` + `pilot-techlead`
- `type:tech`/`type:bug` → `pilot-architect` + `pilot-techlead` only (no PM)

All reviewers run **in parallel, fully independent of each other** — none sees another's
verdict — in both pair and `--auto`; nothing later in the run reopens that isolation, not
even the one pair checkpoint. This section is read by `pilot-review/SKILL.md` for its own
step 3, and cited by `docs/pilot-task-implement.md`/`-implement-e2e.md` for which personas
cover a reclaimed ticket — never injected into a reviewer's own prompt, which only needs
its own task doc for that.

## `change`/`decision` tags

Each reviewer returns a verdict: approve, or block with one or more points tagged either
`change` — a concrete fix the reviewer can articulate — or `decision` — a genuine judgment
call with no fix to propose until a human weighs in. Default to `change` whenever a fix can
be named. A validation/CI mismatch always counts as `change`: the tech lead re-runs this
project's own build/test/lint commands directly against the PR's branch before voting
(`docs/pilot-task-review-spec-conformance.md`) — the other reviewers don't duplicate that
check — and once this project has a CI workflow covering the affected area, a red or
pending check on the PR's head commit is the same kind of automatic block; until then, the
tech lead's re-run is PILOT's only safety net. Once every reviewer's verdict is in, the
tags decide the outcome, each submitted as its own GitHub PR review event — never a plain
issue comment for this:
- All approve → an approval; `status:approved` (`docs/pilot-process.md` §3).
- Any point tagged `change` (a validation/CI failure above always counts) → a request for
  changes; `needs-human` added, `status:changes-requested` (`docs/pilot-process.md` §3) —
  `/pilot-dev` reclaims once cleared, reading the `change`-tagged points back off the
  submitted PR review (not a plain issue comment).
- Every blocking point tagged `decision`, none `change` → a plain comment (nothing
  code-level to request, and not an approval either); `needs-human` added,
  `status:in-review` stays (`docs/pilot-process.md` §3) — this ticket re-enters phase 5's
  own pool once cleared, unless resolved live first (`pilot-review/SKILL.md`).
