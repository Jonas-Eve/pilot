# PILOT link — ticket types, levels and the tree

Read by `pilot-discovery`, `pilot-spec` and `pilot-qa` when they create, split or re-scope tickets, and cited by the link docs
for bug tickets, e2e tasks and epic descent. `.pilot/pilot-process.md` §3 holds the vocabulary (the labels and what they mean);
this is where each type originates and how the tree of epics, stories and tasks is built.

## Types and where each originates

Two independent axes classify every ticket, and neither is inherited from a parent to a
child — every ticket carries its own of each, assigned for what that specific ticket
actually is, never copied down a tree:

- **`type:`** (this section) — the *nature* of the work: `feature`, `tech`, `bug`, or
  `e2e`. Decides which agent(s) originate it and the phase-4 reviewer
  set (`.pilot/pilot-link-review-consensus.md`) for that ticket specifically.
- **`level:`** ("Three levels" below) — *depth* in the tree: `epic`, `story`, or `task`,
  capped at exactly these three, never deeper.

**Where a ticket originates depends on its `type:`, not a single shared entry point:**

- **`type:feature`** — the only type that goes through Discovery. A human describes an
  idea in free text to `/pilot-discovery`; the PM turns it into one or more user stories and
  the architect validates them (`.pilot/pilot-link-agent-dialogue.md` "Roster"), anticipating architecture (interfaces, infra
  shape) from the start rather than challenging a finished artifact later. Phase 4 review involves PM + tech lead by default (architect
  optional — its architecture decisions are made and cross-examined by the tech lead
  already, at spec time).
- **`type:tech`** — originates in one of two ways: **grouped** with a `type:feature`
  effort — Discovery's own PM-led, architect-validated discussion recognizes the idea needs a technical
  enabler alongside the product work and formalizes it as its own `type:tech` story under
  the same `level:epic` — or **standalone** — a human describes a purely technical need
  (infra, CI, security hardening, migration, no product framing) directly to
  `/pilot-spec`, with no ticket and no Discovery pass at all (`--tech`, or auto-detected):
  the architect formalizes it and, in the same continuous pass, splits/specs it alongside
  the tech lead (`.pilot/pilot-link-agent-dialogue.md` "Agent dialogue") — skipping Discovery entirely, since a purely
  technical need has no product judgment for a PM to weigh in on. Phase 4 review is tech
  lead alone (architect optional); the PM is never involved.
- **`type:bug`** — a defect in already-shipped code. **One single creation mechanism for
  the whole process**: `/pilot-spec --bug` (explicit or auto-detected), given no ticket —
  invoked directly by a human, or reused identically by `pilot-dev`/`pilot-e2e` (phase 3)
  or `pilot-qa` (phase 5) the instant they notice one mid-work
  (`.pilot/pilot-link-bug-tickets.md`). The architect alone classifies it: genuinely a
  code defect (created directly as `level:task`, `status:backlog` — dev-sized by nature,
  it never splits, and its spec still gets written by a later, ordinary `/pilot-spec`
  pass rather than in the same breath, so a dev/e2e/qa discovering one mid-work isn't
  blocked writing it); actually a different/new need in disguise (redirect to the
  ordinary `type:feature`/`type:tech` flow instead); or not actionable at all (create
  nothing — a bug has no later `status:wont-do` checkpoint to catch an invalid one).
  Never goes through Discovery. Phase 4 review is tech lead alone (architect optional),
  same as `type:tech` — the PM is never involved, even when found via an e2e test or
  phase-5 QA on a `type:feature` flow: a regression fix isn't a new product call.
- **`type:e2e`** — never created via Discovery (there's no raw "e2e need" a human reports
  from scratch) — always originated by the architect+tech lead's Spec dialogue, as the one
  mandatory end-to-end-test task every `type:feature` split produces
  (`.pilot/pilot-link-e2e-tasks.md`). Phase 4 review is PM + tech lead,
  the same set as `type:feature` — deliberately: reading the test is how the PM confirms
  the split, taken as a whole, actually validates the story's real end-to-end flow, not
  just its individual pieces.

