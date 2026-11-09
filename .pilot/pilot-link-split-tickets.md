# PILOT link — prerequisites, dependencies and re-scoping when splitting a story

Read by `pilot-spec` and the architect's scoping duty (`.pilot/pilot-task-scope-story.md`), and cited by the link docs for bug tickets and epic descent.
Ticket types and levels are `.pilot/pilot-link-ticket-tree.md`.

## Prerequisite tech/bug tickets (distinct from a split's tasks)

A task (`.pilot/pilot-link-ticket-tree.md` "Three levels") is part of the *same* ticket's tree — its own `level:task` and `type:`
(`.pilot/pilot-link-ticket-tree.md` "Types and where each originates"), never a separate root. A **prerequisite** is the opposite case: while
splitting/speccing a `type:feature` (or `type:tech`) ticket, the architect discovers it
depends on technical work that isn't part of it at all — infra, CI, a shared library, a
migration — exactly the kind of thing that would normally come in as a standalone
`type:tech` need (`.pilot/pilot-link-ticket-tree.md` "Types and where each originates"), just discovered from inside another ticket's Spec pass instead
of being reported directly. Spec is the one place this still originates a brand-new
ticket itself — the architect already has full context loaded for this pass, so it
creates the prerequisite inline, writing it the same way `.pilot/pilot-task-formalize-tech-need.md`
describes for a standalone need — never the live human drafting loop that doc's own
no-ticket entry adds on top (`pilot-spec/SKILL.md` step 1a): a human live in this pass, if
any, is there for the ticket actually being worked, not to co-draft this one. Land it
directly at `status:backlog` for a later, separate `/pilot-spec` run to pick up, same as
any other prerequisite.

The same applies to a prerequisite **bug** discovered mid-Spec: classify it first
(`.pilot/pilot-link-bug-tickets.md`), and if genuine, create it the same way a standalone
bug is created via Spec's own `--bug` entry.

The architect creates the tech prerequisite — always exactly one `level:story`, standalone,
never grouped under an Epic (there is no `type:tech` epic; if it turns out too big for one
story, that's its own future Spec pass's split judgment call, not a reason to create
several here) — **never** as a sub-issue of the ticket being worked: a
sub-issue would make it `level:task` and tie its lifecycle to the parent's split-tracking,
which is wrong for a ticket that is its own root and goes through Spec/Dev/Review
independently. Instead, link the two directions with a plain issue reference: a comment on
the new ticket ("Blocks #M") pointing back, and a line in the body of the ticket being
worked naming it. A prerequisite bug ticket is `level:task` directly (never `level:story`)
and likewise never a sub-issue. Never `sub_issue_write` for either relationship.

If the ticket being worked itself belongs to a `level:epic`, also comment on that Epic
naming the blocking relationship (e.g. "Story #<worked> is blocked by prerequisite #<new>")
— the sub-issue list only shows the epic's own stories, never an external prerequisite, so
without this an epic's own view never reveals that one of its stories is waiting on
something outside it. Skip this when the worked ticket has no parent Epic.

Whether the prerequisite is a **hard blocker** — the ticket genuinely can't be built until
it lands — decides the exact wording of that line, because `.pilot/pilot-process.md` §4 "Blocked-by
dependencies" below mechanically gates a ticket on the literal phrase, not on a label:
- Hard blocker → write "Depends on #N". Nothing needs to be lifted by hand: `.pilot/pilot-process.md` §4's gate
  excludes the ticket from every phase's candidate pool for as long as #N stays open, and
  it becomes a normal candidate again on its own, the next time that phase runs, the
  instant #N closes. A prerequisite bug is always a hard blocker.
- Not a hard blocker (the ticket can proceed in parallel, or the prerequisite is a
  nice-to-have) → write a plain, non-gating reference instead — e.g. "Related
  prerequisite: #N" — informational only, nothing reads or excludes on this wording.

Don't reach for `on-hold` (`.pilot/pilot-process.md` §3) for this either way: its manual-lift requirement is the
wrong tool for a wait that resolves itself in a specific, mechanically checkable way.
Reserve `on-hold` for a pause with no single ticket to point at.

