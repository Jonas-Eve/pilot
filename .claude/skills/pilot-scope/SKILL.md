---
name: pilot-scope
description: "Phase 2 of PILOT (see docs/pilot-process.md): the architect agent takes an already-formalized ticket (type:feature, type:tech, or type:bug, created via /pilot-story) and, in one pass, challenges it, then either scopes it as-is or splits it into dev-sized tasks (level:task, each with its own independent type: — never inherited) — a judgment call for type:tech/type:bug (scoping as-is is fine), but mandatory for type:feature: one or more tasks (typically type:feature, sometimes a type:tech enabler mixed in) plus exactly one end-to-end-test task typed type:e2e, depending on every other task in the split. Also records dependencies (a prerequisite type:tech or type:bug ticket, and/or between tasks of the same split), or decides the ticket shouldn't be built at all (status:wont-do) — or flags needs-human for a judgment call. For a type:feature story, the PM agent also checks the proposed type:feature tasks (excluding any type:tech or type:e2e sibling) against the story's original acceptance criteria before it's finalized. Defaults to pair mode — walks through the proposed decomposition with a human live in the session, checkpointing progress into the ticket as it goes; pass --auto to finalize straight away instead (needed for a scheduled cron Routine, since pair requires a live human). Also resumes a ticket it previously flagged needs-human once a human clears that flag, resumes a ticket left mid-pair session with --resume <issue number>, reclaims a type:feature story sitting at status:qa/status:in-qa to add a new round of tasks (moving it back to status:scoping, then status:split once the round is proposed — refuses outright on a status:done story, which always needs a new ticket instead), and runs bare with no argument to pick up fresh or needs-human-resumable work (e.g. --auto from a scheduled cron Routine), skipping anything still on-hold or blocked by an unresolved 'Depends on #N' reference. Use whenever an already-created ticket needs to be scoped/decomposed — not for formalizing a brand-new need, that's /pilot-story."
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
   - An issue number that's `status:done` → terminal, refuse
     (`docs/pilot-process.md` §2 "Re-scoping a `type:feature` story after its split is
     done"): report that it's already done and point the human at opening a new ticket
     for the additional work instead (a plain "Extends #N" reference in its body is
     enough). Never claim it.
   - An issue number that's `status:qa` (unclaimed) or `status:in-qa` (already assigned,
     regardless of who) → a valid re-scope entry point, not a fresh claim in the usual
     sense (`docs/pilot-process.md` §2 "Re-scoping a `type:feature` story after its split
     is done"). Read the ticket and its tasks (which ones are `status:done`, including the
     original e2e task) for context, post a comment explaining why (new scope found; any
     `status:in-qa` session is being set aside), then claim it — overwrite the assignee if
     any (same non-conflict exception a `status:changes-requested` reclaim gets, below) and
     set `status:scoping` — before continuing to step 3, passing that extra context (the
     earlier round's already-done tasks) alongside the ticket body. Skip step 2, the claim
     already happened here.
   - An issue number otherwise → this is an existing story (`type:feature`, `type:tech`,
     or `type:bug`) being scoped/re-scoped. Read it (`mcp__github__issue_read`), along with
     its parent Epic (if linked) and anything already referenced via "Blocks #M"/
     "Depends on #N" or a sub-issue relationship, as context for the agent. If it's
     `level:epic`, there's nothing to scope on the epic itself — stop and point at its
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
   its target system design, if it has such docs) — plus, for a `status:qa`/`status:in-qa`
   reclaim (step 1 above), which of its existing tasks are already `status:done` from the
   earlier round, including the original e2e one. Not the running conversation history.
