# PILOT link — Phase 5 review consensus

Injected whole by `pilot-review/SKILL.md` into each reviewer's prompt, and by
`pilot-dev`/`pilot-e2e`'s task docs on reclaim. The reviewer set itself is
`pilot-review/SKILL.md`'s own step 3, not here. Never by `.claude/agents/pilot-*.md`,
which carry only identity now. See `.pilot/pilot-process.md` §2/§3/§4 for the generic
labels, states, and claim protocol this builds on.

Each reviewer returns a verdict: approve, or block with one or more points tagged either
`change` — a concrete fix the reviewer can articulate, nothing for a human to weigh in on
— or `decision` — a genuine judgment call with no fix to propose until a human weighs in.
Default to `change` whenever a fix can be named. A validation/CI mismatch always counts as
`change`: the tech lead re-runs this project's own build/test/lint commands directly
against the PR's branch before voting (`.pilot/pilot-task-review-spec-conformance.md`) — the
other reviewers don't duplicate that check — and once this project has a CI workflow
covering the affected area, a red or pending check on the PR's head commit is the same kind
of automatic block; until then, the tech lead's re-run is PILOT's only safety net. Once
every reviewer's verdict is in, the tags decide the outcome, each submitted as its own
GitHub PR review event — never a plain issue comment for this:
- All approve → an approval; `status:approved` (`.pilot/pilot-process.md` §3).
- At least one blocking point tagged `change`, **none** tagged `decision` → a request for
  changes; `status:changes-requested`, **no** `needs-human` — nothing here needs a human to
  decide, so `/pilot-dev` may reclaim it immediately, reading the `change`-tagged points
  back off the submitted PR review (not a plain issue comment;
  `.pilot/pilot-process.md` §4 "Reclaiming a `status:changes-requested` ticket" — that
  section also covers keeping the issue coherent with the fix).
- At least one blocking point tagged `change` **and** at least one tagged `decision` → a
  request for changes; `status:changes-requested`, `needs-human` added — the `decision`
  point(s) still need a human before `/pilot-dev` can reclaim, even though some points in
  the same review are already actionable as-is.
- Every blocking point tagged `decision`, none `change` → a plain comment (nothing
  code-level to request, and not an approval either); `needs-human` added,
  `status:in-review` stays (`.pilot/pilot-process.md` §3) — this ticket re-enters phase 5's
  own pool once cleared, unless resolved live first (`pilot-review/SKILL.md`).