A human never opens a raw, unformalized GitHub issue directly for any of these kinds of
ticket — every ticket is created by an agent, either Discovery (`type:feature`, and any
`type:tech` grouped with one) or Spec (a standalone `type:tech` need, a `type:bug` report,
or the split-off `type:e2e` task). The exceptions: a prerequisite tech or bug ticket the
architect originates itself, inline, mid-Spec pass (using Spec's own no-ticket entry —
"Prerequisite tech/bug tickets" below and `.pilot/pilot-link-bug-tickets.md`); and the PM's own
involvement when a `type:feature` story gets split — see "Three levels" below.

## `type:` is never inherited

Each task the architect+tech lead create when splitting a
story gets its own `type:`, assigned for what that specific task actually is — not copied
from the story above it. A `type:feature` story's split is typically a mix: one or more
`type:feature` tasks doing the user-facing work, sometimes a `type:tech` task alongside
them for a technical enabler the feature tasks depend on (a migration, a shared piece of
infra) — free to block the feature tasks the ordinary way ("Dependencies between tasks of
the same split" below) — and always exactly one `type:e2e` task
(`.pilot/pilot-link-e2e-tasks.md`). A purely technical enabler task shouldn't get a
PM review it has nothing useful to say about
(`pilot-review/SKILL.md` step 3), and a task's own `type:` is
what routes that review — not which story it happens to sit under.

## Three levels: `level:epic` → `level:story` → `level:task`

Every ticket also carries a `level:` label — depth in the tree, capped at exactly three,
never deeper: a `level:task` is never itself split into further tasks. If phase 2 (Spec)
discovers one is still too big while writing its spec, that's an estimation problem to fix
by re-splitting the *story* differently — never a reason for a fourth level. `level:epic`
is not the same thing as a story split into tasks — the two are different levels and easy
to conflate.

- **`level:epic`** — always `type:feature`; there is no `type:tech` epic. Groups several
  **`level:story`** tickets under a shared theme, for categorization — a `type:feature`
  story, or a `type:tech` story genuinely tied to that same feature effort (above), can
  both sit under it. Never itself scoped, spec'd, or built — no `status:` label. Created
  by Discovery's PM-led, architect-validated discussion, at the same moment a story would otherwise be
  created, the instant it's clear the idea can't be delivered as a single story. A
  standalone `type:tech` need originated directly via Spec's own entry point is never
  grouped under an epic — there's no Discovery pass to decide one's needed.
  **Auto-closes once every one of its current stories is closed**
  (`status:done` or `status:wont-do`) — same
  cascading-completion mechanism as a split story's tasks (`.pilot/pilot-process.md` §3), one level up, driven by
  GitHub's own sub-issue open/closed state rather than a `status:` label (it carries
  none). Closing it this way is terminal, exactly like a split story reaching
  `status:done`: an Epic's theme is defined by the stories ever linked under it, and once
  every one of them is done or wont-do, that theme is realized. Further work in the same
  area becomes a new Epic — never a story added back into a closed one.
- **`level:story`** (`type:feature`/`type:tech`, `status:backlog` at creation — never
  `type:bug`, which is always `level:task` directly, below) — one functional or technical
  unit. It always goes through Spec on its own, where the architect+tech lead decide
  whether it needs splitting into tasks.
