# PILOT — Ticket Pipeline (Simplified Multi-Agent Process)

PILOT is this repo's lightweight, in-house multi-agent ticket process: specialized agent
personas take a piece of work from a raw idea to a merged PR, each phase running in its
own isolated agent context (§5) rather than accumulating the whole ticket's history.

**P**lan → **I**nvestigate → **L**ay out → **O**perate → **T**est & validate, plus a sixth
phase, Human QA (§7), mandatory for `type:feature` only — a manual acceptance check once
every task is merged, before the story reaches `status:done`. `type:tech`/`type:bug`
tickets never go through it.

This document is the source of truth: the state machine, GitHub label conventions, claim
protocol, and how the phases fit together. The agent personas
(`.claude/agents/pilot-*.md`) and skills (`.claude/skills/*/SKILL.md`) reference this file
rather than repeating it — keep this document accurate first, then bring those in line.

---

## 0. Prerequisites & Quickstart

**These GitHub labels must exist before any PILOT skill runs** — no skill creates them on
the fly, and applying a label that doesn't exist fails the API call outright:

`type:feature`, `type:tech`, `type:bug`, `type:e2e`, `level:epic`, `level:story`,
`level:task`, `priority:P0`, `priority:P1`, `priority:P2`,
`status:draft`, `status:backlog`, `status:scoping`, `status:spec-ready`, `status:in-spec`,
`status:dev-ready`, `status:in-dev`, `status:review-ready`, `status:in-review`,
`status:changes-requested`,
`status:approved`, `status:wont-do`, `status:split`, `status:qa`, `status:in-qa`,
`status:done`, `needs-human`, `on-hold`.

Each phase is a Claude Code slash command, run from a session with read/write access to
this repo's issues and PRs. `/pilot-story` and `/pilot-qa` never run except because
something sent their exact command literally, human or scheduled Routine (§4 "Scheduled
sweeps") — the other four phases can also be invoked without one, but every phase, whichever
way it's invoked, only ever acts on a ticket that's actually, currently in its own pre-claim
`status:` (§4 "Claim Protocol"); nothing here infers which phase a ticket belongs to or
invents work. Bare, no-argument commands are what make the scheduled case useful —
see `docs/pilot-process-companion.md` for example invocations of each command; there's no
single command that runs all six phases end to end, drive the pipeline one phase at a
time, per ticket.

Every phase skill also runs bare, with **no argument at all** — it then works its normal
pool of fresh candidates (its own pre-claim `status:`) *and* its own `needs-human`/
`on-hold` tickets whose flag has since been cleared (§4 "Picking the next ticket..." and
"Scheduled sweeps"). This is what a cron Routine calls on a timer — with `--auto` added for
`/pilot-scope`, `/pilot-spec`, `/pilot-dev`, and `/pilot-review`, all four of which default
to pair and need that flag to run unattended (§4 "Interaction modes").
`/pilot-story` and `/pilot-qa` are pair-only and are never Routine-driven at all.

---

## 1. The Six Phases

| # | Phase | Skill | Agent | Produces |
|---|-------|-------|-------|----------|
| 1 | Plan | `/pilot-story` | `pilot-pm` (`type:feature`) or `pilot-architect` (`type:tech`/`type:bug`) — auto-detected, `--tech`/`--bug` to declare it upfront | A `level:story` (feature/tech), or, for a genuine `type:bug`, a `level:task` ready to build directly — a bug skips phase 2 (§2 "Three levels"). Either way `status:draft` until human approval, then `status:backlog` (story) or `status:spec-ready` (bug) |
| 2 | Investigate | `/pilot-scope` | `pilot-architect` — plus `pilot-pm` when a `type:feature` story is split | The story scoped as-is or split into dev-sized tasks — mandatory for `type:feature`, a size judgment call for `type:tech`; `type:bug` never reaches this phase at all (§2 "Three levels") |
| 3 | Lay out | `/pilot-spec` | `pilot-techlead` | A technical spec written into the ticket (the test plan itself, for an e2e task) |
| 4 | Operate | `/pilot-dev` | `pilot-dev`, or `pilot-e2e` instead for a `type:e2e` task | An implementation + pull request (following `.github/pull_request_template.md`) |
| 5 | Test & validate | `/pilot-review` | `pilot-pm` + `pilot-architect` + `pilot-techlead` (feature/e2e) or `pilot-architect` + `pilot-techlead` (tech/bug) | A submitted GitHub PR review (Approve/Request changes/Comment): `status:approved`, or blocking points (`needs-human`, plus `status:changes-requested` if code-level) — merges only with `--merge`, otherwise a human merges by hand |
| 6 | Human QA (`type:feature` only) | `/pilot-qa` | `pilot-qa` | A human-confirmed `status:done` once every task has merged, or a `needs-human` flag with what failed (§7) |

Each phase skill is invoked on its own (`/pilot-scope 123`, etc.), as its own isolated
agent call (see §5), one phase at a time.

## 2. Ticket Types And Levels

Two independent axes classify every ticket, and neither is inherited from a parent to a
child — every ticket carries its own of each, assigned for what that specific ticket
actually is, never copied down a tree:

- **`type:`** (this section) — the *nature* of the work: `feature`, `tech`, `bug`, or
  `e2e`. Decides which agent handles phase 1 (where applicable) and the phase-5 reviewer
  set (§6) for that ticket specifically.
- **`level:`** ("Three levels" below) — *depth* in the tree: `epic`, `story`, or `task`,
  capped at exactly these three, never deeper.

Every ticket is created in phase 1 — `type:` decides only which agent phase 1 calls,
never whether phase 1 runs at all. What comes *after* phase 1 does depend on `type:`: a
`type:feature`/`type:tech` story goes on to phase 2 (decomposition), a `type:bug` skips
straight to phase 3 ("Three levels" below). Phase 1 itself is purely about identifying and
formalizing what the need actually is — never about dependencies, prerequisites, or
splitting; that's entirely phase 2's job, for the tickets that have one (below):

- **`type:feature`** — a human describes an idea in free text to `/pilot-story`; the PM
  agent formalizes it into a user story. Phase 5 review involves all three agents (PM
  checks product fit against the story's acceptance criteria).
- **`type:tech`** — a human describes a technical need in free text to the same
  `/pilot-story`; the architect agent formalizes it into a story (or several) in place of
  the PM — same act either way, just a different agent. Phase 5 review is architect + tech
  lead only; the PM is never involved.
- **`type:bug`** — a defect in already-shipped code: reported via `/pilot-story --bug`, or
  discovered inline while another ticket is being scoped, implemented, or manually
  confirmed in phase 6 (the architect, dev/`pilot-e2e`, or `pilot-qa` — "Prerequisite bug
  tickets" below). Classified first by whoever finds it: genuinely a code defect (created
  directly as `level:task`, skipping phase 2 outright — "Three levels" below has the
  mechanics); actually a different/new need in disguise (handled as `type:feature`/
  `type:tech` instead); or not actionable at all (create nothing, the same "out of scope"
  outcome any raw need gets — a bug has no later `status:wont-do` checkpoint to catch an
  invalid one). Phase 5 review is architect + tech lead only, same as `type:tech` — the PM
  is never involved, even when found via an e2e test or phase-6 QA on a `type:feature`
  flow: a regression fix isn't a new product call.
- **`type:e2e`** — never created via phase 1 (there's no raw "e2e need" a human reports
  from scratch) — always originated by the architect during phase 2, as the one mandatory
  end-to-end-test task every `type:feature` split produces ("End-to-end test tasks"
  below). Phase 5 review is PM + architect + tech lead, the same set as `type:feature` —
  deliberately: reading the test is how the PM confirms the split, taken as a whole,
  actually validates the story's real end-to-end flow, not just its individual pieces.

**Which agent phase 1 calls is auto-detected from the need, not asked for explicitly.**
`/pilot-story` is pair-only (§4 "Interaction modes"), so a wrong guess is never silent —
the human sees which agent picked it up and corrects it live before anything is created.
Pass `--tech` or `--bug` to skip detection and declare the need's type upfront (there is
no `--feature` equivalent; feature is the default read of an undecorated need).

A human never opens a raw, unformalized GitHub issue directly for any of these kinds of
ticket — every ticket is created by an agent during phase 1 (PM for `type:feature`,
architect for `type:tech`/`type:bug`; `type:e2e` is never phase-1-created at all). Phase 2
(`/pilot-scope`) always uses the architect regardless of `type:` — challenging/decomposing
an already-created story is a technical judgment call either way, never the PM's on its
own. The exceptions: a prerequisite tech or bug ticket the architect originates itself,
inline, mid-phase-2 scoping pass, or the same for a bug specifically that dev/`pilot-e2e`
originates mid-phase-4 or `pilot-qa` originates mid-phase-6 — see "Prerequisite tech
tickets" and "Prerequisite bug tickets" below; and the PM's own involvement when a
`type:feature` story gets split — see "Three levels" below.

**`type:` is never inherited.** Each task the architect creates when splitting a story
gets its own `type:`, assigned for what that specific task actually is — not copied from
the story above it. A `type:feature` story's split is typically a mix: one or more
`type:feature` tasks doing the user-facing work, sometimes a `type:tech` task alongside
them for a technical enabler the feature tasks depend on (a migration, a shared piece of
infra) — free to block the feature tasks the ordinary way ("Dependencies between tasks of
the same split" below) — and always exactly one `type:e2e` task ("End-to-end test tasks"
below). A purely technical enabler task shouldn't get a PM review it has nothing useful to
say about (§6 "Reviewer set"), and a task's own `type:` is what routes that review —
not which story it happens to sit under.

### Three levels: `level:epic` → `level:story` → `level:task`

Every ticket also carries a `level:` label — depth in the tree, capped at exactly three,
never deeper: a `level:task` is never itself split into further tasks. If phase 3
discovers one is still too big, that's an estimation problem to fix by re-spec'ing it or
re-splitting the *story* differently — never a reason for a fourth level. `level:epic` is
not the same thing as a story split into tasks — the two are different levels and easy to
conflate. Symmetric for both entry points:

- **`level:epic`** (alongside `type:feature` or `type:tech` — never `type:bug`, which is
  never grouped, "Prerequisite bug tickets" below) — groups several **`level:story`**
  tickets under a shared theme, for categorization. Never itself scoped, spec'd, or
  built — no `status:` label. Created by the PM (`type:feature`) or the architect
  (`type:tech`) during phase 1, at the same moment a story would otherwise be created, the
  instant it's clear the idea can't be delivered as a single story. **Stays open and is
  closed by hand, always** — unlike a split story's tasks (a fixed set decided once, §3
  "Cascading completion"), new stories can be added to an Epic at any point, so its
  completeness is never something PILOT can prove on its own.
