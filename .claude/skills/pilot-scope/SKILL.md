---
name: pilot-scope
description: "Phase 2 of PILOT (see docs/pilot-process.md): the architect agent takes an already-formalized ticket (type:feature or type:tech, created via /pilot-story) and, in one pass, challenges it — scoping it as-is, splitting it into dev-sized sub-tickets, recording dependencies (a prerequisite type:tech ticket, and/or between sub-tickets of the same split), or deciding it shouldn't be built at all (status:wont-do) — or flags needs-human for a judgment call. When a type:feature story is split, the PM agent also checks the proposed sub-tickets against the story's original acceptance criteria before it's finalized. Defaults to pair mode — walks through the proposed decomposition with a human live in the session, checkpointing progress into the ticket as it goes; pass --auto to finalize straight away instead (needed for a scheduled cron Routine, since pair requires a live human). Also resumes a ticket it previously flagged needs-human once a human clears that flag, resumes a ticket left mid-pair session with --resume <issue number>, and runs bare with no argument to pick up fresh or needs-human-resumable work (e.g. --auto from a scheduled cron Routine), skipping anything still on-hold or blocked by an unresolved 'Depends on #N' reference. Use whenever an already-created ticket needs to be scoped/decomposed — not for formalizing a brand-new need, that's /pilot-story."
argument-hint: "<issue number> [--auto] | <issue number> --resume"
disable-model-invocation: true
---

# PILOT — Phase 2: Investigate

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 2.

## Steps

1. Determine the input:
   - An issue number given with `--resume`: it must be `status:scoping`, already
     assigned, with **no** `needs-human` and **no** `on-hold` — a ticket left mid-pair
     session. Follow `docs/pilot-process.md` §4 "Resuming a paused pair session" instead
     of the rest of these steps — skip the claim in step 2, it's already claimed. If the
     ticket doesn't match (wrong status, unassigned, or still carrying `needs-human`/
     `on-hold`), report that and stop.
   - An issue number given without `--resume` that's currently `status:scoping` with
     **no** `needs-human` and **no** `on-hold`, and whose thread shows a `needs-human`
     block that was later cleared → this is a resume, not a fresh claim. Follow
     `docs/pilot-process.md` §4 "Resuming a `needs-human` ticket" instead of the rest of
     these steps — skip the claim in step 2, it's already claimed.
   - An issue number given without `--resume` that's `status:scoping`, already assigned,
     **no** `needs-human`, **no** `on-hold`, but with no `needs-human` history in its
     thread → this looks like a ticket left mid-pair session. Report that and ask the
     human to re-run with `--resume` rather than proceeding.
   - An issue number that's `status:scoping` and still carries `needs-human` or
     `on-hold` → not resolved yet, report that and stop.
   - An issue number otherwise → this is an existing story (`type:feature` or
     `type:tech`) being scoped/re-scoped. Read it (`mcp__github__issue_read`), along with
     its parent Epic (if linked) and anything already referenced via "Blocks #M"/
     "Depends on #N" or a sub-issue relationship, as context for the agent. If it's
     `type:epic`, there's nothing to scope on the epic itself — stop and point at its
     stories instead.
   - No argument → per `docs/pilot-process.md` §4 "Picking the next ticket...": the
     merged pool of unclaimed `status:backlog` tickets (fresh) and `status:scoping`
     tickets with `needs-human`/`on-hold` just cleared (resumable — a ticket left
     mid-pair session is never in this pool, only reachable via an explicit
     `--resume <issue>`), highest `priority:` then oldest first. This is what a
     scheduled cron Routine drives with `--auto` added (`docs/pilot-process.md` §4
     "Scheduled sweeps").
2. **Claim** the ticket per `docs/pilot-process.md` §4: set assignee + `status:scoping`,
   re-read to confirm the claim held.
3. Call the `Agent` tool with `subagent_type: "pilot-architect"`, passing only what phase
   2 needs: the ticket's current body, its parent Epic/linked tickets if any, and
   pointers to this project's own coding standards/security conventions and its own
   architecture docs (wherever it documents its identity/tenancy/security boundaries and
   its target system design, if it has such docs). Not the running conversation history.
