---
name: pilot-scope
description: "Phase 2 of PILOT (see .pilot/pilot-process.md): the architect agent takes an already-formalized ticket (type:feature or type:tech only — type:bug never reaches this phase, always created directly as a spec-ready task) and, in one pass, challenges it, then scopes it as-is or splits it into dev-sized tasks (level:task, each its own independent type: — never inherited) — judgment call for type:tech, mandatory for type:feature: one or more tasks (typically type:feature, sometimes a type:tech enabler) plus exactly one type:e2e task depending on every other task in the split. Also records dependencies (a prerequisite type:tech/type:bug ticket, and/or between split tasks), decides status:wont-do, or flags needs-human. For type:feature, the PM agent also checks the proposed type:feature tasks (excluding type:tech/type:e2e siblings) against the story's acceptance criteria before finalizing. Defaults to pair mode (walks the decomposition with a live human, checkpointing into the ticket); --auto finalizes straight away (for a scheduled cron Routine, which has no live human). Also resumes a needs-human ticket once cleared, resumes a mid-pair ticket with --resume <issue number>, reclaims a type:feature story at status:qa/status:in-qa for a new round (status:in-scope then status:split — refuses on status:done, which needs a new ticket), and with no argument picks up fresh or resumable work (e.g. --auto from a cron Routine), skipping on-hold or unresolved-'Depends on #N' tickets. An optional --multi <N> runs N architects independently on the one claimed ticket instead of one and reconciles them into a single proposal, escalating to needs-human on genuine, unresolved disagreement (see .pilot/pilot-link-multi-consensus.md). Use for scoping/decomposing an already-created type:feature/type:tech ticket — not for formalizing a new need (that's /pilot-story)."
argument-hint: "<issue number, optional — picks the next fresh/resumable status:backlog ticket if omitted> [--auto] [--multi [N]] | <issue number> --resume"
---

# PILOT — Phase 2: Investigate

Read `.pilot/pilot-process.md` before running this if you haven't — it's the source of
truth for labels, states, and the claim protocol; this skill covers only the
mechanics of running phase 2.

## Steps

