# PILOT link — Phase 4 review consensus

Injected whole by `pilot-review/SKILL.md` into each reviewer's prompt, and by
`pilot-dev`/`pilot-e2e`'s task docs on reclaim. The reviewer set itself is
`pilot-review/SKILL.md`'s own step 3, not here. Never by `.claude/agents/pilot-*.md`,
which carry only identity now. See `.pilot/pilot-process.md` §3/§4 for the generic
labels, states, and claim protocol this builds on.

**When passed a prior submitted review on this PR** (`pilot-review/SKILL.md` step 3/5 —
this round follows a reclaim, not the PR's first review): read it before writing your own
points. For each of its `change`-tagged points, check the PR's current head commit and
drop it only if it's actually resolved there — otherwise re-raise it yourself, it never
carries over on its own. For a `decision`-tagged point the thread shows a human already
answered, take that resolution as given rather than re-litigating it; one still unanswered
is still open and belongs in your list again. Knowing this round follows an earlier one is
context, not a reason to look less carefully — the current head commit gets the same
scrutiny as a first pass, including anything the earlier round never touched.

Each reviewer returns a verdict: approve, or block with one or more points tagged either
`change` — a concrete fix the reviewer can articulate, nothing for a human to weigh in on
— or `decision` — a genuine judgment call with no fix to propose until a human weighs in.
Default to `change` whenever a fix can be named. Before returning it, re-read your own
points against the PR's current head commit and the review as a whole, not just what
prompted each one along the way, and drop or fix anything that no longer holds — phase 4
(Review) has no incremental buildup to reconcile the way phases 1-3 do
(`.pilot/pilot-process.md` §4 "Interaction modes"), so this is its own one-shot equivalent.
A validation/CI mismatch always counts as
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
  `.pilot/pilot-link-review-consensus.md` "Reclaiming a `status:changes-requested` ticket" — that
  section also covers keeping the issue coherent with the fix).
- At least one blocking point tagged `change` **and** at least one tagged `decision` → a
  request for changes; `status:changes-requested`, `needs-human` added — the `decision`
  point(s) still need a human before `/pilot-dev` can reclaim, even though some points in
  the same review are already actionable as-is.
- Every blocking point tagged `decision`, none `change` → a plain comment (nothing
  code-level to request, and not an approval either); `needs-human` added,
  `status:in-review` stays (`.pilot/pilot-process.md` §3) — this ticket re-enters phase 4's
  own pool once cleared, unless resolved live first (`pilot-review/SKILL.md`).

## Reclaiming a `status:changes-requested` ticket (`/pilot-dev` only)

Unlike "Resuming a `needs-human` ticket" or "Resuming an orphaned claim" above,
`status:changes-requested` is set by *phase 4*
(`.pilot/pilot-link-review-consensus.md`), not by `/pilot-dev` itself — the
ticket already has an open PR, and phase 4 unassigned it with its verdict.

Reclaiming one is `.pilot/pilot.py claim --mode reclaim`: assignee → this session,
`status:` → `in-dev`, re-read to confirm. An assignee an older verdict left on the ticket
doesn't count as "already claimed" for this status: it is overwritten.

Once claimed, pass the subagent the phase-4 blocking review — its submitted PR review,
read from the PR's reviews rather than the issue's comment thread
(`.pilot/pilot-link-review-consensus.md`) — with its
`change`-tagged points to fix, plus any `decision`-tagged points and their resolution,
instead of a fresh spec — the existing PR's branch is what gets more commits. The subagent
pushes to that same branch/PR (never a second PR for the same ticket) and, once satisfied,
moves the ticket to
`status:review-ready` (unassigned) exactly as it would after a first-time implementation —
never `status:in-review` directly, phase 4 claims it fresh.

Since the blocking points themselves live only in the PR review, not on the issue
(`.pilot/pilot-link-review-consensus.md`), and a pure-`change` reclaim (above) never has a
human look at the ticket before this, the subagent also posts one comment on the issue
itself when it pushes the fix — a short summary of what changed in response to the review,
so the ticket's own history stays coherent with the code without duplicating the review's
full detail (`.pilot/pilot-task-implement.md`).