4. The subagent returns one of:
   - For `type:tech`/`type:bug`: a single scoped ticket body (no split needed), or a set
     of proposed tasks (split, a judgment call) each with security/architecture
     decisions, dependencies, and a suggested priority.
   - For `type:feature`: always a set of proposed tasks — one or more dev tasks (each
     assigned its own `type:feature` or `type:tech`, whichever fits — `docs/pilot-process.md`
     §2 "`type:` is never inherited"), plus exactly one flagged as the mandatory
     end-to-end-test task, its own `type:e2e` (`docs/pilot-process.md` §2 "End-to-end test
     tasks"), dependent on every other task in the set. Never a single unsplit body for
     `type:feature`.
   - Or, for either: a verdict that it shouldn't be built at all.
   Independently of any of this, it may also flag one or more **prerequisite** needs —
   `type:tech` (`docs/pilot-process.md` §2 "Prerequisite tech tickets") or `type:bug`
   (`docs/pilot-process.md` §2 "Prerequisite bug tickets (phase 2 or phase 4)") — and, for
   each, whether it's a hard blocker.
4a. **If the ticket is `type:feature`** (always split, per step 4), call the `Agent` tool a
    second time with `subagent_type: "pilot-pm"`, passing the original story's acceptance
    criteria and **only the `type:feature` tasks** — excluding any `type:tech` task and
    the `type:e2e` task (`docs/pilot-process.md` §2 "End-to-end test tasks" — neither
    covers a criterion itself: a tech task is an enabler, the e2e task verifies criteria
    its `type:feature` siblings already cover), for a coverage check
    (`docs/pilot-process.md` §2 "Three levels" — the PM checks the split's coverage, not
    the architect's technical decisions). If the PM blocks with a gap, feed that back
    to the architect and repeat until it approves, before showing anything to the human in
    step 4b. This runs regardless of `--auto`/pair — it's a validation step, not a human
    checkpoint.
4b. **Unless `--auto` was given** (`docs/pilot-process.md` §4 "Interaction modes" — pair
    is the default for this skill): don't finalize anything yet. Show the human the
    proposed decomposition — split or not, any e2e task proposed, security/
    architecture decisions, dependencies, wont-do verdict, any prerequisite tech/bug
    need(s) flagged and whether each is a hard blocker, the PM's coverage check if one
    ran — as a normal reply, wait for
    their response, and feed it back to the architect (and PM, if its check applies) —
    repeat until they approve. Once a checkpoint is approved, write it into the ticket
    right away (a comment summarizing the current proposal, or a partial `issue_write`)
    instead of holding it in-conversation — this is what `--resume` picks back up later
    if the session ends before final approval (`docs/pilot-process.md` §4 "Resuming a
    paused pair session"). Requires a human live in this session; a scheduled Routine
    must pass `--auto` instead. Once approved, continue to step 4c — its GitHub
    write is then just the remaining piece (final labels, any still-unwritten
    sub-issues), since earlier checkpoints were already saved.
4c. **Final consolidation pass** (`docs/pilot-process.md` §4 "Interaction modes"): before
    applying anything, have the architect re-read the ticket (and every proposed
    task, if split) as a whole — not just the latest round's delta — and fix
    anything that no longer holds together across rounds (an earlier security decision
    that doesn't square with a later one, a gap neither checkpoint's author noticed). Do
    this whether the run was pair or `--auto` — `--auto` has no rounds to reconcile, but
    still benefits from one coherence read before writing.
5. Apply the result (`mcp__github__issue_write`, `mcp__github__sub_issue_write`):
   - No split (`type:tech`/`type:bug` only — a `type:feature` story is never this case,
     step 4): update the ticket body with the decisions, set `status:spec-ready`.
   - Split into tasks: create the sub-issues, link them to the parent as native
     sub-issues, each labeled `level:task` plus its own `type:` as the architect assigned
     it in step 4 (never the parent's — `docs/pilot-process.md` §2 "`type:` is never
     inherited": `type:feature` or `type:tech` for a dev task, `type:e2e` for the one
     end-to-end task), and `status:spec-ready` + `priority:P0/P1/P2`. If the architect
     recorded a dependency between two of them, add a "Depends on #N" line to the
     dependent one's body (`docs/pilot-process.md` §2 "Dependencies between tasks of the
     same split" — this is also how the e2e task's own dependencies on every sibling get
     recorded). Set the parent's `status:` to `split` (its `level:` stays `level:story` —
     `level:epic` is reserved for a group of *stories*, not a story's own tasks; see
     `docs/pilot-process.md` §2), leave it open and unassigned as a tracker.
   - Won't-do (clear-cut only): label `status:wont-do`, close the issue. If it's not
     clear-cut, add `needs-human` with the subagent's reasoning instead (keep
     `status:scoping`) — don't close it.
   - Prerequisite tech ticket(s) flagged (in addition to whichever of the above
     applies): create each the same way a fresh `type:tech` need is created
     (`docs/pilot-process.md` §2), its own `level:story` — **never** as a sub-issue of the
     ticket being scoped, that would make it `level:task` instead. For each one, add a "Blocks #M"
     comment on the new ticket, and its own separate line in this ticket's body naming
     it — "Depends on #N" if the architect judged it a hard blocker (this exact phrase is
     what `docs/pilot-process.md` §4 "Blocked-by dependencies" mechanically gates future
     phases on), or a plain non-gating reference (e.g. "Related prerequisite: #N")
     otherwise. Several prerequisites means several separate lines, one `#N` each —
     never combined onto one line (`docs/pilot-process.md` §4).
   - Prerequisite bug ticket(s) flagged (in addition to whichever of the above applies):
     create each the same way, `type:bug` instead of `type:tech`
     (`docs/pilot-process.md` §2 "Prerequisite bug tickets (phase 2 or phase 4)") — same
     linking rules, always a hard blocker for this case (the discovering ticket cannot be
     finished until the bug is fixed).
6. Report the outcome (ticket(s) scoped/split, dependencies recorded, prerequisite
   ticket(s) spun out, or closed as won't-do) back to the human.