- **`level:story`** (`type:feature`/`type:tech`, `status:backlog` at creation — never
  `type:bug`, which is always `level:task` directly, below) — one functional or technical
  unit, exactly what phase 1 always produces for these two types. Whether or not it
  belongs to an Epic, it always goes through phase 2 on its own, where the architect
  decides whether it needs splitting into tasks.
- **`level:task`** — normally the architect splits a story into dev-sized tasks; the story
  that got split then gets `status:split` instead (§3) — it is still just a `level:story`,
  one level below an Epic, not an Epic itself. Split along vertical slices (each task
  delivers a coherent, ideally independently shippable/testable unit) rather than by
  technical layer — a front-end-only or back-end-only task is rarely reviewable or
  testable on its own, unless the two are genuinely decoupled (e.g. a backend API meant to
  be consumed later, independently).
  - **`type:tech` story**: splitting is still a judgment call — "it's fine for it not to"
    (§2 "Scoping an already-created story" in `pilot-architect.md`), a well-scoped story
    can carry itself through phases 3-4 as a single ticket, `level:story` the whole way,
    never split into `level:task`s.
  - **`type:bug` ticket: always `level:task` directly, never split, no parent.** The one
    exception to "the architect splits a story into tasks" above: dev-sized by nature, so
    it skips phase 2 entirely, created directly as `level:task`/`status:spec-ready` — the
    one place `level:task` exists standalone. Classified once, at the point it's reported
    or discovered (§2 above; "Prerequisite bug tickets" below), never in a later pass.
  - **`type:feature` story: splitting is never optional.** A feature story always ends up
    `status:split` with **at least two** tasks — one or more tasks doing the dev work
    (typically `type:feature`, sometimes mixed with a `type:tech` enabler, above) plus
    exactly one `type:e2e` task — never a single unsplit ticket carried through phases 3-4
    directly. See "End-to-end test tasks" below for why, and §7 "Phase 6 — Human QA" for
    what this makes possible once every task is done. The architect's real judgment for a
    feature story is how many tasks it needs and what each one's own `type:` should be —
    never *whether* to split at all.
  Either way, **for a `type:feature` story**, the PM is also invoked to check the proposed
  `type:feature` tasks still collectively cover the original story's acceptance criteria
  before it's finalized (excluding any `type:tech` or `type:e2e` task from that check —
  neither implements a criterion) — a split that quietly drops part of what the story
  promised would otherwise only surface in phase 5, after everything's already been built.

**Creating or reusing an Epic** (phase 1, for either type): before creating a new Epic,
check open `level:epic` issues of the matching `type:` for one that already fits the
idea/need by theme — reuse it (attach the new story/stories as sub-issues of it) rather
than creating a duplicate. Only create a new Epic when no existing one fits and the idea
genuinely can't be delivered as one story.

**Phase 2 still claims and works exactly one ticket per invocation** (§4 "Claim
Protocol"). But nothing stops the architect from *reading* related tickets for context
while scoping that one ticket: the parent Epic (if any), sibling stories under it, or
anything already linked via "Blocks #M"/"Depends on #N" or a sub-issue relationship — this
is read-only context-gathering, not a second claim.

### Prerequisite tech tickets (distinct from a split's tasks)

A task (above) is part of the *same* ticket's tree — its own `level:task` and `type:`
(§2 intro), never a separate root. A **prerequisite** is the opposite case: while scoping a
`type:feature` (or `type:tech`) ticket in phase 2, the architect discovers it depends on
technical work that isn't part of it at all — infra, CI, a shared library, a migration —
exactly the kind of thing that would normally come in through phase 1 as a human-reported
`type:tech` need (above), just discovered from inside another ticket's phase-2 scoping pass
instead of being reported to `/pilot-story` directly. This is the one place phase 2 still
originates a brand-new ticket itself rather than routing back through phase 1 — the
architect already has full scoping context loaded for this pass, so it creates the
prerequisite inline, using the same mechanics phase 1 uses for a human-reported `type:tech`
need.

The architect creates it — one story, or several under a new/reused Epic, each its own
`level:story` — **never** as a sub-issue of the ticket being scoped: a sub-issue would
make it `level:task` and tie its lifecycle to the parent's split-tracking, which is wrong
for a ticket that is its own root and goes through phases 2-5 independently. Instead, link
the two directions with a plain issue reference: a comment on the new ticket ("Blocks #M")
pointing back, and a line in the body of the ticket being scoped naming it. Never
`sub_issue_write` for this relationship.

Whether the prerequisite is a **hard blocker** — the ticket genuinely can't be spec'd or
built until it lands — decides the exact wording of that line, because §4 "Blocked-by
dependencies" below mechanically gates a ticket on the literal phrase, not on a label:
- Hard blocker → write "Depends on #N". Nothing needs to be lifted by hand: §4's gate
  excludes the ticket from every phase's candidate pool for as long as #N stays open, and
  it becomes a normal candidate again on its own, the next time that phase runs, the
  instant #N closes.
- Not a hard blocker (the ticket can proceed in parallel, or the prerequisite is a
  nice-to-have) → write a plain, non-gating reference instead — e.g. "Related
  prerequisite: #N" — informational only, nothing reads or excludes on this wording.

Don't reach for `on-hold` (§3) for this either way: its manual-lift requirement is the
wrong tool for a wait that resolves itself in a specific, mechanically checkable way.
Reserve `on-hold` for a pause with no single ticket to point at.

The prerequisite ticket itself is nothing special once created: a normal `type:tech`
story, `status:backlog`, moving through phases 2-5 like any other. The only place its
existence matters downstream is the gate check on whatever ticket names it (§4 below).

### Dependencies between tasks of the same split

Distinct from a prerequisite (above, a separate root ticket): when the architect splits a
story, two of its own tasks can still depend on each other — e.g. a front-end task that
consumes an API a back-end task in the same split creates, or a `type:tech` enabler task
that a `type:feature` task needs first (§2 intro). Unlike a prerequisite, this is *within*
the same tree, both tasks `level:task` under the same `level:story` parent regardless of
each one's own independent `type:`. Record it with the same "Depends on #N" phrase (§4
"Blocked-by dependencies") on the dependent task, at split time — the mechanism already
gates on the literal phrase regardless of whether the referenced ticket is a separate root
or a sibling.

