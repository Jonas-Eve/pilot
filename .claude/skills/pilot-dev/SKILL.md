---
name: pilot-dev
description: "Phase 4 of PILOT (see docs/pilot-process.md): implements a single spec'd ticket (status:dev-ready) and opens a pull request — or flags needs-human and stops without a PR if it hits something it genuinely can't resolve alone. Calls the senior-dev agent (pilot-dev) for an ordinary ticket, or the end-to-end-test agent (pilot-e2e) instead when the ticket carries the secondary type:e2e label. Claims the ticket (assignee + status:in-dev) before starting so multiple devs can run this skill in parallel without picking the same ticket. Defaults to pair mode — agrees on the implementation approach with a human live in the session before writing any code (pair-coding), checkpointing progress into the ticket as it goes; pass --auto to implement straight away instead (needed for a scheduled cron Routine, since pair requires a live human). Also resumes a ticket it previously flagged once a human clears that flag, resumes a ticket left mid-pair session with --resume <issue number>, reclaims a ticket phase 5 sent back for changes (status:changes-requested, once needs-human is cleared) and pushes new commits to its existing PR, and runs bare with no argument to pick up fresh, needs-human-resumable, or reclaimable work (e.g. --auto from a scheduled cron Routine), skipping anything still on-hold or blocked by an unresolved 'Depends on #N' reference, and preferring a ticket that blocks another over one that doesn't. Use once a ticket has a technical spec from /pilot-spec and is ready to be built."
argument-hint: "<issue number, optional — picks the next dev-ready or needs-human-resumable ticket if omitted> [--auto] | <issue number> --resume"
disable-model-invocation: true
---

# PILOT — Phase 4: Operate

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 4. This is the phase most likely to run as several parallel
instances (several devs picking up different tickets at once) — the claim step below is
what keeps them from colliding.

## Steps