4. The subagent returns: a single scoped ticket body (no split needed), a set of
   proposed sub-tickets each with security/architecture decisions, dependencies, and a
   suggested priority, or a verdict that it shouldn't be built at all. Independently of
   which, it may also flag one or more **prerequisite** tech needs
   (`docs/pilot-process.md` §2 "Prerequisite tech tickets") and, for each, whether it's a
   hard blocker.
4a. **If the ticket is `type:feature` and the architect proposed a split**, call the
    `Agent` tool a second time with `subagent_type: "pilot-pm"`, passing the original
    story's acceptance criteria and the proposed sub-tickets, for a coverage check
    (`docs/pilot-process.md` §2 "Three levels" — the PM checks the split's coverage, not
    the architect's technical decisions). If the PM blocks with a gap, feed that back to
    the architect and repeat until it approves, before showing anything to the human in
    step 4b. This runs regardless of `--auto`/pair — it's a validation step, not a human
    checkpoint.
4b. **Unless `--auto` was given** (`docs/pilot-process.md` §4 "Interaction modes" — pair
    is the default for this skill): don't finalize anything yet. Show the human the
    proposed decomposition — split or not, security/architecture decisions,
    dependencies, wont-do verdict, any prerequisite tech need(s) flagged and whether each
    is a hard blocker, the PM's coverage check if one ran — as a normal reply, wait for
    their response, and feed it back to the architect (and PM, if its check applies) —
    repeat until they approve. Once a checkpoint is approved, write it into the ticket
    right away (a comment summarizing the current proposal, or a partial `issue_write`)
    instead of holding it in-conversation — this is what `--resume` picks back up later
    if the session ends before final approval (`docs/pilot-process.md` §4 "Resuming a
    paused pair session"). Requires a human live in this session; a scheduled Routine
    must pass `--auto` instead. Once approved, continue to step 5 as normal — its GitHub
    write is then just the remaining piece (final labels, any still-unwritten
    sub-issues), since earlier checkpoints were already saved.
5. Apply the result (`mcp__github__issue_write`, `mcp__github__sub_issue_write`):
   - No split: update the ticket body with the decisions, set `status:spec-ready`.
   - Split into sub-tickets: create the sub-issues, link them to the parent as native
     sub-issues, each inheriting the root `type:` and getting `status:spec-ready` +
     `priority:P0/P1/P2`. If the architect recorded a dependency between two of them, add
     a "Depends on #N" line to the dependent one's body
     (`docs/pilot-process.md` §2 "Dependencies between sub-tickets of the same split").
     Set the parent's `status:` to `split` (not `type:epic` — that label is reserved for
     a group of *stories*, not a story's own sub-tickets; see `docs/pilot-process.md`
     §2), leave it open and unassigned as a tracker.
   - Won't-do (clear-cut only): label `status:wont-do`, close the issue. If it's not
     clear-cut, add `needs-human` with the subagent's reasoning instead (keep
     `status:scoping`) — don't close it.
   - Prerequisite tech ticket(s) flagged (in addition to whichever of the above
     applies): create each the same way a fresh `type:tech` need is created
     (`docs/pilot-process.md` §2) — **never** as a sub-issue of the ticket being scoped,
     that would make it inherit this ticket's `type:`. For each one, add a "Blocks #M"
     comment on the new ticket, and its own separate line in this ticket's body naming
     it — "Depends on #N" if the architect judged it a hard blocker (this exact phrase is
     what `docs/pilot-process.md` §4 "Blocked-by dependencies" mechanically gates future
     phases on), or a plain non-gating reference (e.g. "Related prerequisite: #N")
     otherwise. Several prerequisites means several separate lines, one `#N` each —
     never combined onto one line (`docs/pilot-process.md` §4).
6. Report the outcome (ticket(s) scoped/split, dependencies recorded, prerequisite
   ticket(s) spun out, or closed as won't-do) back to the human.
