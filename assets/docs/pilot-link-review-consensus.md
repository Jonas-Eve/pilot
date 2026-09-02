# PILOT link — Phase 5 review consensus

Injected whole by `pilot-review/SKILL.md` into each reviewer's prompt, and by
`pilot-dev`/`pilot-e2e`'s task docs on reclaim. The reviewer set itself is
`pilot-review/SKILL.md`'s own step 3, not here. Never by `.claude/agents/pilot-*.md`,
which carry only identity now. See `docs/pilot-process.md` §2/§3/§4 for the generic
labels, states, and claim protocol this builds on.

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