1. Resolve the ticket:
   - Given issue number with `--resume`: it must be `status:in-dev`, already assigned,
     with **no** `needs-human` and **no** `on-hold` — a ticket left mid-pair session.
     Follow `docs/pilot-process.md` §4 "Resuming a paused pair session" instead of steps
     2-6 below — skip the claim, it's already claimed. If the ticket doesn't match, report
     that and stop.
   - Given issue number without `--resume`, `status:in-dev`, **no** `needs-human`, **no**
     `on-hold`, and its thread shows a `needs-human` block that was later cleared →
     resume, not a fresh claim. Follow `docs/pilot-process.md` §4 "Resuming a
     `needs-human` ticket" instead of steps 2-6 below — skip the claim, it's already
     claimed.
   - Given issue number without `--resume`, `status:in-dev`, already assigned, **no**
     `needs-human`, **no** `on-hold`, but with no `needs-human` history in its thread →
     this looks like a ticket left mid-pair session. Report that and ask the human to
     re-run with `--resume` rather than proceeding.
   - Given issue number, `status:in-dev`, still has `needs-human` or `on-hold` → not
     resolved yet, report that and stop.
   - Given issue number, `status:changes-requested`, no `needs-human` and no `on-hold` →
     **reclaim**, a third case distinct from both above (a PR already exists; phase 5,
     not this skill, sent it back). Follow `docs/pilot-process.md` §4 "Reclaiming a
     `status:changes-requested` ticket" instead of steps 2-6 below — claim it per that
     section (an existing assignee doesn't block this claim, unlike step 2's normal rule)
     and skip straight to step 3, passing the phase-5 blocking comment instead of a fresh
     spec.
   - Given issue number, `status:changes-requested`, still has `needs-human` or
     `on-hold` → not resolved yet, report that and stop.
   - Given issue number, `status:dev-ready`, unclaimed, but its body carries a "Depends on
     #N" whose `#N` is still open → not ready yet, report which ticket it's blocked on
     and stop rather than claiming it (`docs/pilot-process.md` §4 "Blocked-by
     dependencies" — this check applies to an explicitly-given ticket exactly as it does
     to bare-pool selection below, not just the pool).
   - Given issue number otherwise, or none given → per `docs/pilot-process.md` §4
     "Picking the next ticket...": the given ticket, or the merged pool of unclaimed
     `status:dev-ready` (fresh), `status:in-dev` with `needs-human`/`on-hold` just
     cleared (resumable), and `status:changes-requested` with `needs-human`/`on-hold`
     just cleared (reclaimable) — a ticket left mid-pair session is never in this pool,
     only reachable via an explicit `--resume <issue>` — excluding any with an unresolved
     "Depends on #N" (`docs/pilot-process.md` §4 "Blocked-by dependencies"), highest
     `priority:` then a ticket named in another open ticket's "Blocks #M" before one that
     isn't, then oldest first (`mcp__github__search_issues`). This is what a scheduled
     cron Routine drives with `--auto` added (`docs/pilot-process.md` §4 "Scheduled
     sweeps").
2. **Claim** it per `docs/pilot-process.md` §4: set assignee + `status:in-dev`, then
   re-read the ticket. If the assignee changed since the claim (another instance won the
   race), stand down and go back to step 1 for a different ticket rather than proceeding.
2a. **Pick the persona**: if the ticket carries the secondary `type:e2e` label
    (`docs/pilot-process.md` §2 "End-to-end test sub-tickets") — alongside whichever
    `type:` it inherits from its root — `subagent_type: "pilot-e2e"`; otherwise
    `subagent_type: "pilot-dev"` as before. This is the only thing `type:e2e` changes
    about this skill's mechanics — claim, pool selection, and everything below apply
    identically either way.
3. Call the `Agent` tool with the `subagent_type` chosen in step 2a, passing the ticket's
   spec and the architect's decisions — not the running conversation history, and not the
   state of any other ticket being worked in parallel. **If this is a
   `status:changes-requested`
   reclaim** (per step 1 above): pass the phase-5 blocking comment (the `change`-tagged
   points to fix, plus any `decision`-tagged points and their resolution) instead of a
   fresh spec — there's no new spec here, only more commits on the existing PR. **Unless
   `--auto` was given** (`docs/pilot-process.md` §4 "Interaction modes" — pair is the
   default for this skill; a fresh claim or a paused-pair resume only, never combined
   with a `status:changes-requested` reclaim): ask for a proposed implementation approach
   first, not the finished implementation — this is the pair-coding checkpoint. Show the
   human that plan as a normal reply, wait for their response, and feed it back to the
   agent — repeat until they approve, writing each approved checkpoint into the ticket
   right away (a comment, or a partial `issue_write`) instead of holding it
   in-conversation — this is what `--resume` picks back up later if the session ends
   before final approval (`docs/pilot-process.md` §4 "Resuming a paused pair session").
   Requires a human live in this session; a scheduled Routine must pass `--auto` instead.
   Once approved, proceed with implementation below — the already-existing "ask live"
   behavior for a genuine blocker (§3) still applies during implementation itself, pair
   mode doesn't replace it.
4. The subagent either implements the ticket, runs the relevant validation, and opens a
   pull request following this project's own PR template if it has one (e.g.
   `.github/pull_request_template.md`) — including a "PILOT ticket" section if the
   template defines one: type, `Closes #<issue>`, spec deviations — or, for a
   `status:changes-requested` reclaim, pushes new commits addressing the blocking comment
   to that same existing PR instead of opening a new one — or hits a genuine blocking
   conflict it can't resolve on its own and stops without a PR (or without pushing, for a
   reclaim).
5. Apply the result:
   - PR opened, or new commits pushed to an existing PR (reclaim case): set
     `status:in-review` on the ticket.
   - Blocking conflict: nothing further to set — the subagent already added
     `needs-human` and posted its comment itself (`status:in-dev` stays, per
     `docs/pilot-process.md` §3).
   - Bug discovered mid-implementation (`docs/pilot-process.md` §2 "Prerequisite bug
     tickets (phase 2 or phase 4)"): nothing further to set either — the subagent
     (`pilot-dev` or `pilot-e2e`) already originated the new `type:bug` ticket, linked it
     ("Blocks #M"/"Depends on #N"), and added `on-hold` with its own comment
     (`status:in-dev` stays). This ticket only becomes a candidate again for an explicit
     `--resume` once a human removes `on-hold` after the new ticket reaches
     `status:done`.
6. Report the PR URL, or the blocking summary, back to the human. Never merge as part of
   this skill.
