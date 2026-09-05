---
name: pilot-dev
description: "Phase 4 of PILOT (see .pilot/pilot-process.md): implements a spec'd ticket (status:dev-ready) and opens a PR, or flags needs-human and stops without one if genuinely blocked. Uses the pilot-dev agent, or pilot-e2e when the ticket's own type is type:e2e. Claims the ticket (assignee + status:in-dev) first so parallel runs don't collide. Defaults to pair mode — agrees the approach with a live human before coding, checkpointing progress into the ticket; --auto skips this (required for a scheduled cron Routine, since pair needs a live human). Also resumes a previously-flagged ticket once needs-human clears, resumes a mid-pair-session ticket via --resume <issue number>, reclaims a status:changes-requested ticket by pushing new commits to its existing PR — immediately for a pure code-level review verdict (no needs-human ever set), or once needs-human clears for a verdict that also blocked on a judgment call — and with no argument sweeps fresh/resumable/reclaimable work (e.g. --auto from a scheduled cron Routine), skipping on-hold or dependency-blocked tickets and preferring one that blocks another. An optional --multi <N> runs N devs independently on their own branches for the one claimed ticket and reconciles them into a single PR, escalating to needs-human with every branch pushed on genuine, unresolved disagreement (see .pilot/pilot-link-multi-consensus.md) — no effect on a reclaim, which always pushes to the one already-open PR's own branch. Use once /pilot-spec has produced a technical spec."
argument-hint: "<issue number, optional — picks the next dev-ready or can-resume-marked ticket if omitted> [--auto] [--multi N] | <issue number> --resume"
---

# PILOT — Phase 4: Operate

Read `.pilot/pilot-process.md` first — source of truth for labels, states, and the claim
protocol; this skill covers only phase 4's mechanics. Most likely phase to run as several
parallel instances; the claim step below prevents collisions.

## Steps

1. Resolve the ticket:
   - With `--resume`: must be `status:in-dev`, assigned, no `needs-human`/`on-hold` (a
     ticket left mid-pair session). Follow `.pilot/pilot-process.md` §4 "Resuming an
     orphaned claim" instead of steps 2-6 — already claimed. Mismatch → report and stop.
   - Without `--resume`, `status:in-dev`, no `needs-human`/`on-hold`, carrying
     `can-resume` → resume, not a fresh claim. Follow
     `.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket" instead of steps 2-6 —
     already claimed.
   - Without `--resume`, `status:in-dev`, assigned, no `needs-human`/`on-hold`, no
     `can-resume` → likely mid-pair-session; report and ask the human to re-run
     with `--resume`, or add `can-resume` themselves.
   - `status:in-dev` still carrying `needs-human` or `on-hold` → unresolved; report and
     stop.
   - `status:changes-requested`, no `needs-human`/`on-hold` → **reclaim**, distinct from
     both above (a PR already exists; phase 5, not this skill, sent it back). Follow
     `.pilot/pilot-process.md` §4 "Reclaiming a `status:changes-requested` ticket" instead
     of steps 2-6 — claim per that section (an existing assignee doesn't block this claim,
     unlike step 2's normal rule) and skip straight to step 3, passing the phase-5
     blocking review instead of a fresh spec.
   - `status:changes-requested` still carrying `needs-human` or `on-hold` → unresolved;
     report and stop.
   - `status:dev-ready`, unclaimed, body carries an open "Depends on #N" → not ready yet;
     report which ticket it's blocked on and stop rather than claim (`.pilot/pilot-process.md`
     §4 "Blocked-by dependencies" — applies to an explicitly-given ticket exactly as to
     bare-pool selection below, not just the pool).
   - Otherwise, or no issue given → per `.pilot/pilot-process.md` §4 "Picking the next
     ticket...": the given ticket, or the merged pool of unclaimed `status:dev-ready`
     (fresh), `status:in-dev` carrying `can-resume` (resumable), and
     `status:changes-requested` with no `needs-human`/`on-hold` (reclaimable — immediately,
     for a review verdict that was purely code-level and so never carried `needs-human`
     to begin with, or once a human clears it for one that also blocked on a judgment
     call, `.pilot/pilot-link-review-consensus.md`) —
     a mid-pair-session ticket is never in this pool, only reachable via an explicit
     `--resume <issue>` — excluding any with an unresolved "Depends on #N"
     (`.pilot/pilot-process.md` §4 "Blocked-by dependencies"), ordered by highest
     `priority:`, then a ticket named in another open ticket's "Blocks #M" before one that
     isn't, then oldest first (`mcp__github__search_issues`). A scheduled cron Routine
     drives this with `--auto` added (`.pilot/pilot-process.md` §4 "Scheduled sweeps").
2. **Claim** it per `.pilot/pilot-process.md` §4: set assignee + `status:in-dev`, then
   re-read the ticket. If the assignee changed (another instance won the race), stand
   down and return to step 1 for a different ticket.
2a. **Pick the persona**: ticket's own `type:e2e` (`.pilot/pilot-link-e2e-tasks.md` — never
    inherited, read off the ticket, not its story) →
    `subagent_type: "pilot-e2e"`; otherwise `"pilot-dev"`. The only thing `type:e2e`
    changes here — claim, pool selection, and everything below apply identically either
    way.
3. Call the `Agent` tool with the `subagent_type` chosen in step 2a — once, or, with
   `--multi <N>`, N times in parallel each on its own branch plus a reconciliation pass
   (`.pilot/pilot-link-multi-consensus.md`) — except on a **reclaim** (step 1), where
   `--multi` has no effect and this always runs once: N independent branches don't
   compose with pushing more commits to one already-open PR's own branch. Read
   `.pilot/pilot-task-implement.md` and pass its content as part of the prompt — for
   `pilot-e2e`, also read and pass `.pilot/pilot-task-implement-e2e.md` alongside it, since
   it only documents that persona's differences from the base task. Also pass
   `.pilot/pilot-link-bug-tickets.md` in full — either persona may hit step 3a's bug case
   mid-implementation, and the task doc covers only the phase-4-specific delta itself, not
   the classify/originate mechanic. Pass the ticket's
   spec and the architect's decisions, including any UI/UX description carried into it
   (`.pilot/pilot-task-scope-story.md`) — not the running conversation history or the state
   of any other ticket being worked in parallel. **Resume case** (per step 1, needs-human
   cleared): also pass the original blocking comment and whatever's in the thread after it
   (`.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket"). **Reclaim case** (per
   step 1): pass the phase-5 blocking review — its submitted PR review, fetched via
   `mcp__github__pull_request_read` method `get_reviews` (the body holds the points, not a
   plain issue comment, `.pilot/pilot-link-review-consensus.md`) — with its `change`-tagged
   points to fix, plus any `decision`-tagged points and their resolution, instead of a
   fresh spec — only more commits on the existing PR. **Unless `--auto` was given**
   (`.pilot/pilot-process.md` §4
   "Interaction modes" — pair is the default; a fresh claim or paused-pair resume only,
   never combined with a reclaim): first ask for a proposed implementation approach, not
   the finished implementation — the pair-coding checkpoint. Show the human that plan as a
   normal reply, wait for their response, feed it back to the agent, repeat until approved,
   writing each approved checkpoint into the ticket right away (a comment, or a partial
   `issue_write`) rather than holding it in-conversation — this is what `--resume` picks
   back up if the session ends before final approval (`.pilot/pilot-process.md` §4
   "Resuming an orphaned claim"). Requires a human live in this session; a scheduled
   Routine must pass `--auto` instead. Once approved, proceed with implementation below —
   the "ask live" behavior for a genuine blocker (§3) still applies during implementation
   itself; pair mode doesn't replace it.