- **`level:task`** — normally Spec splits a story into dev-sized tasks; the story
  that got split then gets `status:split` instead (`.pilot/pilot-process.md` §3) — it is still just a `level:story`,
  one level below an Epic, not an Epic itself. Split along vertical slices (each task
  delivers a coherent, ideally independently shippable/testable unit) rather than by
  technical layer — a front-end-only or back-end-only task is rarely reviewable or
  testable on its own, unless the two are genuinely decoupled (e.g. a backend API meant to
  be consumed later, independently).
  - **`type:tech` story**: splitting is still a judgment call — "it's fine for it not to"
    ("Scoping an already-created story" in `pilot-architect.md`), a well-scoped story
    can carry itself through phase 3 (Dev) as a single ticket, `level:story` the whole way,
    never split into `level:task`s.
  - **`type:bug` ticket: always `level:task` directly, never split, no parent.** The one
    exception to "Spec splits a story into tasks" above: dev-sized by nature, so
    it's created directly as `level:task`, `status:backlog` — the
    one place `level:task` exists standalone. Classified once, at the point it's reported
    or discovered ("Types and where each originates"; `.pilot/pilot-link-bug-tickets.md`), never in a later pass.
  - **`type:feature` story: splitting is never optional.** A feature story always ends up
    `status:split` with **at least two** tasks — one or more tasks doing the dev work
    (typically `type:feature`, sometimes mixed with a `type:tech` enabler, above) plus
    exactly one `type:e2e` task — never a single unsplit ticket carried through Dev
    directly. See `.pilot/pilot-link-e2e-tasks.md` for why, and `.claude/skills/pilot-qa/SKILL.md` "Phase 5 — Human QA" for
    what this makes possible once every task is done. The architect's real judgment for a
    feature story is how many tasks it needs and what each one's own `type:` should be —
    never *whether* to split at all.
  Either way, **for a `type:feature` story**, the PM is also invoked to check the proposed
  `type:feature` tasks still collectively cover the original story's acceptance criteria
  before it's finalized (excluding any `type:tech` or `type:e2e` task from that check —
  neither implements a criterion) — a split that quietly drops part of what the story
  promised would otherwise only surface in phase 4, after everything's already been built.

**Creating or reusing an Epic** (Discovery): before creating a new Epic,
check open `level:epic` issues (always `type:feature`) for one that already fits the
idea/need by theme — reuse it (attach the new story/stories as sub-issues of it) rather
than creating a duplicate. Only create a new Epic when no existing one fits and the idea
genuinely can't be delivered as one story.

**Spec still claims and works exactly one ticket per invocation** (`.pilot/pilot-process.md` §4 "Claim
Protocol"). But nothing stops the architect/tech lead from *reading* related tickets for
context while working that one ticket: the parent Epic (if any), sibling stories under it,
or anything already linked via "Blocks #M"/"Depends on #N" or a sub-issue relationship —
this is read-only context-gathering, not a second claim.

## Prerequisite tech/bug tickets (distinct from a split's tasks)

A task (above) is part of the *same* ticket's tree — its own `level:task` and `type:`
("Types and where each originates"), never a separate root. A **prerequisite** is the opposite case: while
splitting/speccing a `type:feature` (or `type:tech`) ticket, the architect discovers it
depends on technical work that isn't part of it at all — infra, CI, a shared library, a
migration — exactly the kind of thing that would normally come in as a standalone
`type:tech` need (above), just discovered from inside another ticket's Spec pass instead
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
that a `type:feature` task needs first ("Types and where each originates"). Unlike a prerequisite, this is *within*
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
  to keep the link visible — never a sub-issue, same reasoning as a prerequisite ticket, "Types and where each originates").
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
  1. Propose the new task(s) the same way as any split ("Three levels"), and write
     each one's spec in the same pass.
  2. Propose exactly one new `type:e2e` task for *this round* — never reopen or amend the
     original, already-`status:done` e2e task. Title it distinctly (e.g. "E2E: <story
     summary> (round 2)") and depend only on this round's new task(s). Its spec should
     say explicitly that its job is to *extend* the existing e2e test asset the
     original task wrote, not duplicate coverage from scratch.
  3. Run the PM coverage check ("Types and where each originates") against this round's new `type:feature` tasks
     only — the original tasks were already checked at split time.
  4. Finalize exactly like any other split (`.pilot/pilot-process.md` §4 "Claim Protocol"): the story lands back on
     `status:split`, now tracking this round's new tasks instead.
  Once this round's new e2e task also reaches `status:done`, the story cascades to
  `status:qa` again exactly as before (`.pilot/pilot-process.md` §3 "Cascading completion") — the new behavior gets
  its own human QA pass in phase 5, same as the original.
- **`status:split`, original e2e task not yet done** — no special handling needed: the
  story hasn't finished its first round yet, so this is an ordinary re-scope. Add the new
  task(s) to the existing split and extend the *existing* (still-open) e2e task's
  dependencies to also cover them, rather than spinning up a second one.

This applies the same way to a `type:tech` story that did split (not every one does, "Three levels") — closed is just as terminal, `status:split` just as
reversible while it's still mid-flight — minus the e2e-task mechanics, which only ever
apply to `type:feature`.

---