### End-to-end test tasks

**Mandatory for every `type:feature` story, never for `type:tech`/`type:bug`.** A story is
one feature — one integrated flow a human can exercise — so every `type:feature` story
gets exactly **one** end-to-end-test task alongside its dev task(s), covering every case of
that flow worth exercising (think one test *file*/`describe` block with several cases
inside, not a single assertion), not a judgment call the architect makes per story.
`type:tech`/`type:bug` tickets never get one — they have no user-facing flow to exercise
this way.

Title convention: "E2E: <story summary>". A dev-sized ticket like any other, `level:task`
under the story, going through phases 2-5 exactly like its siblings, labeled `type:e2e` —
its own type, never stacked with anything else (§2 intro). No new `status:` on the ticket
itself.

It depends on **every** other task in the same split, dev and tech alike — not a
judgment-selected subset: one "Depends on #N" line per sibling, so it naturally isn't
claimable by phase 3/4 until all of them have merged, and structurally can never be the
ticket that finishes the split before its siblings.

**Excluded from the PM's split-coverage check** (above, "Three levels"): neither the e2e
task nor any `type:tech` sibling implements a criterion — the e2e task verifies criteria
the `type:feature` tasks already cover, and a `type:tech` task is an enabler, not a
delivered piece of product behavior.

**Once the e2e task reaches `status:done`, the whole split is structurally finished**
(every dev sibling necessarily already is, per the dependency above) — this is what
triggers §7 "Phase 6 — Human QA" instead of the ordinary cascade straight to `status:done`
(§3 "Cascading completion").

Phase 3 (tech lead) for an e2e task writes the test plan itself as the spec: which flow,
which existing test tooling/framework this project already uses for e2e, and what its
dependencies having merged now makes exercisable end-to-end. **Phase 4 for an e2e task is
`pilot-e2e`, not `pilot-dev`** — `/pilot-dev` (the skill) reads the `type:e2e` label before
calling `Agent` and picks the `pilot-e2e` persona instead, precisely so the agent
implementing it gets a context already tailored to writing a test against real,
already-merged integration points rather than generic implementation instructions.
`pilot-e2e` writes the test against that already-merged behavior — the ticket cannot be
marked done with a test that doesn't actually pass. If running it surfaces a genuine
defect in that already-merged code rather than a gap in the e2e ticket's own scope,
that's a bug discovered mid-implementation — see "Prerequisite bug tickets" below.

### Re-scoping a `type:feature` story after its split is done