4. The subagent (or, with `--multi`, the reconciled instance) either implements the
   ticket, runs the relevant validation, and opens a
   pull request following this project's own PR template if it has one (e.g.
   `.github/pull_request_template.md`) — including a "PILOT ticket" section if the
   template defines one: type, `Closes #<issue>`, spec deviations — or, for a reclaim,
   pushes new commits addressing the blocking review to that same existing PR instead of
   opening a new one — or hits a genuine blocking conflict it can't resolve alone and
   stops without a PR (or without pushing, for a reclaim). With `--multi`, if
   reconciliation still can't resolve a genuine disagreement after its one retry round,
   stop here instead: push every instance's branch (never merge them, never open a PR yet)
   and add `needs-human` with each branch linked plus every round's differing positions
   quoted verbatim (`.pilot/pilot-link-multi-consensus.md`).
5. Apply the result:
   - PR opened, or new commits pushed to an existing PR (reclaim case): clear the assignee
     and set `status:review-ready` on the ticket (phase 5's own pre-claim status — never
     `status:in-review` directly, `.pilot/pilot-process.md` §4 "Claim Protocol").
   - Blocking conflict: nothing further to set — the subagent already added
     `needs-human` and posted its comment itself (`status:in-dev` stays, per
     `.pilot/pilot-process.md` §3).
   - Bug discovered mid-implementation (`.pilot/pilot-process.md` §2 "Prerequisite bug
     tickets (phase 2, phase 4, or phase 6)"): nothing further to set — the subagent
     (`pilot-dev` or `pilot-e2e`) already originated the new `type:bug` ticket, linked it
     ("Blocks #M"/"Depends on #N"), pushed its WIP to a branch with a comment naming it,
     cleared the assignee, and moved the ticket back to `status:dev-ready` itself. It's
     now an ordinary `status:dev-ready` candidate again, gated only by the dependency
     (step 1's "Depends on #N" bullet) — no flag to clear, no `--resume` needed;
     whichever future run claims it picks up that branch per step 1's own claim-time
     check (`.pilot/pilot-task-implement.md` step 1).
6. Report the PR URL, or the blocking summary, back to the human. Never merge as part of
   this skill.
