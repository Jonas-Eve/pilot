# PILOT link — Phase 5 review consensus

Read by `.claude/skills/pilot-review/SKILL.md` (orchestrates it), `.claude/agents/pilot-pm.md`,
`.claude/agents/pilot-architect.md`, and `.claude/agents/pilot-techlead.md` (produce the
tags below), and `.claude/skills/pilot-dev/SKILL.md` plus `.claude/agents/pilot-dev.md`/
`pilot-e2e.md` (read a `change`-tagged verdict back on reclaim) — not by any other phase.
See `docs/pilot-process.md` §2/§3/§4 for the generic labels, states, and claim protocol
this builds on.

## Reviewer set

Decided by **the ticket's own `type:`** (`docs/pilot-process.md` §2 "`type:` is never
inherited" — a `level:task` under a `type:feature` story can itself be `type:tech`, and is
reviewed as `type:tech`, never as if it inherited `type:feature` from its parent):
- `type:feature`/`type:e2e` → `pilot-pm` + `pilot-architect` + `pilot-techlead`
- `type:tech`/`type:bug` → `pilot-architect` + `pilot-techlead` only (no PM)

Three distinct, non-overlapping lenses — product fit/e2e-flow validation, conformance to
the security/architecture decisions recorded at scope time, spec conformance and code
quality/maintainability — deliberately not split into a fourth reviewer, since
`pilot-dev`/`pilot-e2e` already self-reviewed the diff before opening the PR
(`docs/pilot-process.md` §4 "Interaction modes"). All reviewers run **in parallel, fully
independent of each other** — none sees another's verdict — in both pair and `--auto`;
nothing later in the run reopens that isolation, not even the one pair checkpoint.

Before voting, the tech lead re-runs this project's own build/test/lint commands directly
against the PR's branch rather than trusting the PR description's claim that they pass — a
mismatch is an automatic block, always tagged `change` (below); the other reviewers don't
duplicate this, it's the tech lead's own check alone. Once this project has a CI
workflow covering the affected area, a red or pending check on the PR's head commit is the
same kind of automatic `change` block. Until CI exists, this re-run is PILOT's only safety
net.

## `change`/`decision` tags

Each reviewer returns a verdict: approve, or block with one or more points tagged either
`change` — a concrete fix the reviewer can articulate — or `decision` — a genuine judgment
call with no fix to propose until a human weighs in. Default to `change` whenever a fix can
be named. Once every reviewer's verdict is in, the tags decide the outcome, each submitted
as its own GitHub PR review event — never a plain issue comment for this:
- All approve → an approval; `status:approved` (`docs/pilot-process.md` §3).
- Any point tagged `change` (a validation/CI failure above always counts) → a request for
  changes; `needs-human` added, `status:changes-requested` (`docs/pilot-process.md` §3) —
  `/pilot-dev` reclaims once cleared, reading the `change`-tagged points back off the
  submitted PR review (not a plain issue comment).
- Every blocking point tagged `decision`, none `change` → a plain comment (nothing
  code-level to request, and not an approval either); `needs-human` added,
  `status:in-review` stays (`docs/pilot-process.md` §3) — this ticket re-enters phase 5's
  own pool once cleared, unless resolved live first (`pilot-review/SKILL.md`).
