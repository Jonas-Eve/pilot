# PILOT link — Claim protocol, ticket pools, and resuming/reclaiming work

Read directly by every phase skill's own `SKILL.md` (`pilot-story` through `pilot-qa`) and
`pilot-auto`, to run their own claim/pool/resume bookkeeping — never injected into any
`Agent` call, and never read by `.claude/agents/pilot-*.md`, which carry only identity and
never reason about claiming (`.pilot/pilot-process.md` §5: "claim/label bookkeeping is
deterministic tool calls in the skill itself, not something the agent reasons about"). See
`.pilot/pilot-process.md` §2/§3 for the generic ticket types/labels this builds on. Its own
§4 keeps three claim-adjacent sections that stay there instead of here, because a
persona's own task doc relies on them directly: "Blocked-by dependencies", "Reclaiming a
`status:changes-requested` ticket", and "Interaction modes".

## Claim Protocol (avoiding two agents on the same ticket)

Phases 2, 3, 4, 5, and 6 each start by **claiming** the ticket before doing any real work,
because several instances of the same phase (e.g. several devs, or two overlapping
scheduled review sweeps) may run concurrently. Phase 1 doesn't fit this pattern the same
way — there's no pre-existing ticket to claim — but the moment it creates the ticket
(`status:draft`, `.pilot/pilot-process.md` §3), it assigns it the same way, and that
assignment sticks if the pair session ends before final approval, exactly like a claimed
ticket left mid-phase; see "Resuming an orphaned claim" below.

1. Read the ticket's current `status:` and assignee.
2. If it's not in the expected pre-claim status, or already has an assignee, stop — it's
   being worked or has moved on; pick a different ticket (or report nothing to do, if a
   specific ticket number was requested explicitly).
3. Otherwise, immediately set the assignee to the current agent/session and swap the
   `status:` label to the in-progress one for this phase.
4. Re-read the ticket once more. If the assignee is no longer this agent, another run won
   the race — stand down and pick something else. This is optimistic, not a real lock:
   cheap insurance against the common case, not a guarantee under true concurrent writes.
5. Only after a successful claim does the phase's real work (the subagent call) start.

Phase 5's claim only serializes separate *runs* of `/pilot-review` against the same
ticket — the three (or two) reviewers **within** one claimed run still execute
independently in parallel, never seeing each other's verdict
(`.pilot/pilot-link-review-consensus.md`).

### Picking the next ticket when none is specified

Phase 1 has no such pool at all — it always starts from a raw need in free text (or an
explicit `--resume <issue>`). When any other phase skill is invoked without an explicit
ticket number, it builds its candidate pool from **two** queries, not one:
1. **Fresh work** — tickets in its own pre-claim `status:`, no assignee.
2. **Resumable work** — tickets already in its own *in-progress* `status:`, still carrying
   the assignee from when they were originally claimed, now also carrying `can-resume`
   (`.pilot/pilot-process.md` §3) — a human's explicit signal that this one's safe to hand
   to the next sweep. A plain label check, same as any other pool query here — never
   something the subagent has to infer from a comment thread.

`/pilot-dev` alone has a **third** pool: tickets in `status:changes-requested` with
`needs-human` no longer present — phase 5 sent these back for an actual code fix
(`.pilot/pilot-link-review-consensus.md`). See
"Reclaiming a `status:changes-requested` ticket" (`.pilot/pilot-process.md` §4).

All pools that apply to a given phase skill are merged and picked from together: highest
`priority:` first, then a ticket referenced by another open ticket's "Blocks #M" comment
before one that isn't, then oldest by creation date to break ties; a ticket carrying no
`priority:` at all sorts last. A ticket still carrying
`needs-human` or `on-hold` is never a candidate in any pool, and neither is one whose body
has an unresolved "Depends on #N" reference (`.pilot/pilot-process.md` §4 "Blocked-by
dependencies") — both re-enter automatically once resolved, no flag to remove for the
dependency case. An orphaned claim (already assigned, still in that phase's in-progress
`status:`, without `can-resume`) is likewise never a candidate in any bare pool — see
"Resuming an orphaned claim" below; it resumes only via `can-resume` (once a human has
verified it's safe) or an explicit `--resume <issue>`.

### Resuming a `needs-human` ticket

A human resolves the flag by **removing the `needs-human` label** from the ticket —
optionally after leaving a reply comment with guidance, or with no reply at all if
there's nothing to add beyond "proceed as proposed." That removal, not a reaction or a
particular comment, is the entire signal a phase skill looks for. This can happen from
any session, at any time — nothing depends on the session that raised the block still
being alive. Whether the ticket also carries `can-resume` (`.pilot/pilot-process.md` §3)
decides whether it's a bare/scheduled-sweep candidate or only reachable by ticket number.

A phase skill treats a ticket as **resuming**, not a fresh claim, whenever it's already
in that phase's in-progress `status:` (whether picked up via `can-resume` or given
explicitly) — skip the claim, it's already claimed:
1. Read the full blocking context, not just the ticket body — the blocking comment and
   everything posted after it, for every phase except 5. Phase 5's own block is a
   submitted PR review, not a comment (`.pilot/pilot-link-review-consensus.md`) —
   read that, plus the PR's comment thread for
   whatever's posted after it.
2. If `needs-human` is still present, it isn't resolved yet — report that and stop (this
   only matters when a ticket number was given explicitly; the bare pool above already
   excludes these).
3. Otherwise, remove `can-resume` if present (`.pilot/pilot-process.md` §3) and proceed
   with the phase's `Agent` call, passing both the original blocking context and whatever's
   in the thread after it (a specific reply, or "no reply — treat as approved as proposed"
   if none). The agent proceeds, corrects, or blocks again if that still doesn't actually
   resolve things.

### Resuming an orphaned claim (`--resume`, or `can-resume`)

Distinct from both "Resuming a `needs-human` ticket" above and "Reclaiming a
`status:changes-requested` ticket" (`.pilot/pilot-process.md` §4): a ticket claimed
but with nobody actually still working it — still carrying its original assignee, still in
that phase's in-progress `status:` (`status:draft`, `status:in-scope`, `status:in-spec`,
`status:in-dev`, `status:in-review`, `status:in-qa`), with **no** `needs-human`. Two
different causes leave the exact same shape, indistinguishable from the ticket alone: a
**pair** session (`.pilot/pilot-process.md` §4 "Interaction modes") that ended before
reaching the phase's final approval (pair-capable phases only), or an `--auto` run that
died mid-work (a quota limit, a crash, a timeout) before it could either finish or flag
`needs-human`. Left alone, the normal claim-protocol check ("already has an assignee →
stop") would treat either the same as a ticket someone else is actively working right now,
which isn't the case. For phase 1 specifically, `status:draft` is what makes this possible
at all.

Nothing on the ticket itself distinguishes an orphaned claim from one genuinely still in
progress elsewhere — only a human verifying it firsthand can. Once they have, they can
resume it themselves right now via an **explicit** `--resume <issue>` (below — never part
of any bare/scheduled-sweep pool), or add `can-resume` (`.pilot/pilot-process.md` §3) to
hand it to the next sweep instead, same as a cleared `needs-human` ticket above.

To resume via `--resume`:
1. Read the full ticket — body and comment thread, not just the latest checkpoint. For
   `/pilot-scope`, `/pilot-spec`, and `/pilot-dev`'s pair sessions this reconstructs pair
   mode's incremental checkpoint writes (`.pilot/pilot-process.md` §4 "Interaction modes").
   `/pilot-review`'s own checkpoint is a pending GitHub PR review instead of a ticket
   comment (`pilot-review/SKILL.md` has the mechanics) — still pinned to the PR's current
   head commit → that's the recovered outcome, skip re-running the reviewers; stale or
   absent → discard any stale one and restart the reviewers fresh, the tech lead's
   re-validation needs the actual current code regardless. For an `--auto` run of any
   other phase, there's nothing to reconstruct — a plain restart from the ticket's
   original inputs.
2. Claim it the same way a `status:changes-requested` reclaim does
   (`.pilot/pilot-process.md` §4 "Reclaiming a `status:changes-requested` ticket") — an
   existing assignee doesn't count as a conflict here. Overwrite it (assignee → this
   session); `status:` stays at its current
   in-progress value.
3. Pass whatever step 1 recovered to the phase's `Agent` call as its starting context, and
   continue: the normal pair loop where one exists, otherwise a fresh pass.

Finalization behaves exactly as any other run of that phase from here.

### Scheduled sweeps

Each phase skill is meant to also run **bare, on a timer** — a Routine whose prompt is
nothing but the literal command. For `/pilot-scope`, `/pilot-spec`, `/pilot-dev`, and
`/pilot-review` — all four default to pair mode (`.pilot/pilot-process.md` §4 "Interaction
modes") — that literal command must include `--auto` (still no ticket number computed by
the routine itself), since pair requires a human live in the session and a Routine has
none. `/pilot-story` and `/pilot-qa` are pair-only with no `--auto` and are therefore never
driven by a Routine at all. Beyond that flag, this works without any special-casing
because "picking the next ticket when none is specified" (above) already covers both fresh
and resumed work identically. Four independent Routines — one each for `/pilot-scope
--auto`, `/pilot-spec --auto`, `/pilot-dev --auto`, and `/pilot-review --auto` (add
`--merge` too if the Routine should also merge once every reviewer approves,
`.pilot/pilot-process.md` §3 "`status:approved`") — each on its own schedule, so a slow or
failing phase never delays the others.