1. Determine the input:
   - `--resume <issue>`: must be `status:in-scope`, assigned, **no** `needs-human`/
     `on-hold` — a ticket left mid-pair. Follow `.pilot/pilot-process.md` §4 "Resuming
     an orphaned claim", skipping step 2's claim (already claimed). If it
     doesn't match, report and stop.
   - No `--resume`, `status:in-scope`, **no** `needs-human`/`on-hold`, carrying
     `can-resume` → a resume, not a fresh claim. Follow
     `.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket", skipping step 2's
     claim.
   - No `--resume`, `status:in-scope`, assigned, **no** `needs-human`/`on-hold`, and
     no `can-resume` → looks like a ticket left mid-pair. Report and ask the human to
     re-run with `--resume`, or add `can-resume` themselves.
   - `status:in-scope` still carrying `needs-human` or `on-hold` → not resolved yet,
     report and stop.
   - `level:task` → phase 2 only scopes `level:story` tickets, never a task (a task
     is the *output* of scoping, §2 "Three levels"). Report and point at the task's
     parent story. Never claim it.
   - `type:bug` → never reaches phase 2: always created directly as `level:task`,
     `status:spec-ready` (`.pilot/pilot-process.md` §2 "Three levels"). Report and
     point at `/pilot-spec`. Never claim it.
   - GitHub issue **closed** (`status:done`/`status:wont-do`, the only two closed
     states) → terminal, refuse (`.pilot/pilot-process.md` §2 "Re-scoping a
     `type:feature` story after its split is done"): report it's closed, point at
     opening a new ticket instead (a plain "Extends #N" reference suffices). Never
     claim it. Check the issue's actual open/closed state, not just the `status:`
     label — `status:qa`/`status:in-qa` below are still *open*, which is what
     distinguishes them from this.
   - `status:qa` (unclaimed) or `status:in-qa` (assigned, any owner) → a valid
     re-scope entry point, not an ordinary claim (`.pilot/pilot-process.md` §2
     "Re-scoping a `type:feature` story after its split is done"). Read the ticket,
     its parent Epic (if linked), and its tasks (which are `status:done`, including
     the original e2e task) for context, comment why (new scope found; any
     `status:in-qa` session set aside),
     then claim it — overwrite the assignee if any (same non-conflict exception a
     `status:changes-requested` reclaim gets, below) and set `status:in-scope` —
     before continuing to step 3, passing that extra context alongside the ticket
     body. Skip step 2, already claimed here.
   - Otherwise → an existing, open `level:story` (`type:feature`/`type:tech`) being
     scoped/re-scoped. Read it (`mcp__github__issue_read`) plus its parent Epic (if
     linked) and anything referenced via "Blocks #M"/"Depends on #N" or a sub-issue
     relationship, as context. If `level:epic`, there's nothing to scope on the epic
     itself — stop and point at its stories.
   - No argument → per `.pilot/pilot-process.md` §4 "Picking the next ticket...": the
     merged pool of unclaimed `status:backlog` (fresh) and `status:in-scope` carrying
     `can-resume` (resumable — a mid-pair ticket is never in this pool, only reachable
     via `--resume <issue>`), highest `priority:` then oldest first. What a scheduled
     cron Routine drives with `--auto` (`.pilot/pilot-process.md` §4 "Scheduled
     sweeps").
2. **Claim** the ticket per `.pilot/pilot-process.md` §4: set assignee + `status:in-scope`,
   re-read to confirm the claim held.
3. Call `Agent` with `subagent_type: "pilot-architect"` — once, or, with `--multi <N>`,
   N times in parallel plus one further reconciliation call
   (`.pilot/pilot-link-multi-consensus.md` — invalid combined with `--resume`) that reads
   the same `.pilot/pilot-task-scope-story.md` (its own "Reconciling an ensemble" section
   is what tells it this is a comparison, not a fresh scope) plus all N raw proposals, and,
   on a retry round, the prior round's disagreement summary too. Read
   `.pilot/pilot-task-scope-story.md`
   and pass its content as part of the prompt, plus `.pilot/pilot-link-bug-tickets.md` in
   full (the classify/originate mechanic for step 5's "Prerequisite (bug)" case — the task
   doc covers the phase-2-specific delta itself) — plus only what phase 2 needs beyond
   that: the ticket's current body (including, if resuming, the comment thread's
   resolution per §4), its parent Epic/linked tickets if any, pointers
   to this project's own coding standards/security conventions and architecture docs
   (identity/tenancy/security boundaries, target system design, if documented) —
   plus, for a `status:qa`/`status:in-qa` reclaim (step 1), which existing tasks are
   already `status:done` from the earlier round, including the e2e one. Not the
   conversation history. With `--multi`, if reconciliation still can't resolve a
   genuine disagreement after its one retry round, stop here: add `needs-human` with
   every round's differing positions quoted verbatim
   (`.pilot/pilot-link-multi-consensus.md`) — don't continue to step 4.
4. The subagent (or, with `--multi`, the reconciled proposal) returns one of:
   - `type:tech`: a single scoped body (no split, with its `priority:` reconfirmed or
     revised from phase 1), or a set of proposed tasks (split, judgment call) each with
     security/architecture decisions, dependencies, and its own suggested priority.
   - `type:feature`: always a set of proposed tasks — one or more dev tasks (each
     its own `type:feature` or `type:tech`, whichever fits — `.pilot/pilot-process.md`
     §2 "`type:` is never inherited"), plus exactly one flagged as the mandatory
     end-to-end-test task, its own `type:e2e` (`.pilot/pilot-link-e2e-tasks.md`),
     dependent on every other task in the set. Never a
     single unsplit body.
   - Or, for either: a verdict that it shouldn't be built at all.
   Independently, it may also flag one or more **prerequisite** needs — `type:tech`
   (`.pilot/pilot-process.md` §2 "Prerequisite tech tickets") or `type:bug`
   (`.pilot/pilot-link-bug-tickets.md`) — and whether each is a hard blocker.
4a. **If `type:feature`** (always split, step 4): call `Agent` again with
    `subagent_type: "pilot-pm"`. Read `.pilot/pilot-task-check-split-coverage.md` and
    pass its content as part of the prompt, plus the story's acceptance criteria and
    **only the `type:feature` tasks** — excluding `type:tech`/`type:e2e`
    (`.pilot/pilot-link-e2e-tasks.md` — neither covers a
    criterion: a tech task is an enabler, the e2e task verifies what its
    `type:feature` siblings already cover). If the PM blocks with a gap, feed it back
    to the architect and repeat until approved, before step 4b. Runs regardless of
    `--auto`/pair — a validation step, not a human checkpoint.
4b. **Unless `--auto`** (`.pilot/pilot-process.md` §4 "Interaction modes" — pair is
    default): don't finalize yet. Show the human the proposed decomposition — split
    or not, any e2e task, security/architecture decisions, dependencies, wont-do
    verdict, prerequisite need(s) and blocker status, the PM's coverage check if
    run — as a normal reply, wait for their response, feed it back to the architect
    (and PM, if applicable) — repeat until approved. Write each approved checkpoint
    into the ticket right away (a comment, or a partial `issue_write`) rather than
    holding it in-conversation — this is what `--resume` picks back up if the
    session ends first (`.pilot/pilot-process.md` §4 "Resuming an orphaned
    claim"). Requires a live human; a scheduled Routine must pass `--auto`. Once
    approved, continue to step 4c — its GitHub write is then just the remaining
    piece (final labels, unwritten sub-issues), since earlier checkpoints were
    already saved.
4c. **Final consolidation pass** (`.pilot/pilot-process.md` §4 "Interaction modes"):
    before applying anything, have the architect re-read the ticket (and every
    proposed task, if split) as a whole, not just the latest delta, fixing anything
    that no longer holds together across rounds (an earlier security decision at
    odds with a later one, a gap no checkpoint's author noticed). Do this for both
    pair and `--auto` — `--auto` has no rounds to reconcile but still benefits from
    one coherence read before writing.
5. Apply the result (`mcp__github__issue_write`, `mcp__github__sub_issue_write`):
   - No split (`type:tech` only — a `type:feature` story is never this case, step
     4): update the ticket body with the decisions, set `status:spec-ready`, and write
     the reconfirmed/revised `priority:` from step 4 (still the ticket's own — it's
     still the one leaf, `.pilot/pilot-process.md` §3).
   - Split into tasks: create the sub-issues, link to the parent as native
     sub-issues, each labeled `level:task` plus its own `type:` as the architect
     assigned in step 4 (never the parent's — `.pilot/pilot-process.md` §2 "`type:` is
     never inherited": `type:feature`/`type:tech` for a dev task, `type:e2e` for the
     end-to-end one), and `status:spec-ready` + its own `priority:P0/P1/P2`. For a
     recorded dependency between two tasks, add a "Depends on #N" line to the
     dependent one's body (`.pilot/pilot-process.md` §2 "Dependencies between tasks of
     the same split" — also how the e2e task's dependencies on every sibling get
     recorded). Set the parent's `status:` to `split` (its `level:` stays
     `level:story` — `level:epic` groups *stories*, not a story's own tasks,
     `.pilot/pilot-process.md` §2) and remove its own `priority:` label
     (`.pilot/pilot-process.md` §3 — superseded by its tasks'), leave it open and
     unassigned as a tracker.
   - Won't-do (clear-cut only): label `status:wont-do`, close the issue. If not
     clear-cut, add `needs-human` with the subagent's reasoning instead (keep
     `status:in-scope`) — don't close it.
   - Prerequisite tech ticket(s) flagged (alongside whichever of the above
     applies): create each the way a fresh `type:tech` need is created
     (`.pilot/pilot-process.md` §2), its own `level:story` — **never** a sub-issue of
     the ticket being scoped (that would make it `level:task` instead). Add a
     "Blocks #M" comment on each new ticket, and a separate line in this ticket's
     body naming it — "Depends on #N" if the architect judged it a hard blocker (the
     exact phrase `.pilot/pilot-process.md` §4 "Blocked-by dependencies" mechanically
     gates future phases on), else a plain non-gating reference (e.g. "Related
     prerequisite: #N"). Several prerequisites means several separate lines, one
     `#N` each — never combined (`.pilot/pilot-process.md` §4).
   - Prerequisite bug ticket(s) flagged (alongside whichever of the above applies):
     create each directly as `type:bug`, `level:task`, `status:spec-ready` — never
     `level:story`/`status:backlog` (`.pilot/pilot-process.md` §2 "Three levels" — a
     bug skips phase 2), never a sub-issue (`.pilot/pilot-process.md` §2 "Prerequisite
     bug tickets (phase 2, phase 4, or phase 6)") — same linking rules, always a
     hard blocker here (the discovering ticket can't finish until the bug is
     fixed).
   - Either prerequisite case above, when step 1 found a parent Epic for the ticket
     being scoped: also `mcp__github__add_issue_comment` on that Epic naming the
     blocking relationship (`.pilot/pilot-process.md` §2 "Prerequisite tech tickets")
     — skip this when the scoped ticket has no parent Epic.
6. Report the outcome (ticket(s) scoped/split, dependencies recorded, prerequisite
   ticket(s) spun out, or closed as won't-do) back to the human.