The prerequisite ticket itself is nothing special once created: a normal `type:tech`
story, `status:backlog`, moving through Spec/Dev/Review like any other (or, for a
prerequisite bug, `level:task`/`status:backlog` straight into a later Spec pass). The only
place its existence matters downstream is the gate check on whatever ticket names it (`.pilot/pilot-process.md` §4
below).

## Dependencies between tasks of the same split

Distinct from a prerequisite (above, a separate root ticket): when Spec splits a story,
two of its own tasks can still depend on each other — e.g. a front-end task that
consumes an API a back-end task in the same split creates, or a `type:tech` enabler task
that a `type:feature` task needs first (`.pilot/pilot-link-ticket-tree.md` "Types and where each originates"). Unlike a prerequisite, this is *within*
the same tree, both tasks `level:task` under the same `level:story` parent regardless of
each one's own independent `type:`. Record it with the same "Depends on #N" phrase (`.pilot/pilot-process.md` §4
"Blocked-by dependencies") on the dependent task, at split time — the mechanism already
gates on the literal phrase regardless of whether the referenced ticket is a separate root
or a sibling.

## Re-scoping a `type:feature` story after its split is done

Spec only ever splits a `level:story` — never a `level:task` (a task is the *output* of
splitting, not something split again itself; if a task turns out to need further
breakdown, that's re-splitting the *story*, not the task). Within that, `/pilot-spec`
handles an already-once-split `level:story` differently depending on exactly how finished
it is:

- **Closed (`status:done` or `status:wont-do`)** — terminal, full stop. `/pilot-spec`
  refuses to claim it: report that it's already closed and stop, no exception — nothing
  else in PILOT ever moves a ticket backward out of a terminal state. The new work gets
  its own story instead (a plain, non-gating "Extends #N" reference in its body is enough
  to keep the link visible — never a sub-issue, same reasoning as a prerequisite ticket, "Prerequisite tech/bug tickets").
- **`status:qa` or `status:in-qa`** — still reversible, because nothing terminal has
  happened yet: the cascade only just mechanically set `status:qa` the moment the e2e task
  closed, and no human has confirmed anything (`status:in-qa` is one step further — a
  `/pilot-qa` session may even be live — but still short of a verdict). Claiming an issue
  number in either status is a valid, explicit `/pilot-spec` entry point (never part of a
  bare pool) — an existing `status:in-qa` assignee doesn't block this claim, the
  architect+tech lead's claim simply overwrites it. Post a comment explaining why, then
  claim it into `status:in-spec` — the one deliberate, phase-2-only backward transition in
  the whole state machine. From here it's an ordinary Spec pass, just with extra context
  (which tasks, including the original e2e one, are already `status:done` from the
  earlier round):
  1. Propose the new task(s) the same way as any split (`.pilot/pilot-link-ticket-tree.md` "Three levels"), and write
     each one's spec in the same pass.
  2. Propose exactly one new `type:e2e` task for *this round* — never reopen or amend the
     original, already-`status:done` e2e task. Title it distinctly (e.g. "E2E: <story
     summary> (round 2)") and depend only on this round's new task(s). Its spec should
     say explicitly that its job is to *extend* the existing e2e test asset the
     original task wrote, not duplicate coverage from scratch.
  3. Run the PM coverage check (`.pilot/pilot-link-ticket-tree.md` "Types and where each originates") against this round's new `type:feature` tasks
     only — the original tasks were already checked at split time.
  4. Finalize exactly like any other split (`.pilot/pilot-process.md` §4 "Claim Protocol"): the story lands back on
     `status:split`, now tracking this round's new tasks instead.
  Once this round's new e2e task also reaches `status:done`, the story cascades to
  `status:qa` again exactly as before (`.pilot/pilot-link-cascade.md` "Cascading completion") — the new behavior gets
  its own human QA pass in phase 5, same as the original.
- **`status:split`, original e2e task not yet done** — no special handling needed: the
  story hasn't finished its first round yet, so this is an ordinary re-scope. Add the new
  task(s) to the existing split and extend the *existing* (still-open) e2e task's
  dependencies to also cover them, rather than spinning up a second one.

This applies the same way to a `type:tech` story that did split (not every one does, `.pilot/pilot-link-ticket-tree.md` "Three levels") — closed is just as terminal, `status:split` just as
reversible while it's still mid-flight — minus the e2e-task mechanics, which only ever
apply to `type:feature`.

---