Phase 2 only ever scopes a `level:story` — never a `level:task` (a task is the *output* of
scoping, not something scoped again itself; if a task turns out to need further breakdown,
that's re-splitting the *story*, not scoping the task). Within that, `/pilot-scope` handles
an already-once-split `level:story` differently depending on exactly how finished it is:

- **Closed (`status:done` or `status:wont-do`)** — terminal, full stop. `/pilot-scope`
  refuses to claim it: report that it's already closed and stop, no exception — nothing
  else in PILOT ever moves a ticket backward out of a terminal state. The new work gets
  its own story instead (a plain, non-gating "Extends #N" reference in its body is enough
  to keep the link visible — never a sub-issue, same reasoning as a prerequisite ticket,
  §2 above).
- **`status:qa` or `status:in-qa`** — still reversible, because nothing terminal has
  happened yet: the cascade only just mechanically set `status:qa` the moment the e2e task
  closed, and no human has confirmed anything (`status:in-qa` is one step further — a
  `/pilot-qa` session may even be live — but still short of a verdict). Claiming an issue
  number in either status is a valid, explicit `/pilot-scope` entry point (never part of a
  bare pool) — an existing `status:in-qa` assignee doesn't block this claim, the
  architect's claim simply overwrites it. Post a comment explaining why, then claim it
  into `status:scoping` — the one deliberate, phase-2-only backward transition in the
  whole state machine. From here it's an ordinary phase-2 pass, just with extra context
  (which tasks, including the original e2e one, are already `status:done` from the
  earlier round):
  1. Propose the new task(s) the same way as any split (§2 "Three levels").
  2. Propose exactly one new `type:e2e` task for *this round* — never reopen or amend the
     original, already-`status:done` e2e task. Title it distinctly (e.g. "E2E: <story
     summary> (round 2)") and depend only on this round's new task(s). Its phase-3 spec
     should say explicitly that its job is to *extend* the existing e2e test asset the
     original task wrote, not duplicate coverage from scratch.
  3. Run the PM coverage check (§2 above) against this round's new `type:feature` tasks
     only — the original tasks were already checked at split time.
  4. Finalize exactly like any other split (§4 "Claim Protocol"): the story lands back on
     `status:split`, now tracking this round's new tasks instead.
  Once this round's new e2e task also reaches `status:done`, the story cascades to
  `status:qa` again exactly as before (§3 "Cascading completion") — the new behavior gets
  its own human QA pass in phase 6, same as the original.
- **`status:split`, original e2e task not yet done** — no special handling needed: the
  story hasn't finished its first round yet, so this is an ordinary re-scope. Add the new
  task(s) to the existing split and extend the *existing* (still-open) e2e task's
  dependencies to also cover them, rather than spinning up a second one.

This applies the same way to a `type:tech` story that did split (not every one does, §2
"Three levels" — and `type:bug` is never even a `level:story` in the first place, so this
case never arises for one at all) — closed is just as terminal, `status:split` just as
reversible while it's still mid-flight — minus the e2e-task mechanics, which only ever
apply to `type:feature`.

### Prerequisite bug tickets (phase 2, phase 4, or phase 6)

Distinct from a prerequisite *tech* ticket above (a new technical need, no defect
implied): while scoping (phase 2), implementing/testing (phase 4), or manually confirming
shipped behavior (phase 6), the architect, dev/`pilot-e2e`, or `pilot-qa` may run into
something that looks like a concrete **defect** in already-shipped code outside the
ticket's own scope — not an ambiguity in what's being built (phase 4's own spec-deviation
path, `pilot-dev.md`, still covers that). Most commonly this happens while writing or
running an end-to-end test task, or during a phase-6 manual test case (above; §7), but
isn't limited to either case.

**Classify it before creating anything** — the same read `/pilot-story --bug` gives a raw
report (§2 intro above): genuinely a code defect against something already agreed on, or
actually a new/different need in disguise. If it's not a bug, don't create a `type:bug`
ticket at all: treat it as a prerequisite *tech* ticket instead (above) if it's a new
technical need, or, if it needs an actual product/judgment decision, leave it for a human
to take through phase 1 themselves rather than originating anything — §7 "Phase 6 — Human
QA" step 6 covers the phase-6 version of this specifically.

If it genuinely is a bug, originate a new ticket for it using the same linking mechanics as
a prerequisite tech ticket, just `type:bug` instead of `type:tech` — with one difference:
create it directly as `type:bug`, `level:task`, `status:spec-ready` — never
`level:story`/`status:backlog` (§2 "Three levels" — a bug never goes through phase 2's own
scoping pass). Written directly (the same quality bar as `/pilot-story --bug`'s own phase-1
output — what's broken, how observed, root cause/fix if known), unassigned, standalone —
never as a sub-issue of the ticket being worked. Link the two: "Blocks #M" on the new
ticket, "Depends on #N" in the discovering ticket's own body — always a hard blocker, since
the discovering ticket cannot be finished until the bug is fixed.

**Phase 4 and phase 6 need one thing phase 2 doesn't: unclaiming, not just linking.** A
ticket phase 2 is scoping isn't claimed by phase 3/4 yet, so recording "Depends on #N" and
finishing the scoping pass normally is enough — the gate (§4 "Blocked-by dependencies")
does the rest once phase 3/4 later try to claim it. A ticket phase 4 is *implementing*, or
phase 6 is *confirming*, by contrast, is already claimed and mid-phase (`status:in-dev` or
`status:in-qa`, assigned) — the gate only ever fires when a phase builds a candidate pool
or claims a ticket, so leaving it claimed would just sit there with nothing ever
rechecking it. So from phase 4 (`pilot-dev` or `pilot-e2e`) or phase 6 (`pilot-qa`), also
unclaim the ticket being worked before stopping: clear its assignee and move it back to
its own pre-claim `status:` (`status:dev-ready` for phase 4, `status:qa` for phase 6) —
never push a broken or partial commit (phase 4), or finish the QA pass as if nothing were
wrong (phase 6), in the meantime. For phase 4, first push whatever's already done to a
branch (creating one if none exists yet) and comment on the ticket naming it, so whichever
agent claims it next — the same one or a different one — resumes from that branch instead
of starting over (`pilot-dev.md`/`pilot-e2e.md` cover the claim-time check for this). The
ticket is now an ordinary `status:dev-ready`/`status:qa` candidate again, gated only by
"Depends on #N" like any other — no flag to remove, no `--resume` to remember: the moment
the bug ticket reaches `status:done`, the next run (bare, or an explicit ticket number —
§4 extends its explicit-number check to phase 6 too) picks it back up on its own.

---

## 3. Labels

### `type:` — the nature of the work, set independently on every ticket (§2)
- `type:feature`
- `type:tech`
- `type:bug` — a defect in already-shipped code (§2); classified and originated by the
  architect (or dev/`pilot-e2e`/`pilot-qa`, discovered inline), reviewed by architect +
  tech lead only, same as `type:tech`. Always `level:task` directly, never `level:story` —
  it skips phase 2 entirely (§2 "Three levels").
- `type:e2e` — a `level:task`'s own type, never a `level:story`'s or `level:epic`'s;
  always exactly one per `type:feature` split (§2 "End-to-end test tasks"), reviewed by
  PM + architect + tech lead, same set as `type:feature`. It changes which agent
  `/pilot-dev` calls in phase 4 (`pilot-e2e` instead of `pilot-dev`).

Never inherited from a parent to a child (§2 intro) — a story's tasks each get whichever of
the four fits that specific task, assigned by the architect at split time.

### `level:` — depth in the tree, set once at creation, never recomputed
- `level:epic` — groups several `level:story` tickets (§2 "Three levels"). Carries no
  `status:` label and never moves through the pipeline itself — its stories are linked to
  it as native GitHub sub-issues (`mcp__github__sub_issue_write`), not a hand-written
  checklist. It stays **open indefinitely and is closed by hand** — new stories can be
  added to it at any time, so unlike a split story (see "Cascading completion" below), it
  never auto-closes.
- `level:story` — the root unit phase 1 always produces for `type:feature`/`type:tech`
  (§2 "Three levels").
- `level:task` — a dev-sized unit of a `status:split` story, or a standalone `type:bug`
  ticket with no parent (§2 "Three levels"). Never itself split further — depth is capped
  at these three levels.

### `status:` — the pipeline state machine, one label at a time
```
draft → backlog → scoping → spec-ready → in-spec → dev-ready → in-dev → review-ready →
  in-review → approved → done
                      ↓         ↓
                      +---- wont-do (before dev starts) ----+

scoping → split (tracker for tasks, reaches done only by cascade — see below)

split (type:feature only) → qa → in-qa → done (Phase 6 — Human QA, §7 — instead of
cascading straight to done like a type:tech split does)

in-review → changes-requested → in-dev → review-ready → in-review (loop back through dev
when phase 5 blocks on something that needs an actual code change — see
`status:changes-requested` below and §6)
```
- `status:draft` — phase 1 (`/pilot-story`) has created the ticket but the human hasn't
  given final approval yet — assigned to whoever's session created it, the moment the
  agent's first draft exists (§4 "Interaction modes"). Excluded from every phase's
  candidate pools, never picked up bare, only reachable by an explicit `--resume <issue>`
  or once a cleared `needs-human` flag makes it resumable. Becomes `status:backlog`
  (story) or `status:spec-ready` (bug), unassigned, once the human gives final approval.
- `status:backlog` — ticket exists, phase 2 hasn't started.
- `status:scoping` — architect has claimed it for phase 2.
- `status:spec-ready` — ready for phase 3: an unsplit `type:tech` story, a freshly split
  task (already scoped as part of the split), or a `type:bug` ticket skipping phase 2
  entirely.
- `status:split` — the architect decided in phase 2 this story is too big for one pass
  through phases 3-4 and broke it into tasks instead (§2 "Three levels"). The story
  carries no further `status:` transitions of its own from here — it's a tracker for its
  tasks, the same role an Epic plays for its stories, one level down. It reaches
  `status:done` only via cascading completion (below), never directly.
- `status:in-spec` — tech lead has claimed it for phase 3.
- `status:dev-ready` — spec written, ready for phase 4.
- `status:in-dev` — a dev has claimed it for phase 4.
- `status:review-ready` — a PR is open, unassigned, not currently claimed by phase 5: set
  by `/pilot-dev` when it opens a PR, or pushes a reclaim fix, in place of setting
  `status:in-review` directly (§4 "Claim Protocol" — this is phase 5's own pre-claim
  status, matching `status:dev-ready`'s role for phase 4).
- `status:in-review` — phase 5 has claimed it (§4 "Claim Protocol") and is running, or
  blocked on a `decision`-only point awaiting a human — `needs-human` sits alongside, same
  as any other phase's in-progress status (§3 "`needs-human`" below). Never set directly by
  `/pilot-dev`, only by phase 5's own claim.
- `status:changes-requested` — phase 5 found at least one blocking point tagged `change`
  (§6): an actionable code-level fix, not just a question for a human to weigh in on. Set
  instead of leaving `status:in-review`, alongside `needs-human` same as any block. Once a
  human clears `needs-human`, `/pilot-dev` claims it like any other pre-claim status (§4
  "Reclaiming a `status:changes-requested` ticket") — reclaiming here is expected to find
  an existing assignee (phase 5's own claiming session, §4 "Claim Protocol") and overwrite
  it rather than treat that as a conflict. The dev pushes new commits to the *same*
  already-open PR (never a second PR for the same ticket) and moves the ticket to
  `status:review-ready` when done — never `status:in-review` directly, phase 5 claims it
  fresh.
- `status:approved` — phase 5 ran and every reviewer approved (§6) — set instead of
  leaving `status:in-review`. This is the "ready to merge, nothing outstanding" signal.
  Without `--merge`, a human still performs the actual merge — PILOT's default is never to
  merge on its own. Given `--merge` (§4 "Interaction modes", §6 "Merge, only with
  `--merge`"), the same run merges the PR itself right after submitting the review, using
  the repository's normal merge method; the ticket then reaches `status:done` via
  `pilot-status-on-merge.yml` exactly as it would after a human merge. There's no automatic
  re-review trigger if new commits land on the PR after this before it's actually merged —
  re-run `/pilot-review` on it by hand, or move it back to `status:review-ready` yourself,
  before merging.
- `status:wont-do` — the architect concluded during phase 2 that this ticket shouldn't be
  built after all (out of scope, duplicate, superseded) and closed the issue instead of
  scoping it. Only settable from phase 2, before any spec or code has been written —
  once a ticket has reached `status:in-spec` or later, killing it is a human call: flag
  `needs-human` with the reasoning instead and let a human close it. A `type:bug` ticket
  therefore never carries this label at all: it has no phase 2 (§2 "Three levels"), so an
  invalid report is caught in phase 1 by creating nothing in the first place, and a bug
  that only turns out to be invalid after creation goes the `needs-human` route like any
  other post-phase-2 ticket.
- `status:qa` — a `type:feature` `status:split` story whose e2e task (and therefore
  every dev task it depends on) has reached `status:done` — set by
  `.github/workflows/pilot-status-on-merge.yml` in place of the ordinary cascade straight
  to `status:done` (§3 "Cascading completion"; §7 "Phase 6 — Human QA"). Never set on a
  `type:tech` story, and never on a task itself — which covers every `type:bug` ticket too,
  always `level:task` (§2 "Three levels"). Unclaimed, unassigned — the fresh-work pool
  `/pilot-qa` picks from.
- `status:in-qa` — `pilot-qa` has claimed it for phase 6.
- `status:done` — merged (or, for a `status:split` story, completed by cascade or, for a
  `type:feature` one, by phase 6 — see below and §7). Not set by any phase skill directly
  for an actionable ticket coming out of a merge (merge is always a human action or, for
  phase 5, an explicit `--merge` run, §6 "Merge, only with `--merge`" — either way outside
  PILOT's control at the moment it happens) — set instead by the
  `.github/workflows/pilot-status-on-merge.yml` GitHub Actions workflow, independent of any
  agent session being alive:
  - Triggered on `pull_request: closed` (gated on `merged == true`): resolves the issue(s)
    the merge closes via `PullRequest.closingIssuesReferences`, sets `status:done` on each,
    and, for any that's a task, runs the cascading-completion check (§3 "Cascading
    completion") against its `status:split` parent story (never a `level:epic` — that
    always closes by hand). This is the only place `status:done` gets set on an actionable
    ticket coming out of a merge.
  - Also triggered on `issues: closed`, for completions that never go through a PR merge at
    all: `status:wont-do` (above), which the architect sets and closes directly in phase 2,
    and any hand-closed issue. This path only runs the cascading-completion check (§3
    "Cascading completion") — never sets `status:done` itself, since the closing party is
    responsible for the issue's own terminal `status:` label — and only when the issue
    already carries `status:done` or `status:wont-do`. It skips entirely when GitHub's own
    timeline shows the closure came from a merged commit reference, so the same closure is
    never processed twice.

  `/pilot-qa` is the one place a phase skill *does* set `status:done` directly, once a
  human confirms the story's behavior in phase 6 (§7) — there's no PR merge there for the
  workflow to react to.

  **Known limitation:** GitHub only recognizes a `Closes #N` reference (populating
  `closingIssuesReferences`, which the workflow reads) when the merging PR's base is the
  repository's *default* branch — never for a PR merged into an intermediate,
  not-yet-merged branch, even once that branch later reaches the default branch itself.
  If a ticket's implementing PR had to be based on another PILOT PR's branch instead of
  the default branch directly, the workflow finds zero closing issues on that merge and
  does nothing — set `status:done` on the ticket by hand once everything has actually
  landed on the default branch. Not fixable in the workflow itself; a GitHub platform
  behavior.

`level:epic` tickets never carry a `status:` label at all. `status:wont-do` and
`status:split` tickets don't carry any *other* `status:` label — the rest of the state
machine only applies to tickets still actively moving through phases 3-5 themselves.

### `needs-human` — an orthogonal flag, not a pipeline state

Unlike every label above, `needs-human` never replaces the ticket's current `status:` —
it sits alongside whichever one is already there. When a phase hits something only a
human can decide, it leaves the ticket's `status:` exactly where it was and adds
`needs-human`, plus a comment. That comment is never optional and is never just the label
with no context attached — it must say, explicitly, both **why** the ticket needs a human
right now and **what's needed** from a human to unblock it. A label with no comment, or
one that only restates "needs a human" without saying why or what for, is not a valid use
of this flag — whoever reads it next has to be able to act from the comment alone.

**Phase 5 is the one exception to "`status:` stays exactly where it was."** A phase-5
block tagged `change` (§6) is different: the answer is already known regardless of what a
human says about it — the ticket needs code, so it moves straight to
`status:changes-requested` (above) as part of applying the block, not just `needs-human`
on an unchanged `status:in-review`.

A human resolves it by **removing the `needs-human` label** once they've responded (a
reply comment) or decided there's nothing more to add — the label's absence is the whole
signal; nothing else needs to change by hand.

**Always add `needs-human` and post the why/what's-needed comment the moment a phase
hits something only a human can decide** — one path, not two, whether or not a human
happens to be live in the same session right then. What differs by context is only what
happens *next*:

- **Nobody answers on the spot** (a scheduled sweep with no human present, or an
  interactive human who says they need to think about it) — the label and comment stay
  exactly as posted, and the ticket waits for the async resume protocol below.
- **A human is live in the same session** and answers right there in conversation — the
  agent still posts the why/what's-needed comment first, exactly as it would if nobody
  were around; a quick answer is not a reason to skip straight to a resolution. Once the
  human answers, the agent proceeds with that answer and, in the same turn, posts a
  **second** comment summarizing what was actually decided — *then* **removes
  `needs-human` itself**. It never removes it silently: the ticket's GitHub history must
  show both the block and its resolution even when the conversation that resolved it never
  touched GitHub at all — a blocking comment followed by a resolution comment (or, for
  phase 5, a blocking review followed by a second, corrected review, §6), whether the
  gap between them was seconds (live) or days (async).

#### Cascading completion

This applies to `status:split` stories only — a story's tasks are a fixed set for
whichever round is currently in flight (the original split, or a later re-scope round,
"Re-scoping a `type:feature` story after its split is done" above), so completeness at
any given moment is provable from a live read of its current sub-issues — never a cached
list. An Epic's stories are not — an Epic never auto-closes, a human always closes it by
hand, regardless of how many of its current stories are done.

Whenever a task reaches `status:done` or `status:wont-do`, check whether its parent
is a `status:split` story and, if so, whether *all* of that story's other tasks are
now also done/wont-do. A standalone `type:bug` task has no parent at all (§2 "Three
levels") — this check simply finds none and does nothing further; the bug ticket's own
`status:done`, set directly on merge, is the end of it.
- Not all done yet → do nothing further, the parent stays `status:split`.
- All done, parent is `type:tech` (the only root type that can reach `status:split`
  without being `type:feature` — `type:bug` is never even a `level:story`, so it never
  has a parent to check in the first place) → set the parent story itself to
  `status:done` — it was never merged directly, but its work is now finished. This does
  not cascade any further: if that story belongs to an Epic, the Epic still does not
  auto-close — a human closes it whenever they judge it complete.
- All done, parent is `type:feature` → set the parent to **`status:qa`** instead of
  `status:done` (§7 "Phase 6 — Human QA") — every `type:feature` split includes exactly
  one e2e task depending on all its dev siblings, so "all done" here is structurally the
  same moment the e2e task itself just finished. `status:done` for this story is set
  later, by `/pilot-qa` itself, once a human confirms the behavior.

No periodic sweep exists beyond this — the check is event-driven, not polled. A
`status:split` story whose last task was closed without ever carrying
`status:done`/`status:wont-do` (mislabeled outside PILOT's own conventions) is the one
case this still can't catch, since there is no terminal-status event to react to.

### `on-hold` — an orthogonal pause flag, unrelated to a pending decision

Distinct from `needs-human`: `needs-human` means a phase hit something it needs a
person's judgment on *right now*, and stops until that judgment comes. `on-hold` means
the opposite kind of "don't touch this" — nobody needs to look at it or decide anything
imminently, it's paused because of something bigger in flight elsewhere (a global
restructuring, a dependency on an Epic or on several/fuzzy conditions, deliberately
deferred work) and picking it up now would just be wasted or wrong. A dependency on **one
specific, still-open ticket** is not this — that's the "Depends on #N" mechanical gate
instead (§4 "Blocked-by dependencies"), which needs no label and clears itself the moment
that ticket closes; reach for `on-hold` only when there's no single ticket a phase skill
could check. Like `needs-human`, it sits alongside whichever `status:` is already there
rather than replacing it.

A human applies it directly at any time, or a phase agent applies it itself if it notices
mid-work that the ticket depends on unresolved global work — either way, always with a
comment saying what it's waiting on. A bare `on-hold` label with no comment is as invalid
as a bare `needs-human` one.

Excluded from every phase's candidate pools exactly like `needs-human`. Only a human
removes it, once whatever it was waiting on has actually resolved — there's no
live-session "answer it and remove it in the same turn" path like `needs-human` has,
since there's no question being asked that a live human could answer on the spot. Once
removed, the ticket is simply a normal candidate again. The two flags are independent and
can coexist; clearing one has no effect on the other.

### `priority:`
- `priority:P0` / `priority:P1` / `priority:P2` — every ticket gets an initial value at
  phase 1, set by whichever agent creates it: the PM for `type:feature` (business
  value/urgency to the user — the only phase-1 agent with the product context to judge
  it), the architect for `type:tech`/`type:bug` (the technical framing below — neither
  has a PM angle). This is what lets `/pilot-scope`'s own `status:backlog` pool (§4
  "Picking the next ticket...") sort on something real instead of every fresh story
  falling back to oldest-first.
- At phase 2, the architect reconfirms or revises it: unchanged if the ticket ends up not
  split (still the one leaf — `type:tech` only, `type:feature` always splits), or
  replaced by each task's own priority if it splits — a task's priority doesn't have to
  match its story's initial one (e.g. a `type:tech` enabler task inside a `type:feature`
  split may be more or less urgent than the user-facing tasks around it). The moment a
  story reaches `status:split`, its own `priority:` label is removed — from then on it's
  a tracker, and its tasks are what any pool actually selects among.
- Not set on `level:epic` (never itself a candidate in any pool) or `status:split`
  tracker parents (superseded by its tasks' own the moment it splits, above).
- Rough default for the *technical* framing (`type:tech`, `type:bug`, and any `type:tech`
  task within a `type:feature` split) if this project has no priority convention of its
  own: P0 closes a real gap (security, correctness, a broken safety net) — do it soon;
  P1 is solid value, not urgent; P2 is nice-to-have or conditional. For `type:feature`,
  the PM's call is about business value/urgency to the user instead. Adopt this project's
  own priority convention in either case, if it already has one that differs.

---

## 4. Claim Protocol (avoiding two agents on the same ticket)

Phases 2, 3, 4, 5, and 6 each start by **claiming** the ticket before doing any real work,
because several instances of the same phase (e.g. several devs, or two overlapping
scheduled review sweeps) may run concurrently. Phase 1 doesn't fit this pattern the same
way — there's no pre-existing ticket to claim — but the moment it creates the ticket
(`status:draft`, §3), it assigns it the same way, and that assignment sticks if the pair
session ends before final approval, exactly like a claimed ticket left mid-phase; see
"Resuming an orphaned claim" below.

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
independently in parallel, never seeing each other's verdict (§6).

### Picking the next ticket when none is specified

Phase 1 has no such pool at all — it always starts from a raw need in free text (or an
explicit `--resume <issue>`). When any other phase skill is invoked without an explicit
ticket number, it builds its candidate pool from **two** queries, not one:
1. **Fresh work** — tickets in its own pre-claim `status:`, no assignee.
2. **Resumable work** — tickets already in its own *in-progress* `status:`, still carrying
   the assignee from when they were originally claimed, but **no longer** carrying
   `needs-human` — see "Resuming a `needs-human` ticket" below.

`/pilot-dev` alone has a **third** pool: tickets in `status:changes-requested` with
`needs-human` no longer present — phase 5 sent these back for an actual code fix (§6). See
"Reclaiming a `status:changes-requested` ticket" below.

All pools that apply to a given phase skill are merged and picked from together: highest
`priority:` first, then a ticket referenced by another open ticket's "Blocks #M" comment
before one that isn't, then oldest by creation date to break ties; a ticket carrying no
`priority:` at all sorts last. A ticket still carrying
`needs-human` or `on-hold` is never a candidate in any pool, and neither is one whose body
has an unresolved "Depends on #N" reference (below, "Blocked-by dependencies") — both
re-enter automatically once resolved, no flag to remove for the dependency case. An
orphaned claim (already assigned, still in that phase's in-progress `status:`, but no
`needs-human`) is likewise never a candidate in any bare pool — see "Resuming an orphaned
claim" below; it only resumes via an explicit `--resume <issue>`.

### Blocked-by dependencies (mechanical gate, distinct from `on-hold`)

A ticket's body may carry one or more "Depends on #N" references. Three places write
them today: the architect, when phase 2 spins out a prerequisite tech ticket it judges a
hard blocker (§2 "Prerequisite tech tickets"); the architect again, for a prerequisite bug
ticket (§2 "Prerequisite bug tickets (phase 2, phase 4, or phase 6)"); and
`pilot-dev`/`pilot-e2e` (phase 4) or `pilot-qa` (phase 6), into their own ticket's body
when they originate a bug inline (same section — always a hard blocker there). The
mechanism itself isn't specific to any of them; anything that writes the same phrase gets
the same gate for free.

**Format: one dependency per line, always.** Multiple dependencies are multiple separate
"Depends on #N" lines, one issue number each — never several numbers combined onto one
line. This keeps the check a trivial per-line literal match, not a list/prose parse.

Whenever a phase builds a candidate pool from its own `status:` pools (above), it also
reads each candidate's body for this exact phrase and, for each `#N` found, checks whether
that issue is still open — plain open/closed, not its `status:` label. A candidate with at
least one still-open dependency is excluded from the pool for this run, the same as
`needs-human`/`on-hold` above — but unlike those two, nothing needs removing by hand: the
moment the referenced ticket closes, the next run of that phase picks the ticket back up
as an ordinary candidate. This is a deterministic tool-call check the skill performs
directly (§5), never something the subagent reasons about.

**In phases 3, 4, and 6, the gate applies to an explicitly-given ticket number too, not
just bare-pool selection.** `/pilot-spec`, `/pilot-dev`, and `/pilot-qa` each run this same
check before claiming any ticket, whether it got there via the pool or because a human
named it directly — the same principle already applied to an explicit ticket number still
carrying `needs-human`/`on-hold`.

**Phase 2 (`/pilot-scope`) is the deliberate exception.** Re-scoping a ticket doesn't need
its prerequisite resolved first, only the phases that actually spec and build it (3 and 4)
do; `/pilot-scope` doesn't check this gate on an explicitly-given ticket number, and it
never meaningfully fires from phase 2's own bare pool either, since nothing writes
"Depends on #N" onto a ticket before phase 2 has scoped it at least once.

The same reference feeds the ordering tie-break above.

### Resuming a `needs-human` ticket

A human resolves the flag by **removing the `needs-human` label** from the ticket —
optionally after leaving a reply comment with guidance, or with no reply at all if
there's nothing to add beyond "proceed as proposed." That removal, not a reaction or a
particular comment, is the entire signal a phase skill looks for. This can happen from
any session, at any time — nothing depends on the session that raised the block still
being alive.

A phase skill treats a ticket as **resuming**, not a fresh claim, whenever it's already
in that phase's in-progress `status:` (whether picked up bare or given explicitly):
1. Read the full blocking context, not just the ticket body — the blocking comment and
   everything posted after it, for every phase except 5. Phase 5's own block is a
   submitted PR review, not a comment (§6) — read that, plus the PR's comment thread for
   whatever's posted after it.
2. If `needs-human` is still present, it isn't resolved yet — report that and stop (this
   only matters when a ticket number was given explicitly; the bare pool above already
   excludes these).
3. Otherwise, proceed with the phase's `Agent` call, passing both the original blocking
   context and whatever's in the thread after it (a specific reply, or "no reply — treat
   as approved as proposed" if none). The agent proceeds, corrects, or blocks again if
   that still doesn't actually resolve things.

### Resuming an orphaned claim (`--resume`)

Distinct from both "Resuming a `needs-human` ticket" above and "Reclaiming a
`status:changes-requested` ticket" below: a ticket claimed but with nobody actually still
working it — still carrying its original assignee, still in that phase's in-progress
`status:` (`status:draft`, `status:scoping`, `status:in-spec`, `status:in-dev`,
`status:in-review`, `status:in-qa`), with **no** `needs-human`. Two different causes leave
the exact same shape, indistinguishable from the ticket alone: a **pair** session
("Interaction modes" below) that ended before reaching the phase's final approval
(pair-capable phases only), or an `--auto` run that died mid-work (a quota limit, a crash,
a timeout) before it could either finish or flag `needs-human`. Left alone, the normal
claim-protocol check ("already has an assignee → stop") would treat either the same as a
ticket someone else is actively working right now, which isn't the case. For phase 1
specifically, `status:draft` is what makes this possible at all.

`--resume` requires an **explicit ticket number** — it is never part of any bare/
scheduled-sweep pool. Nothing on the ticket itself distinguishes an orphaned claim from one
genuinely still in progress elsewhere.

To resume:
1. Read the full ticket — body and comment thread, not just the latest checkpoint. For
   `/pilot-scope`, `/pilot-spec`, and `/pilot-dev`'s pair sessions this reconstructs pair
   mode's incremental checkpoint writes ("Interaction modes" below). `/pilot-review`'s own
   checkpoint is a pending GitHub PR review instead of a ticket comment (§6 "Checkpoint the
   outcome as a pending review") — check for one under this run's own identity: if it
   exists and is still pinned to the PR's current head commit, that's the recovered
   outcome — skip re-running the reviewers and proceed straight to submitting or confirming
   it per the current mode. If its commit no longer matches (new commits landed since it
   was created), or none exists, discard any stale one and restart the reviewers fresh —
   the tech lead's re-validation has to run against the actual current code either way. For
   an `--auto` run of any other phase, there's nothing to reconstruct — a plain restart from
   the ticket's original inputs.
2. Claim it the same way a `status:changes-requested` reclaim does (below) — an existing
   assignee doesn't count as a conflict here. Overwrite it (assignee → this session);
   `status:` stays at its current in-progress value.
3. Pass whatever step 1 recovered to the phase's `Agent` call as its starting context, and
   continue: the normal pair loop where one exists, otherwise a fresh pass.

Finalization behaves exactly as any other run of that phase from here.

### Reclaiming a `status:changes-requested` ticket (`/pilot-dev` only)

Unlike "Resuming a `needs-human` ticket" or "Resuming an orphaned claim" above,
`status:changes-requested` is set by *phase 5* (§6), not by `/pilot-dev` itself — the
ticket already has an open PR, and whatever assignee is still on it is phase 5's own
claiming session (§4 "Claim Protocol"), not necessarily whoever runs `/pilot-dev` next.

Reclaiming one follows the standard claim protocol above with a single, deliberate
exception: an existing assignee doesn't count as "already claimed" for this status — the
claiming session simply overwrites it (assignee → itself, `status:` → `in-dev`) and
re-reads to confirm the overwrite held.

Once claimed, pass the subagent the phase-5 blocking review — its submitted PR review,
read from the PR's reviews rather than the issue's comment thread (§6) — with its
`change`-tagged points to fix, plus any `decision`-tagged points and their resolution,
instead of a fresh spec — the existing PR's
branch is what gets more commits. The subagent pushes to that same
branch/PR (never a second PR for the same ticket) and, once satisfied, moves the ticket to
`status:review-ready` (unassigned) exactly as it would after a first-time implementation —
never `status:in-review` directly, phase 5 claims it fresh.

### Scheduled sweeps

Each phase skill is meant to also run **bare, on a timer** — a Routine whose prompt is
nothing but the literal command. For `/pilot-scope`, `/pilot-spec`, `/pilot-dev`, and
`/pilot-review` — all four default to pair mode ("Interaction modes" below) — that literal
command must include `--auto` (still no ticket number computed by the routine itself),
since pair requires a human live in the session and a Routine has none. `/pilot-story` and
`/pilot-qa` are pair-only with no `--auto` and are therefore never driven by a Routine at
all. Beyond that flag, this works without any special-casing because "picking the next
ticket when none is specified" (above) already covers both fresh and resumed work
identically. Four independent Routines — one each for `/pilot-scope --auto`, `/pilot-spec
--auto`, `/pilot-dev --auto`, and `/pilot-review --auto` (add `--merge` too if the Routine
should also merge once every reviewer approves, §6 "Merge, only with `--merge`") — each on
its own schedule, so a slow or failing phase never delays the others.

### Interaction modes: pair (default) and `--auto`

The six phase skills split into three groups by which modes they support:

- **`/pilot-story`, `/pilot-qa`** — **pair only**, no `--auto` exists for either. Turning a
  raw idea into a story or a technical need into a ticket is a conversation between the
  drafting agent and a human, not something worth running unattended; symmetrically, phase
  6 is a human physically testing shipped behavior, which has no unattended equivalent at
  all. Neither is ever driven by a scheduled Routine as a result. Both still support
  `--resume <issue>` for a ticket left mid-pair.
- **`/pilot-scope`, `/pilot-spec`, `/pilot-dev`** — default to **pair**, with `--auto` to
  opt out of it.
- **`/pilot-review`** — default to **pair** too, with `--auto` to opt out of it. Unlike the
  three above, its reviewers always run fully parallel and isolated from each other
  regardless of mode (§6) — there's no natural mid-review checkpoint while they're working.
  Its one pair checkpoint sits right after aggregation (§6 "Pair (default) vs `--auto`"):
  once the reviewers' verdicts are collected into the single outcome that would otherwise
  be applied straight away, pair mode shows it to the human first — a last look before an
  approval (and any `--merge`) or a `changes-requested` goes out, and, when the only
  blocking points are `decision`-tagged, a chance to resolve them live instead of leaving
  them for the usual async `needs-human` wait (§3 "A human is live in the same session").
  `--auto` applies the outcome straight away, no pause. Also supports `--merge` (§6 "Merge,
  only with `--merge`") — orthogonal to pair/`--auto`, combinable with either — to merge
  the PR itself once every reviewer approves instead of leaving it for a human; without it,
  phase 5 never merges. Still supports `--resume <issue>` to recover a claim orphaned by a
  crashed run (above).

Both modes still claim (above) immediately, same as always — it's concurrency
bookkeeping, unrelated to the content decision.

**Pair** requires a human live in the same session. The agent stops at its phase's
natural checkpoint(s) — the drafted story, the proposed decomposition, the spec outline,
the implementation plan — and the skill relays that to the human as an ordinary reply,
waits for their next message, feeds it back to the agent, and repeats until they approve.
**The skill writes progress into the ticket immediately at every checkpoint** (a comment,
or a partial `issue_write`) instead of holding it in-conversation until the whole phase is
done — the ticket itself becomes the durable record of how far the pair session got, which
is what makes `--resume` possible.

For phases 2-4 a ticket already exists before the phase starts. **Phase 1 is the one case
where no ticket exists yet at the very first checkpoint** — `/pilot-story` creates it
right there (`status:draft`, §3) as soon as the agent's first draft is ready to show the
human, instead of holding it in-conversation. Either way, the very last thing pair mode
does — setting the phase's completion `status:` — is the same end-state `--auto` reaches
in one pass, for the phases that have an `--auto` (phase 1 doesn't, below).

**Final consolidation pass, every phase with incremental checkpoints, right before setting
the completion `status:`.** Writing progress checkpoint by checkpoint means the ticket (or,
for phase 4, the diff) was assembled incrementally, round by round of the pair
conversation — nothing guarantees a decision from an early round still squares with one
added several rounds later. Once the human gives final approval, before applying the
completion label, the agent re-reads the whole thing as it now stands — the full ticket
body, not just the latest round's delta; the full diff, not just the last commit, for
phase 4 — and fixes anything incoherent or incomplete it finds. This is also what
`pilot-dev` uses in phase 4 as its own self-review of the implementation before opening
the PR — a substitute for a separate reviewer checking the same thing again in phase 5
(§6), not an addition to it. Phase 5 has no incremental assembly to reconcile this way —
its own aggregation (§6) already collapses every reviewer's one-shot verdict into a single
outcome before its one pair checkpoint is ever reached, so there's nothing earlier to
re-read against.

**`--auto`** is the old default, before pair mode existed: the agent decides everything
and the skill applies the finished result straight to GitHub in one pass, no human
checkpoint. This is what a scheduled Routine must use for `/pilot-scope`, `/pilot-spec`,
`/pilot-dev`, or `/pilot-review` (above, "Scheduled sweeps") — pair requires a live human.
`/pilot-story` has no `--auto` and is therefore never Routine-driven.

`--auto` and `--resume` are mutually exclusive with each other and with pair mode itself —
pick exactly one per run. `--merge` (phase 5 only, §6 "Merge, only with `--merge`") is a
separate, orthogonal flag: it controls only whether an all-approve outcome also merges the
PR itself, and combines with either pair or `--auto`.

This is unrelated to the "ask live" behavior in §3 ("`needs-human` — an orthogonal
flag") — that one fires for a genuine blocker the agent can't resolve alone, whether or
not pair mode is active; pair is for iterating on a draft together even when nothing is
actually blocking.

---

## 5. Token Efficiency: Isolated Contexts Per Phase

Keeping token cost down per ticket is central to PILOT's design. Two rules keep it cheap:

1. **Each phase is a separate agent context**, not one context that accumulates every
   prior phase's transcript. A phase skill reads only what that phase needs from the
   ticket (its current body, linked parent/children, the relevant `docs/` files) and
   hands that — not the pipeline's history — to a fresh `Agent` call using the matching
   persona in `.claude/agents/pilot-*.md`.
2. **Claim/label bookkeeping is deterministic tool calls in the skill itself**, not
   something the agent reasons about. Only the actual thinking — writing the story,
   challenging the ticket, writing the spec, writing the code, reviewing the PR — goes
   through an `Agent` call.

A human driving several phases back to back for the same ticket passes forward only the
ticket number between them — never a running transcript of the prior phase's `Agent` call.

---

## 6. Phase 5 — Review Consensus

Claim/pool mechanics are the ordinary claim protocol (§4) — nothing phase-5-specific there
beyond its own pre-claim/in-progress pair, `status:review-ready`/`status:in-review` (§3).
What's specific to phase 5 is how it reaches a verdict:

**Reviewer set** — decided by **the ticket's own `type:`** (§2 "`type:` is never
inherited" — a `level:task` under a `type:feature` story can itself be `type:tech`, and is
reviewed as `type:tech`, never as if it inherited `type:feature` from its parent):
`pilot-pm` + `pilot-architect` + `pilot-techlead` for `type:feature`/`type:e2e`,
`pilot-architect` + `pilot-techlead` only for `type:tech`/`type:bug`. Three distinct,
non-overlapping lenses — product fit/e2e-flow validation, conformance to the
security/architecture decisions recorded at scope time, spec conformance and code
quality/maintainability — deliberately not split into a fourth reviewer, since
`pilot-dev`/`pilot-e2e` already self-reviewed the diff before opening the PR (§4
"Interaction modes"). All reviewers run **in parallel, fully independent of each other** —
none sees another's verdict — in both pair and `--auto` (below); nothing later in the run
reopens that isolation, not even the one pair checkpoint.

Before voting, each reviewer re-runs this project's own build/test/lint commands directly
against the PR's branch rather than trusting the PR description's claim that they pass — a
mismatch is an automatic block, always tagged `change` (below). Once this project has a CI
workflow covering the affected area, a red or pending check on the PR's head commit is the
same kind of automatic `change` block. Until CI exists, this re-run is PILOT's only safety
net.

**`change`/`decision` tags** — each reviewer returns a verdict: approve, or block with one
or more points tagged either `change` — a concrete fix the reviewer can articulate — or
`decision` — a genuine judgment call with no fix to propose until a human weighs in.
Default to `change` whenever a fix can be named. Once every reviewer's verdict is in, the
tags decide the outcome — approve, `change`-tagged, or `decision`-tagged only — which in
turn decides the review event below and, for a block, whether it's `status:changes-requested`
or `status:in-review` stays (§3); either way `needs-human` is added.

**Checkpoint the outcome as a pending review** — the moment the outcome above is decided,
before anything else: create a GitHub PR review with no event, pinned to the PR's current
head commit — a draft, visible only to this run's own identity, with the body already
written out in full. This is phase 5's version of the incremental checkpoint writes every
other pair-capable phase makes (§4 "Interaction modes") — durable the instant it exists, so
an orphaned run (§4 "Resuming an orphaned claim") can recover it instead of re-running the
reviewers.

**Pair (default) vs `--auto`** (§4 "Interaction modes") — never mid-review (the reviewers
already ran fully isolated by the time this is reached), and never for the decision-only
outcome either: §3's `needs-human` rule requires the block itself to reach GitHub before
any resolution, even a live one ("one path, not two... it never removes it silently") — so
that pending review is submitted immediately regardless of mode, exactly as `--auto` would.
Only once it's submitted does pair mode's live value apply: if a human is live and answers
right there, resolve it the same way any other phase resolves a live `needs-human` block
(§3 "A human is live in the same session") — apply their answer, determine the
now-corrected outcome (approved, still blocked with `change` points, or the `decision`
block genuinely stands as originally raised), and submit **one more** review reflecting it
(below) — this keeps GitHub's own review status honest, not just the ticket's label. No
answer on the spot → the ticket waits async like any other unresolved `needs-human`, one
review standing until a later run resolves it. The all-approve and any-`change` outcomes
are where the pair checkpoint actually applies instead — nothing for a human to decide
there (an approval or a code-level fix isn't a judgment call), but still worth a last look
before the pending review is submitted: an approval (and any `--merge`, below) or a
`changes-requested` goes out only once confirmed; `--auto` skips this pause and submits
immediately.

Submitting means turning that pending review into a real one — never a plain issue comment
for this — its event matching the outcome (all-approve → an approval; any-`change` → a
request for changes; decision-only → a plain comment, since there's nothing code-level to
request and it isn't an approval either). Exactly **one** submitted review per run, except
the one case above where a live resolution submits a second, corrected review right after
the first — never more than that, and never one review per reviewer; the aggregation step
is what keeps this from turning into review-bot noise, the same principle one consolidated
comment used to serve.

**Merge, only with `--merge`:** an all-approved outcome merges the PR itself, using the
repository's normal merge method, only when `/pilot-review` was run with `--merge`;
otherwise, or on any other outcome, phase 5 never merges — a human merges by hand, same as
always. Either way, `status:done` and the cascading-completion check follow from the merge
exactly as described in §3 "`status:done`".

---

## 7. Phase 6 — Human QA (`type:feature` only)

Every other phase in this document is agent-driven, code-level work. Phase 6 is neither:
it's a human physically exercising the shipped, integrated feature and saying whether it
actually behaves as intended — the one check in PILOT no agent can perform on its own,
because it requires a real environment and a real person's judgment on the experience, not
just the diff. `type:tech`/`type:bug` tickets never reach this phase: a `type:tech` split
cascades straight to `status:done` once all its tasks are done (§3 "Cascading
completion"); a `type:bug` ticket — always a standalone `level:task`, never split (§2
"Three levels") — reaches `status:done` directly once its own PR merges.

### When it fires

Set by §3 "Cascading completion": once a `type:feature` story's e2e task (and therefore
every dev sibling it depends on, per "End-to-end test tasks" above) reaches `status:done`,
the story itself lands on `status:qa` instead of `status:done` — unclaimed, unassigned,
the pool `/pilot-qa` picks from.

### Running it

`/pilot-qa` is **pair-only** — no `--auto`, never Routine-driven — same as `/pilot-story`.
It claims the story (§4 "Claim Protocol": `status:qa` → `status:in-qa`), builds a manual
test plan from its acceptance criteria and each task's spec/PR, and walks the human through
it case by case until every case is confirmed or a failure surfaces. Each failure is
classified the same way a raw bug report is (§2 "Prerequisite bug tickets (phase 2, phase
4, or phase 6)"): a genuine defect, or actually a different/new need in disguise. Whenever
it genuinely can't tell on its own, that's a live `needs-human` block like any other (§3) —
labeled and commented immediately even with the human right there, then resolved and
cleared in the same turn once they answer (§3 "A human is live in the same session").

Applying the result:
- **All confirmed, or every failure resolves to "not actually a bug"** → `status:done`,
  issue closed — the one place a phase skill sets `status:done` directly, since there's no
  PR merge here for `pilot-status-on-merge.yml` to react to. Report any "not actually a
  bug" finding to the human so they raise it via phase 1 themselves.
- **One or more real-bug failures** → a `type:bug` ticket per failure, originated directly
  as `level:task`/`status:spec-ready` (§2 "Three levels" — never through phase 2), then the
  story itself unclaimed (`status:in-qa` → `status:qa`) with a comment naming the new
  ticket(s) — same mechanics as a bug found mid-implementation in phase 4 (§2 "Prerequisite
  bug tickets"). Takes priority over a same-pass "not actually a bug" failure — the story
  can't be done while a real defect is still open.
- **A failure still unresolved** (nobody answered on the spot — should be rare, pair-only)
  → the `needs-human` label and comment stand, `status:in-qa` stays, resolved later like
  any other `needs-human` ticket.

Never invokes `pilot-e2e`/`pilot-dev` — an originated `type:bug` ticket goes straight to
`status:spec-ready` for `/pilot-spec` to pick up next, never handed to phase 4 directly
from here.
