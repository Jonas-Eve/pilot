---
name: pilot-spec
description: "Phase 3 of PILOT (see docs/pilot-process.md): the tech lead agent writes the technical implementation spec for an already-scoped ticket (status:spec-ready), or flags needs-human if the architect's decisions don't hold up against the real code. Defaults to pair mode — walks through the drafted spec with a human live in the session, checkpointing progress into the ticket as it goes; pass --auto to write it straight away instead (needed for a scheduled cron Routine, since pair requires a live human). Also resumes a previously-flagged ticket once a human clears the flag, resumes a ticket left mid-pair session with --resume <issue number>, and runs bare with no argument to pick up fresh or needs-human-resumable work (e.g. --auto from a scheduled cron Routine), skipping anything on-hold or blocked by an unresolved 'Depends on #N' reference, preferring a ticket that blocks another over one that doesn't. Use once a ticket has been through /pilot-scope and needs its spec written before development starts."
argument-hint: "<issue number, optional — picks the next spec-ready or needs-human-resumable ticket if omitted> [--auto] | <issue number> --resume"
disable-model-invocation: true
---

# PILOT — Phase 3: Lay Out

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 3.

## Steps

1. Resolve the ticket:
   - Given issue number with `--resume`: must be `status:in-spec`, already assigned,
     with **no** `needs-human` and **no** `on-hold` — a ticket left mid-pair session.
     Follow `docs/pilot-process.md` §4 "Resuming an orphaned claim" instead of steps
     2-5 below — skip the claim, already claimed. If it doesn't match, report and stop.
   - Given issue number without `--resume`, `status:in-spec`, **no** `needs-human`, **no**
     `on-hold`, and its thread shows a `needs-human` block that was later cleared →
     resume, not a fresh claim. Follow `docs/pilot-process.md` §4 "Resuming a
     `needs-human` ticket" instead of steps 2-5 below — skip the claim, already claimed.
   - Given issue number without `--resume`, `status:in-spec`, already assigned, **no**
     `needs-human`, **no** `on-hold`, but no `needs-human` history in its thread → looks
     like a ticket left mid-pair session. Report that and ask the human to re-run with
     `--resume` rather than proceeding.
   - Given issue number, `status:in-spec`, still has `needs-human` or `on-hold` → not
     resolved yet, report that and stop.
   - Given issue number, `status:spec-ready`, unclaimed, but its body carries a "Depends
     on #N" whose `#N` is still open → not ready yet; report which ticket it's blocked on
     and stop rather than claim it (`docs/pilot-process.md` §4 "Blocked-by dependencies" —
     applies to an explicitly-given ticket the same as bare-pool selection below, not just
     the pool).
   - Given issue number otherwise, or none given → per `docs/pilot-process.md` §4
     "Picking the next ticket...": the given ticket, or the merged pool of unclaimed
     `status:spec-ready` (fresh) and `status:in-spec` with `needs-human`/`on-hold` just
     cleared (resumable — a ticket left mid-pair session is never in this pool, only
     reachable via an explicit `--resume <issue>`), excluding any with an unresolved
     "Depends on #N" (`docs/pilot-process.md` §4 "Blocked-by dependencies"), highest
     `priority:` then a ticket named in another open ticket's "Blocks #M" before one that
     isn't, then oldest first (`mcp__github__search_issues`). This is what a scheduled
     cron Routine drives with `--auto` added (`docs/pilot-process.md` §4 "Scheduled
     sweeps").
2. **Claim** it per `docs/pilot-process.md` §4: set assignee + `status:in-spec`, re-read
   to confirm the claim held.
3. Call the `Agent` tool with `subagent_type: "pilot-techlead"`, passing only the
   ticket's current body (including the architect's decisions, and, if resuming, the
   comment thread's resolution per §4) and pointers to the relevant docs for the area it
   touches (this project's own per-service/per-package docs, wherever it keeps them —
   e.g. `apps/<app-name>/docs/`, a `docs/` folder, or a service-level README) — not the
   running conversation history.
4. The subagent returns either: a technical spec to append to the ticket, or a
   blocking conflict with the architect's decisions that needs a human.
4a. **Unless `--auto` was given** (`docs/pilot-process.md` §4 "Interaction modes" — pair
    is the default for this skill): don't finalize the spec yet. Show the human the
    drafted spec outline as a normal reply, wait for their response, and feed it back to
    the agent — repeat until they approve, writing each approved checkpoint into the
    ticket right away (a comment, or a partial `issue_write`) rather than holding it
    in-conversation — this is what `--resume` picks back up if the session ends before
    final approval (`docs/pilot-process.md` §4 "Resuming an orphaned claim"). Requires
    a human live in session; a scheduled Routine must pass `--auto` instead. Once
    approved, continue to step 4b — its GitHub write is then just the remaining piece
    (final `status:dev-ready`), since the spec was already saved checkpoint by checkpoint.
4b. **Final consolidation pass** (`docs/pilot-process.md` §4 "Interaction modes"): before
    applying anything, have the tech lead re-read the whole spec as it now stands — not
    just the latest round's delta — and fix anything that no longer holds together
    across rounds. Do this whether the run was pair or `--auto`.
5. Apply the result:
   - Spec produced: update the ticket body, set `status:dev-ready`.
   - Blocking conflict: leave the subagent's explanation as a comment on the ticket, add
     `needs-human` (`status:in-spec` stays — it's an orthogonal flag, `docs/pilot-process.md`
     §3).
6. Report the outcome back to the human.
