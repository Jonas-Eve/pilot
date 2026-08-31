# PILOT — Ticket Pipeline (Simplified Multi-Agent Process)

PILOT is this repo's lightweight, in-house multi-agent ticket process: specialized agent
personas take a piece of work from a raw idea to a merged PR, with few tokens spent per
ticket — five short, focused phases, each phase running in its own isolated agent context
rather than one context accumulating the whole ticket's history.

**P**lan → **I**nvestigate → **L**ay out → **O**perate → **T**est & validate.

`type:feature` stories carry one more, mandatory phase 6 after those five — Human QA,
§7 — a manual, human-paired acceptance check at the story level once every task is
done, before the story itself reaches `status:done`. `type:tech`/`type:bug` tickets never
go through it.

This document is the source of truth for the process: the state machine, the GitHub
label conventions, the claim protocol, and how the phases fit together. The agent
personas (`.claude/agents/pilot-*.md`) and the skills that drive them
(`.claude/skills/*/SKILL.md`) both reference this file rather than repeating it —
keep this document accurate first, then bring those files in line with it (per this
project's own documentation-maintenance convention, if it has one).

---

## 0. Prerequisites & Quickstart

**The GitHub labels below must exist in this repository before any PILOT skill runs.**
No skill creates them on the fly — applying a label that doesn't exist yet fails the
GitHub API call outright, not silently. Create them once (repo Settings → Labels, or
the GitHub API/CLI):

`type:feature`, `type:tech`, `type:bug`, `type:e2e`, `level:epic`, `level:story`,
`level:task`, `priority:P0`, `priority:P1`, `priority:P2`,
`status:draft`, `status:backlog`, `status:scoping`, `status:spec-ready`, `status:in-spec`,
`status:dev-ready`, `status:in-dev`, `status:in-review`, `status:changes-requested`,
`status:approved`, `status:wont-do`, `status:split`, `status:qa`, `status:in-qa`,
`status:done`, `needs-human`, `on-hold`.

Each phase is a Claude Code slash command, run from a session with read/write access to
this repo's issues and PRs. Nothing in PILOT triggers itself as reasoning — every phase
runs because something sent its exact command as a literal message, whether that's a
human typing it or a scheduled Routine doing the same on a timer (§4 "Scheduled sweeps").
Bare, no-argument commands are what make the scheduled case useful — see below:

```
/pilot-story "let a user filter search results by wheelchair accessibility"
    → opens a type:feature issue (PM agent, auto-detected)

/pilot-story "add the GitHub Actions CI workflow described in our tech-debt backlog"
    → opens one or more type:tech issues (architect agent, auto-detected)

/pilot-story --tech "..."   → skips detection, declares the need type:tech upfront
/pilot-story --bug "clicking export on the reports page throws a 500"
    → skips detection, declares it type:bug upfront (architect agent)
/pilot-story --resume 12    → picks back up a status:draft ticket left mid-pair

/pilot-scope 42        → scopes/decomposes existing issue #42
/pilot-spec 42         → writes the technical spec for #42 (must be status:spec-ready)
/pilot-dev             → claims and implements the next status:dev-ready ticket, no
                          argument needed
/pilot-dev 42          → claims and implements #42 specifically
/pilot-review 57       → runs phase 5 against PR/issue #57
/pilot-qa 61           → runs phase 6 (human QA) against story #61 (must be status:qa)
```

There's no single command that runs all six phases end to end — drive the pipeline one
phase at a time, per ticket.

Every phase skill also runs bare, with **no argument at all** — it then works its normal
pool of fresh candidates (its own pre-claim `status:`) *and* its own `needs-human`/
`on-hold` tickets whose flag has since been cleared (§4 "Picking the next ticket..." and
"Scheduled sweeps"). This is what a cron Routine calls on a timer — literally bare for
`/pilot-review` (no ticket number ever computed on its behalf); with `--auto` added for
`/pilot-scope`, `/pilot-spec`, and `/pilot-dev`, which default to pair and need that flag
to run unattended (§4 "Interaction modes"). `/pilot-story` and `/pilot-qa` are pair-only
and are never Routine-driven at all.

---

## 1. The Six Phases

| # | Phase | Skill | Agent | Produces |
|---|-------|-------|-------|----------|
| 1 | Plan | `/pilot-story` | `pilot-pm` (`type:feature`) or `pilot-architect` (`type:tech`/`type:bug`) — auto-detected from the need, `--tech`/`--bug` to declare it upfront | A functional user story, formalized technical need, or bug report, or an Epic + several stories, for any `type:` — content only, no dependency/prerequisite analysis. The ticket exists as `status:draft` until the human's final approval (§3) |
| 2 | Investigate | `/pilot-scope` | `pilot-architect` — plus `pilot-pm` when a `type:feature` story is split | The story itself scoped (`type:tech`/`type:bug` only), or split into dev-sized tasks ready for spec — mandatory for `type:feature` (dev task(s) + one e2e task, §2 "End-to-end test tasks"), a size judgment call for `type:tech`/`type:bug` — with dependencies recorded (prerequisite ticket(s) and/or between sibling tasks) — plus, either way, a wont-do verdict where applicable |
| 3 | Lay out | `/pilot-spec` | `pilot-techlead` | A technical spec written into the ticket (the test plan itself, for an e2e task) |
| 4 | Operate | `/pilot-dev` | `pilot-dev`, or `pilot-e2e` instead for a `type:e2e` task | An implementation + pull request (following `.github/pull_request_template.md`) |
| 5 | Test & validate | `/pilot-review` | `pilot-pm` + `pilot-architect` + `pilot-techlead` (feature) or `pilot-architect` + `pilot-techlead` (tech/bug) | A GitHub comment: either blocking points for a human (`needs-human`, plus `status:changes-requested` if any are code-level) or a consolidated go-ahead (`status:approved`) — a human always does the actual merge |
| 6 | Human QA (`type:feature` only) | `/pilot-qa` | `pilot-qa` | A human-confirmed `status:done` on the story once every task has merged, or a `needs-human` flag with what failed (§7) |

There is no single global-orchestrator command — each phase skill is invoked on its own
(`/pilot-scope 123`, etc.), as its own isolated agent call (see §5), one phase at a time.

## 2. Ticket Types And Levels

Two independent axes classify every ticket, and neither is inherited from a parent to a
child — every ticket carries its own of each, assigned for what that specific ticket
actually is, never copied down a tree:

- **`type:`** (this section) — the *nature* of the work: `feature`, `tech`, `bug`, or
  `e2e`. Decides which agent handles phase 1 (where applicable) and the phase-5 reviewer
  set (§6) for that ticket specifically.
- **`level:`** ("Three levels" below) — *depth* in the tree: `epic`, `story`, or `task`,
  capped at exactly these three, never deeper.

Every ticket goes through phase 1 (creation) before phase 2 (decomposition) — `type:`
decides only which agent phase 1 calls, never whether phase 1 runs at all. Phase 1 is
purely about identifying and formalizing what the need actually is — never about
dependencies, prerequisites, or splitting; that's entirely phase 2's job (below):

- **`type:feature`** — a human describes an idea in free text to `/pilot-story`; the PM
  agent formalizes it into a user story. Phase 5 review involves all three agents (PM
  checks product fit against the story's acceptance criteria).
- **`type:tech`** — a human describes a technical need in free text to the same
  `/pilot-story`; the architect agent formalizes it into a story (or several) in place of
  the PM — there is no separate ticket-creation skill, it's the same act either way, just
  a different agent behind it. Phase 5 review is architect + tech lead only; the PM is
  never involved.
- **`type:bug`** — a human reports broken behavior in already-shipped code via
  `/pilot-story --bug`, or it's discovered inline while another ticket is being scoped or
  implemented (see "Prerequisite bug tickets" below) instead of being reported through
  `/pilot-story` directly. Either way, the architect formalizes/originates it — same agent
  as `type:tech`, since a bug fix is a technical correction, not a new product decision.
  Phase 5 review is architect + tech lead only, same as `type:tech`; the PM is never
  involved, even when the bug was found via an end-to-end test on a `type:feature` flow —
  that story's acceptance criteria were already validated once when it shipped, and a
  regression fix against them isn't a new product judgment call.
- **`type:e2e`** — never created via phase 1 (there's no raw "e2e need" a human reports
  from scratch) — always originated by the architect during phase 2, as the one mandatory
  end-to-end-test task every `type:feature` split produces (see "End-to-end test tasks"
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
architect for `type:tech`/`type:bug`; `type:e2e` is never phase-1-created at all), even
when the origin is a five-word request from a person. Phase 2 (`/pilot-scope`) always uses
the architect regardless of `type:` — challenging/decomposing an already-created story is a
technical judgment call either way, never the PM's on its own. The one exception is a
prerequisite tech or bug ticket the architect originates itself, inline, mid-phase-2
scoping pass — see "Prerequisite tech tickets" and "Prerequisite bug tickets" below; the
other is the PM's own involvement when a `type:feature` story gets split — see "Three
levels" below.

**`type:` is never inherited.** Each task the architect creates when splitting a story
gets its own `type:`, assigned for what that specific task actually is — not copied from
the story above it. A `type:feature` story's split is typically a mix: one or more
`type:feature` tasks doing the user-facing work, sometimes a `type:tech` task alongside
them for a technical enabler the feature tasks depend on (a migration, a shared piece of
infra) — free to block the feature tasks the ordinary way ("Dependencies between tasks of
the same split" below) — and always exactly one `type:e2e` task ("End-to-end test tasks"
below). A purely technical enabler task shouldn't get a PM review it has nothing useful to
say about (§6 "Determine reviewers"), and a task's own `type:` is what routes that review —
not which story it happens to sit under.

### Three levels: `level:epic` → `level:story` → `level:task`

Every ticket also carries a `level:` label — depth in the tree, capped at exactly three,
never deeper: a `level:task` is never itself split into further tasks. If phase 3
discovers one is still too big, that's an estimation problem to fix by re-spec'ing it or
re-splitting the *story* differently — never a reason for a fourth level. `level:epic` is
not the same thing as a story split into tasks — the two are different levels and easy to
conflate. Symmetric for both entry points:

- **`level:epic`** (alongside `type:feature`, `type:tech`, or `type:bug`) — groups several
  **`level:story`** tickets under a shared theme, for categorization ("CI", "wheelchair
  filtering across the app"). Never itself scoped, spec'd, or built — no `status:` label.
  Created by the PM (`type:feature`) or the architect (`type:tech`/`type:bug`) during
  phase 1, at the same moment a story would otherwise be created, the instant it's clear
  the idea can't be delivered as a single story. **Stays open and is closed by hand,
  always** — unlike a split story's tasks (a fixed set decided once, §3 "Cascading
  completion"), new stories can be added to an Epic at any point, so its completeness is
  never something PILOT can prove on its own.
- **`level:story`** (`type:feature`/`type:tech`/`type:bug`, `status:backlog` at creation)
  — one functional or technical unit, exactly what phase 1 always produces. Whether or not
  it belongs to an Epic, it always goes through phase 2 on its own, where the architect
  decides whether it needs splitting into tasks.
- **`level:task`** — the architect splits a story into dev-sized tasks. The story that got
  split now gets `status:split` instead (§3) — it is still just a `level:story`, one level below an Epic,
  not an Epic itself. Split along vertical slices (each task delivers a coherent, ideally
  independently shippable/testable unit) rather than by technical layer — a front-end-only
  or back-end-only task is rarely reviewable or testable on its own, unless the two
  are genuinely decoupled (e.g. a backend API meant to be consumed later, independently).
  - **`type:tech` story (and, for now, `type:bug`)**: splitting is still a judgment call —
    "it's fine for it not to" (§2 "Scoping an already-created story" in
    `pilot-architect.md`), a well-scoped story can carry itself through phases 3-4 as a
    single ticket, `level:story` the whole way, never split into `level:task`s.
  - **`type:feature` story: splitting is never optional.** A feature story always ends up
    `status:split` with **at least two** tasks — one or more tasks doing the dev work
    (typically `type:feature`, sometimes mixed with a `type:tech` enabler, above) plus
    exactly one `type:e2e` task — never a single unsplit ticket carried through phases 3-4
    directly. See "End-to-end test tasks" below for why, and §7 "Phase 6 — Human QA" for
    what this makes possible once every task is done. The architect's real judgment for a
    feature story is how many tasks it needs and what each one's own `type:` should be
    (one `type:feature` task is enough for a small story) — never *whether* to split at
    all.
  Either way, **for a `type:feature` story**, the PM is also invoked to check the proposed
  `type:feature` tasks still collectively cover the original story's acceptance criteria
  before it's finalized (excluding any `type:tech` or `type:e2e` task from that check —
  neither implements a criterion, see "End-to-end test tasks" below) — a split that
  quietly drops part of what the story promised would otherwise only surface in phase 5,
  after everything's already been built.

**Creating or reusing an Epic** (phase 1, for either type): before creating a new Epic,
check open `level:epic` issues of the matching `type:` for one that already fits the
idea/need by theme — reuse it (attach the new story/stories as sub-issues of it) rather
than creating a duplicate. Only create a new Epic when no existing one fits and the idea
genuinely can't be delivered as one story.

**Phase 2 still claims and works exactly one ticket per invocation** (§4 "Claim
Protocol") — nothing about the above changes that. But nothing stops the architect from
*reading* related tickets for context while scoping that one ticket: the parent Epic (if
any), sibling stories under it, or anything already linked via "Blocks #M"/"Depends on
#N" or a sub-issue relationship — e.g. to avoid spinning out a prerequisite that a
sibling ticket already covers, or proposing a split that conflicts with what a linked
ticket already does. This is read-only context-gathering, not a second claim.

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
the two directions with a plain issue reference: a comment on
the new ticket ("Blocks #M") pointing back, and a line in the body of the ticket being
scoped naming it. Never `sub_issue_write` for this relationship.

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
Reserve `on-hold` for a pause with no single ticket to point at — a global restructuring,
deliberately deferred work — where there genuinely is nothing for a phase skill to check.

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
or a sibling, so nothing new needs to be built for this, just the same phrase used one
level down.

### End-to-end test tasks

**Mandatory for every `type:feature` story, never for `type:tech`/`type:bug`.** A story is
one feature — one integrated flow a human can exercise — so every `type:feature` story
gets exactly **one** end-to-end-test task alongside its dev task(s), covering
every case of that flow worth exercising (think one test *file*/`describe` block with
several cases inside, not a single assertion), not a judgment call the architect makes per
story. `type:tech`/`type:bug` tickets never get one — they have no user-facing flow to
exercise this way, and split there stays purely a size judgment (above).

Title convention: "E2E: <story summary>". A dev-sized ticket like any other, `level:task`
under the story, going through phases 2-5 exactly like its siblings, labeled `type:e2e` —
its own type, never stacked with anything else (§2 intro). No new `status:` on the ticket
itself.

It depends on **every** other task in the same split, dev and tech alike — not a
judgment-selected subset: one "Depends on #N" line per sibling (§4 "Blocked-by
dependencies"; §2 "Dependencies between tasks of the same split"), so it naturally isn't
claimable by phase 3/4 until all of them have merged, and structurally can never be the
ticket that finishes the split before its siblings.

**Excluded from the PM's split-coverage check** (above, "Three levels" — the PM confirms
the proposed `type:feature` tasks collectively cover the original story's acceptance
criteria): neither the e2e task nor any `type:tech` sibling implements a criterion — the
e2e task verifies criteria the `type:feature` tasks already cover, and a `type:tech` task
is an enabler, not a delivered piece of product behavior — so the architect asks the PM to
check coverage against the `type:feature` tasks only.

**Once the e2e task reaches `status:done`, the whole split is structurally
finished** (every dev sibling necessarily already is, per the dependency above) — this is
what triggers §7 "Phase 6 — Human QA" instead of the ordinary cascade straight to
`status:done` (§3 "Cascading completion").

Phase 3 (tech lead) for an e2e task writes the test plan itself as the spec: which
flow, which existing test tooling/framework this project already uses for e2e (its own
docs/CI config, if it has one), and what its dependencies having merged now makes
exercisable end-to-end. **Phase 4 for an e2e task is `pilot-e2e`, not `pilot-dev`** —
`/pilot-dev` (the skill) reads the `type:e2e` label before calling `Agent` and picks the
`pilot-e2e` persona instead, precisely so the agent implementing it gets a context already
tailored to writing a test against real, already-merged integration points rather than
generic implementation instructions. `pilot-e2e` writes the test against that already-merged
behavior — the ticket cannot be marked done with a test that doesn't actually pass. If
running it surfaces a genuine defect in that already-merged code rather than a gap in the
e2e ticket's own scope, that's a bug discovered mid-implementation, not a workaround — see
"Prerequisite bug tickets" below.

### Re-scoping a `type:feature` story after its split is done

Phase 2 only ever scopes a `level:story` — never a `level:task` (a task is the *output* of
scoping, not something scoped again itself; if a task turns out to need further breakdown,
that's re-splitting the *story*, not scoping the task). Within that, `/pilot-scope` handles
an already-once-split `level:story` differently depending on exactly how finished it is:

- **Closed (`status:done` or `status:wont-do`)** — terminal, full stop. `/pilot-scope`
  refuses to claim it: report that it's already closed and stop, no exception. This isn't
  arbitrary — nothing else in PILOT ever moves a ticket backward out of a terminal state (a
  bug found in already-shipped code becomes its own new ticket, "Prerequisite bug tickets"
  above, never a reopening of the original) — reopening a closed issue to re-scope it would
  be the one place PILOT ever did that. The new work gets its own story instead (a plain,
  non-gating "Extends #N" reference in its body is enough to keep the link visible — never
  a sub-issue, same reasoning as a prerequisite ticket, §2 above).
- **`status:qa` or `status:in-qa`** — still reversible, because nothing terminal has
  happened yet: the cascade only just mechanically set `status:qa` the moment the e2e task
  closed, and no human has confirmed anything (`status:in-qa` is one step further — a
  `/pilot-qa` session may even be live — but still short of a verdict). Claiming an issue
  number in either status is a valid, explicit `/pilot-scope` entry point (never part of a
  bare pool, same as `--resume` or a `status:changes-requested` reclaim, §4) — an existing
  `status:in-qa` assignee doesn't block this claim, the architect's claim simply overwrites
  it, the same non-conflict exception a `status:changes-requested` reclaim already gets
  (§4). Post a comment explaining why (new scope found, any in-progress QA session is being
  set aside), then claim it into `status:scoping` — the one deliberate, phase-2-only
  backward transition in the whole state machine; nothing else ever moves a ticket out of
  `status:qa`/`status:in-qa` this way. From here it's an ordinary phase-2 pass, just with
  extra context (which tasks, including the original e2e one, are already `status:done`
  from the earlier round):
  1. Propose the new task(s) the same way as any split (§2 "Three levels" — a mix of
     `type:feature`/`type:tech`, each its own `level:task`).
  2. Propose exactly one new `type:e2e` task for *this round* — never reopen or amend the
     original, already-`status:done` e2e task. Title it distinctly (e.g. "E2E: <story
     summary> (round 2)") and depend only on this round's new task(s) — not the
     already-closed originals, the gate is a no-op for those anyway. Its phase-3 spec
     should say explicitly that its job is to *extend* the existing e2e test asset the
     original task wrote, not duplicate coverage from scratch — point at the original
     task's PR for what already exists.
  3. Run the PM coverage check (§2 above) against this round's new `type:feature` tasks
     only — the original tasks were already checked against the story's acceptance
     criteria at split time; re-checking them again here would be redundant.
  4. Finalize exactly like any other split (§4 "Claim Protocol"): the story lands back on
     `status:split` — the same status it left, now tracking this round's new tasks instead.
  Once this round's new e2e task also reaches `status:done`, the story cascades to
  `status:qa` again exactly as before (§3 "Cascading completion") — the new behavior gets
  its own human QA pass in phase 6, same as the original.
- **`status:split`, original e2e task not yet done** — no special handling needed: the
  story hasn't finished its first round yet, so this is an ordinary re-scope. Add the new
  task(s) to the existing split and extend the *existing* (still-open) e2e task's
  dependencies to also cover them, rather than spinning up a second one.

This applies the same way to a `type:tech`/`type:bug` story that did split (not every one
does, §2 "Three levels") — closed is just as terminal, `status:split` just as reversible
while it's still mid-flight — minus the e2e-task mechanics, which only ever apply to
`type:feature`.

### Prerequisite bug tickets (phase 2 or phase 4)

Distinct from a prerequisite *tech* ticket above (a new technical need, no defect
implied): while scoping (phase 2) or implementing/testing (phase 4) a ticket, the
architect or dev/`pilot-e2e` may instead discover a concrete **defect** in already-shipped
code outside the ticket's own scope — not an ambiguity in what's being built (phase 4's
own spec-deviation path, `pilot-dev.md`, still covers that), a genuine bug. Most commonly
this happens while writing or running an end-to-end test task (above), but isn't
limited to that case.

Whoever finds it originates a new ticket for it using the exact same mechanics as a
prerequisite tech ticket, just `type:bug` instead of `type:tech`: written directly (the
same quality bar as `/pilot-story --bug`'s own phase-1 output — what's broken, how
observed, root cause/fix if known), `status:backlog`, unassigned — never as a sub-issue of
the ticket being worked. Link the two: "Blocks #M" on the new ticket, "Depends on #N" in
the discovering ticket's own body — always a hard blocker, since the discovering ticket
cannot be finished until the bug is fixed.

**Phase 4 needs one thing phase 2 doesn't.** A ticket phase 2 is scoping isn't claimed by
phase 3/4 yet, so recording "Depends on #N" and finishing the scoping pass normally is
enough — the gate (§4 "Blocked-by dependencies") does the rest once phase 3/4 later try to
claim it. A ticket phase 4 is *implementing*, by contrast, is already claimed and
mid-phase (`status:in-dev`, assigned) — the dependency gate alone won't pull an
already-in-progress ticket out of circulation. So from phase 4 (`pilot-dev` or
`pilot-e2e`), also add `on-hold` to the ticket being implemented, with a comment naming the
new bug ticket, before stopping — never push a broken or partial commit in the meantime. A
human (or the same agent) removes `on-hold` once the bug ticket reaches `status:done`, and
only then resumes the original with `--resume`.

---

## 3. Labels

### `type:` — the nature of the work, set independently on every ticket (§2)
- `type:feature`
- `type:tech`
- `type:bug` — a defect in already-shipped code (§2); formalized/originated by the
  architect, reviewed by architect + tech lead only, same as `type:tech`.
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
- `level:story` — the root unit phase 1 always produces (§2 "Three levels").
- `level:task` — a dev-sized unit of a `status:split` story (§2 "Three levels"). Never
  itself split further — depth is capped at these three levels.

### `status:` — the pipeline state machine, one label at a time
```
draft → backlog → scoping → spec-ready → in-spec → dev-ready → in-dev → in-review → approved → done
                      ↓         ↓
                      +---- wont-do (before dev starts) ----+

scoping → split (tracker for tasks, reaches done only by cascade — see below)

split (type:feature only) → qa → in-qa → done (Phase 6 — Human QA, §7 — instead of
cascading straight to done like a type:tech/type:bug split does)

in-review → changes-requested → in-dev → in-review (loop back through dev when phase
5 blocks on something that needs an actual code change — see `status:changes-requested`
below and §6)
```
- `status:draft` — phase 1 (`/pilot-story`) has created the ticket but the human hasn't
  given final approval yet — assigned to whoever's session created it, the moment the
  agent's first draft exists (§4 "Interaction modes"). Mirrors an in-progress `status:`
  below in every way that matters: excluded from every phase's candidate pools (§4
  "Picking the next ticket..."), never picked up bare, only reachable by an explicit
  `--resume <issue>` (§4 "Resuming a paused pair session") or once a cleared
  `needs-human` flag makes it resumable (§4 "Resuming a `needs-human` ticket"). Becomes
  `status:backlog`, unassigned, once the human gives final approval — an Epic still gets
  no `status:` label at all (above), draft or not.
- `status:backlog` — ticket exists, phase 2 hasn't started.
- `status:scoping` — architect has claimed it for phase 2.
- `status:spec-ready` — scoped, not split, ready for phase 3. A freshly created
  task also starts here directly — it was already scoped as part of being created.
- `status:split` — the architect decided in phase 2 this story is too big for one pass
  through phases 3-4 and broke it into tasks instead (§2 "Three levels"). The story
  carries no further `status:` transitions of its own from here — it's a tracker for its
  tasks, the same role an Epic plays for its stories, one level down. It reaches
  `status:done` only via cascading completion (below), never directly.
- `status:in-spec` — tech lead has claimed it for phase 3.
- `status:dev-ready` — spec written, ready for phase 4.
- `status:in-dev` — a dev has claimed it for phase 4.
- `status:in-review` — a PR is open, phase 5 is running or about to.
- `status:changes-requested` — phase 5 found at least one blocking point tagged `change`
  (§6): an actionable code-level fix, not just a question for a human to weigh in on. Set
  instead of leaving `status:in-review`, alongside `needs-human` same as any block. Once a
  human clears `needs-human`, `/pilot-dev` claims it like any other pre-claim status (§4
  "Reclaiming a `status:changes-requested` ticket") — reclaiming here is expected to find
  an existing assignee (carried over from the original phase-4 claim) and overwrite it
  rather than treat that as a conflict, unlike a genuinely fresh `status:dev-ready`
  ticket. The dev pushes new commits to the *same* already-open PR (never a second PR for
  the same ticket) and moves the ticket back to `status:in-review` when done — landing it
  in the exact same bare/no-`needs-human` bucket phase 5 already sweeps (§6 step 0), so no
  separate "review this again" pool is needed on that side.
- `status:approved` — phase 5 ran and every reviewer approved (§6) — set instead of
  leaving `status:in-review`. This is the "ready to merge, nothing outstanding" signal a
  human (or an automation) can filter on without reading the review comment itself; a
  human still performs the actual merge, PILOT never does. There's no automatic
  re-review trigger if new commits land on the PR after this before it's actually
  merged — re-run `/pilot-review` on it by hand, or move it back to `status:in-review`
  yourself, before merging.
- `status:wont-do` — the architect concluded during phase 2 that this ticket shouldn't be
  built after all (out of scope, duplicate, superseded) and closed the issue instead of
  scoping it. Only settable from phase 2, before any spec or code has been written —
  once a ticket has reached `status:in-spec` or later, killing it is a human call: flag
  `needs-human` with the reasoning instead and let a human close it.
- `status:qa` — a `type:feature` `status:split` story whose e2e task (and therefore
  every dev task it depends on) has reached `status:done` — set by
  `.github/workflows/pilot-status-on-merge.yml` in place of the ordinary cascade straight
  to `status:done` (§3 "Cascading completion"; §7 "Phase 6 — Human QA"). Never set on a
  `type:tech`/`type:bug` story, and never on a task itself. Unclaimed, unassigned —
  the fresh-work pool `/pilot-qa` picks from.
- `status:in-qa` — `pilot-qa` has claimed it for phase 6.
- `status:done` — merged (or, for a `status:split` story, completed by cascade or, for a
  `type:feature` one, by phase 6 — see below and §7). Not set by any phase skill directly
  for an actionable ticket coming out of a merge (merge is always a human action, outside
  PILOT's control) — set by the `.github/workflows/pilot-status-on-merge.yml` GitHub
  Actions workflow, triggered directly on `pull_request: closed` (gated on
  `merged == true`) and, separately, on `issues: closed`, independent of any agent session
  being alive; see §6. `/pilot-qa` is the one place a phase skill *does* set `status:done`
  directly, once a human confirms the story's behavior in phase 6 (§7).

  **Known limitation:** GitHub only recognizes a
  `Closes #N` reference (populating `closingIssuesReferences`, which the workflow reads)
  when the merging PR's base is the repository's *default* branch — never for a PR
  merged into an intermediate, not-yet-merged branch, even once that branch later reaches
  the default branch itself. If a ticket's implementing PR had to be based on another
  PILOT PR's branch instead of the default branch directly (per this project's own
  git-workflow conventions on dependent/stacked branches, if it documents one), the
  workflow finds zero closing issues on that merge and does nothing — set `status:done`
  on the ticket by hand once everything has actually landed on the default branch. This
  isn't fixable in the workflow itself; it's a GitHub platform behavior.

`level:epic` tickets never carry a `status:` label at all. `status:wont-do` and
`status:split` tickets don't carry any *other* `status:` label — the rest of the state
machine only applies to tickets still actively moving through phases 3-5 themselves
(leaf tickets, or a story that turned out not to need splitting).

### `needs-human` — an orthogonal flag, not a pipeline state

Unlike every label above, `needs-human` never replaces the ticket's current `status:` —
it sits alongside whichever one is already there. When a phase hits something only a
human can decide, it leaves the ticket's `status:` exactly where it was (e.g.
`status:in-spec` stays `status:in-spec`) and adds `needs-human`, plus a comment. That
comment is never optional and is never just the label with no context attached — it must
say, explicitly, both **why** the ticket needs a human right now (what was found, what
decision the phase couldn't make on its own) and **what's needed** from a human to
unblock it (a decision, a missing piece of information, an explicit approval). A label
with no comment, or a comment that only restates "needs a human" without saying why or
what for, is not a valid use of this flag — whoever reads it next (a human, or a phase
skill resuming a different ticket later) has to be able to act from the comment alone,
without reconstructing the agent's reasoning. This is deliberate: collapsing everything
into one `status:blocked` value would throw away *which phase* was mid-work, which is
exactly the information needed to know which phase skill should pick the ticket back up —
see §4 "Resuming a `needs-human` ticket."

**Phase 5 is the one exception to "`status:` stays exactly where it was."** Elsewhere,
the very question a block raises is often what determines what happens next (a phase-2
judgment call might still lead to splitting further, or not; a phase-3 conflict might
still need a re-spec, or not), so `status:` has to wait for the answer. A phase-5 block
tagged `change` (§6) is different: the answer is already known regardless of what a human
says about it — the ticket needs code, so it moves straight to `status:changes-requested`
(above) as part of applying the block, not just `needs-human` on an unchanged
`status:in-review`. `needs-human` itself still only ever sits alongside whichever
`status:` it lands on, in-review or changes-requested — it's phase 5's aggregation step,
not the flag, that moves `status:` here.

A human resolves it by **removing the `needs-human` label** once they've responded (a
reply comment) or decided there's nothing more to add (approve as proposed, no reply
needed) — the label's absence is the whole signal; nothing else needs to change by hand.

**Always add `needs-human` and post the why/what's-needed comment the moment a phase
hits something only a human can decide** — one path, not two, whether or not a human
happens to be live in the same session right then. This is deliberate: an agent that
skips the label or the comment when it *thinks* someone's there to ask is one
interrupted session away from a ticket stuck with no signal on it at all (or a label
with no explanation attached), and no way to tell it apart from any other in-progress
ticket.

What differs by context is only what happens *next* — never whether the flag and its
comment get posted in the first place:

- **Nobody answers on the spot** (a scheduled sweep with no human present, or an
  interactive human who says they need to think about it) — the label and comment stay
  exactly as posted, and the ticket waits for the async resume protocol below, same as
  ever.
- **A human is live in the same session** (an interactive run, not a scheduled sweep —
  below) and answers right there in conversation — the agent still posts the
  why/what's-needed comment first, as part of applying the flag, exactly as it would if
  nobody were around; a quick answer is not a reason to skip straight to a resolution.
  Once the human answers, the agent proceeds with that answer and, in the same turn,
  posts a **second** comment summarizing what was actually decided (the question that was
  asked, and the resolution reached) — *then* **removes `needs-human` itself**. It
  doesn't wait for the human to separately go remove it on GitHub, but it also never
  removes it silently: the ticket's GitHub history must show both the block and its
  resolution even when the conversation that resolved it never touched GitHub at all.
  Whoever reads the ticket later sees the same two-comment trail either way — a blocking
  comment followed by a resolution comment — whether the gap between them was seconds
  (live) or days (async).

#### Cascading completion

This applies to `status:split` stories only — a story's tasks are a fixed set for
whichever round is currently in flight (the original split, or a later re-scope round,
"Re-scoping a `type:feature` story after its split is done" above), so completeness at
any given moment is provable from a live read of its current sub-issues — never a cached
list. An Epic's stories are not
(§2, §3 "type: — set once..." above) — an Epic never auto-closes, a human always closes
it by hand, regardless of how many of its current stories are done.

Whenever a task reaches `status:done` or `status:wont-do`, check whether its parent
is a `status:split` story and, if so, whether *all* of that story's other tasks are
now also done/wont-do:
- Not all done yet → do nothing further, the parent stays `status:split`.
- All done, parent is `type:tech` or `type:bug` → set the parent story itself to
  `status:done` — it was never merged directly, but its work is now finished. This does
  not cascade any further: if that story belongs to an Epic, the Epic still does not
  auto-close (see above) — a human closes it whenever they judge it complete.
- All done, parent is `type:feature` → set the parent to **`status:qa`** instead of
  `status:done` (§7 "Phase 6 — Human QA") — every `type:feature` split includes exactly
  one e2e task depending on all its dev siblings (§2 "End-to-end test tasks"),
  so "all done" here is structurally the same moment the e2e task itself just
  finished. `status:done` for this story is set later, by `/pilot-qa` itself, once a human
  confirms the behavior — not by this workflow.

No periodic sweep exists beyond this — the check is event-driven, not polled (below and
§6). A `status:split` story whose last task was closed without ever carrying
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
could check. Like `needs-human`,
it sits alongside whichever `status:` is already there rather than replacing it, for the
same reason: losing track of which phase the ticket was at would make resuming it later
harder, not easier.

A human applies it directly at any time (no phase skill needs to be running), or a phase
agent applies it itself if it notices mid-work that the ticket depends on unresolved
global work — either way, always with a comment saying what it's waiting on (a linked
ticket/Epic, or a plain description of the restructuring in question). A bare `on-hold`
label with no comment is as invalid as a bare `needs-human` one, for the same reason:
whoever looks at the ticket next has to know what it's waiting for without asking around.

Excluded from every phase's candidate pools exactly like `needs-human` (§4 "Picking the
next ticket..."). Only a human removes it, once whatever it was waiting on has actually
resolved — there's no live-session "answer it and remove it in the same turn" path like
`needs-human` has, because there's no question being asked that a live human could answer
on the spot; lifting it is itself the human's call. Once removed, the ticket is simply a
normal candidate again in whichever pool its current `status:`/assignee state already
puts it in — no special resume handshake, since nothing was actually asked. The two flags
are independent and can coexist (a ticket can be both `needs-human` and `on-hold` at
once); clearing one has no effect on the other.

### `priority:`
- `priority:P0` / `priority:P1` / `priority:P2` — set by the architect, on each
  leaf/task, during phase 2. Not set on `level:epic` or `status:split` tracker
  parents — priority lives on the actionable tickets underneath them. Same rough meaning
  as most backlog conventions: P0 closes a real gap (security, correctness, a broken
  safety net) — do it soon; P1 is solid value, not urgent; P2 is nice-to-have or
  conditional. Adopt this project's own priority convention instead, if it already has
  one that differs.

---

## 4. Claim Protocol (avoiding two agents on the same ticket)

Phases 2, 3, 4, and 6 each start by **claiming** the ticket before doing any real work,
because several instances of the same phase (e.g. several devs) may run concurrently.
Phase 1 doesn't fit this pattern the same way — there's no pre-existing ticket to claim,
since phase 1 is what creates one — but the moment it creates the ticket (`status:draft`,
§3), it assigns it the same way, and that assignment sticks if the pair session ends
before final approval, exactly like a claimed ticket left mid-phase; see "Resuming a
paused pair session" below.

1. Read the ticket's current `status:` and assignee (`mcp__github__issue_read` /
   `pull_request_read`).
2. If it's not in the expected pre-claim status, or already has an assignee, stop — it's
   being worked or has moved on; pick a different ticket (or report nothing to do, if a
   specific ticket number was requested explicitly).
3. Otherwise, immediately set the assignee to the current agent/session and swap the
   `status:` label to the in-progress one for this phase (`issue_write`), in the same
   call where possible.
4. Re-read the ticket once more. If the assignee is no longer this agent, another run won
   the race — stand down and pick something else. This is optimistic, not a real lock:
   it's cheap insurance against the common case (two devs starting around the same time),
   not a guarantee under true concurrent writes, but that's an acceptable trade-off at
   the scale of a handful of parallel agents.
5. Only after a successful claim does the phase's real work (the subagent call) start.

Phase 5 does **not** claim — the three (or two) reviewers run in parallel by design, not
in competition for the same ticket.

### Picking the next ticket when none is specified

Phase 1 has no such pool at all — it always starts from a raw need in free text (or an
explicit `--resume <issue>`), never from picking an existing ticket, so nothing below
applies to it. When any other phase skill is invoked without an explicit ticket number,
it builds its candidate pool from **two** queries, not one
(`mcp__github__search_issues` / `list_issues`):
1. **Fresh work** — tickets in its own pre-claim `status:`, no assignee (as before: e.g.
   `status:spec-ready` for `/pilot-spec`).
2. **Resumable work** — tickets already in its own *in-progress* `status:` (e.g.
   `status:in-spec` for `/pilot-spec`), still carrying the assignee from when they were
   originally claimed, but **no longer** carrying `needs-human` — see "Resuming a
   `needs-human` ticket" below for what that means and how to proceed once picked.

`/pilot-dev` alone has a **third** pool: tickets in `status:changes-requested` with
`needs-human` no longer present — phase 5 sent these back for an actual code fix (§6),
and they're a distinct case from both of the above, not a "fresh" ticket and not a
same-claim "resume" either. See "Reclaiming a `status:changes-requested` ticket" below.

All pools that apply to a given phase skill are merged and picked from together: highest
`priority:` first, then a ticket referenced by another open ticket's "Blocks #M" comment
(§2 "Prerequisite tech tickets") before one that isn't — resolving what unblocks something
else is worth more than strict recency — then oldest by creation date to break ties;
untagged tickets sort last. A ticket still carrying `needs-human` or `on-hold` is never a
candidate in any pool — it re-enters only once neither flag remains — and neither is one
whose body has an unresolved "Depends on #N" reference (below, "Blocked-by dependencies")
— it re-enters automatically once #N closes, no flag to remove. A ticket left mid-pair
session (already assigned, still in that phase's in-progress `status:`, but no
`needs-human`) is likewise never a candidate in any bare pool — see "Resuming a paused pair
session" below; it only resumes via an explicit `--resume <issue>`.

### Blocked-by dependencies (mechanical gate, distinct from `on-hold`)

A ticket's body may carry one or more "Depends on #N" references — today, only the
architect writes these, when phase 2 spins out a prerequisite tech ticket it judges a hard
blocker (§2 "Prerequisite tech tickets"), but the mechanism itself isn't specific to that
case; anything that writes the same phrase gets the same gate for free.

**Format: one dependency per line, always.** Multiple dependencies are multiple separate
"Depends on #N" lines, one issue number each — never several numbers combined onto one
line (never "Depends on #12, #15"). This is deliberate: it keeps the check a trivial
per-line literal match, not a list/prose parse the skill would have to get right for every
phrasing someone might use.

Whenever a phase builds a candidate pool from its own `status:` pools (above), it also
reads each candidate's body for this exact phrase and, for each `#N` found, checks whether
that issue is still open (`mcp__github__issue_read`) — plain open/closed, not its
`status:` label, since a closed ticket is `status:done` or `status:wont-do` either way. A
candidate with at least one still-open dependency is excluded from the pool for this run,
the same as `needs-human`/`on-hold` above — but unlike those two, nothing needs removing by
hand: the moment the referenced ticket closes, the next run of that phase picks the ticket
back up as an ordinary candidate. This is a deterministic tool-call check the skill
performs directly (§5), never something the subagent reasons about.

**In phases 3 and 4, the gate applies to an explicitly-given ticket number too, not just
bare-pool selection.** `/pilot-spec` and `/pilot-dev` each run this same check before
claiming any ticket, whether it got there via the pool or because a human named it
directly, and report the blocking `#N` and stop instead of claiming if it's still open —
exactly the same principle already applied to an explicit ticket number still carrying
`needs-human`/`on-hold` (each phase skill's own "given issue number" handling, e.g.
`.claude/skills/pilot-spec/SKILL.md` step 1). Skipping the check just because a number was
given by hand would make the gate trivial to bypass by accident.

**Phase 2 (`/pilot-scope`) is the deliberate exception.** Re-scoping a ticket — revisiting
its decisions, splitting it further — doesn't need its prerequisite resolved first, only
the phases that actually spec and build it (3 and 4) do; `/pilot-scope` doesn't check this
gate on an explicitly-given ticket number, and it never meaningfully fires from phase 2's
own bare pool either, since nothing writes "Depends on #N" onto a ticket before phase 2
has scoped it at least once (the phrase is phase 2's own output, per §2 above).

The same reference feeds the ordering tie-break above: a candidate that's itself named in
another open ticket's "Blocks #M" comment sorts ahead of one that isn't, at the same
`priority:`, since spec'ing or building it sooner is what lets that other ticket clear its
own gate.

### Resuming a `needs-human` ticket

A human resolves the flag by **removing the `needs-human` label** from the ticket —
optionally after leaving a reply comment with guidance, or with no reply at all if
there's nothing to add beyond "proceed as proposed." That removal, not a reaction or a
particular comment, is the entire signal a phase skill looks for. This can happen from
any session, at any time — nothing depends on the session that raised the block still
being alive, the same isolation every other phase call already relies on (§5); the full
context (the blocking comment, and anything posted after it) lives on the ticket itself.

A phase skill treats a ticket as **resuming**, not a fresh claim, whenever it's already
in that phase's in-progress `status:` (whether picked up bare, per above, or given
explicitly as an argument):
1. Read the full comment thread (`mcp__github__issue_read` `get_comments`), not just the
   ticket body — the blocking comment and everything posted after it.
2. If `needs-human` is still present, it isn't resolved yet — report that and stop (this
   only matters when a ticket number was given explicitly; the bare/no-argument pool
   above already excludes these).
3. Otherwise, proceed with the phase's `Agent` call, passing both the original blocking
   context and whatever's in the thread after it (a specific reply, or "no reply — treat
   as approved as proposed" if none). The agent proceeds, corrects, or blocks again
   (re-adds `needs-human`, posts a fresh comment) if that still doesn't actually resolve
   things.

### Resuming a paused pair session (`--resume`)

Distinct from both "Resuming a `needs-human` ticket" above and "Reclaiming a
`status:changes-requested` ticket" below: this is for a ticket left mid-**pair**
("Interaction modes" below) — still carrying its original assignee, still in that phase's
in-progress `status:` (`status:draft`, `status:scoping`, `status:in-spec`,
`status:in-dev`, `status:in-qa`), with **no** `needs-human` — the pair session simply ended (the human
stepped away, the session closed) before reaching the phase's final approval. Left alone,
the normal claim-protocol check (above, step 2: "already has an assignee → stop") would
treat this the same as a ticket someone else is actively working right now, which isn't
the case here. For phase 1 specifically, `status:draft` is what makes this possible at
all — before it existed, an interrupted phase-1 session left nothing behind to resume.

`--resume` requires an **explicit ticket number** — it is never part of any bare/
scheduled-sweep pool. Unlike `needs-human`, nothing on the ticket itself distinguishes an
abandoned pair session from one genuinely still in progress elsewhere; only a human
deliberately choosing to pick a specific ticket back up makes reclaiming it safe.

To resume:
1. Read the full ticket — body and comment thread (`mcp__github__issue_read`
   `get_comments`), not just the latest checkpoint. Pair mode's incremental writes
   ("Interaction modes" below) are exactly the state to reconstruct from: what's already
   validated (already written into the body) versus what's still open.
2. Claim it the same way a `status:changes-requested` reclaim does (below) — an existing
   assignee doesn't count as a conflict here, carrying one forward from the original pair
   session is the norm, not a signal to stand down. Overwrite it (assignee → this
   session); `status:` stays at its current in-progress value, nothing to change there.
3. Pass the reconstructed state to the phase's `Agent` call as its starting context, in
   place of a fresh, empty brief, and continue the normal pair loop (checkpoint, show the
   human, wait, write) from wherever that leaves off.

Finalization behaves exactly as any other pair run from here — the phase's completion
`status:` is set once the human gives final approval, same as "Interaction modes" below
describes.

### Reclaiming a `status:changes-requested` ticket (`/pilot-dev` only)

Unlike "Resuming a `needs-human` ticket" or "Resuming a paused pair session" above (same
claim, same in-progress `status:`, just re-entering), `status:changes-requested` is set
by *phase 5*
(§6), not by `/pilot-dev` itself — the ticket already has an open PR from the original
phase-4 pass, and whatever assignee is still on it is whoever ran *that* pass, not
necessarily whoever runs `/pilot-dev` next.

Reclaiming one follows the standard claim protocol above with a single, deliberate
exception: an existing assignee doesn't count as "already claimed" for this status —
carrying one forward from the original phase-4 claim is the norm here, not a conflict
signal — the claiming session simply overwrites it (assignee → itself, `status:` →
`in-dev`) and re-reads to confirm the overwrite held, the same optimistic check any other
claim uses.

Once claimed, pass the subagent the phase-5 blocking comment (the `change`-tagged points
to fix, plus any `decision`-tagged points and their resolution) instead of a fresh spec —
there's no new spec to write; the existing PR's branch is what gets more commits. The
subagent pushes to that same branch/PR (never a second PR for the same ticket) and, once
satisfied, moves the ticket back to `status:in-review` exactly as it would after a
first-time implementation — landing it back in phase 5's own bare pool (§6 step 0) for
another review pass.

### Scheduled sweeps

Each phase skill is meant to also run **bare, on a timer** — a Routine (this
environment's scheduled-trigger mechanism) whose prompt is nothing but the literal
command. For `/pilot-scope`, `/pilot-spec`, and `/pilot-dev` — which default to pair mode
("Interaction modes" below) — that literal command must include `--auto`
(`/pilot-spec --auto`, still no ticket number computed by the routine itself), since pair
requires a human live in the session and a Routine has none. `/pilot-review` needs no
flag either way, it's already auto-only, so its Routine's prompt stays a bare
`/pilot-review`. `/pilot-story` and `/pilot-qa` are pair-only with no `--auto` and are
therefore never driven by a Routine at all — phase 6 is a human physically testing
something, there is no unattended version of that. Beyond that flag, this works without
any special-casing because "picking the next ticket when none is specified" (above)
already covers both fresh and resumed work — the routine doesn't need to know which one
it's about to do. Four independent Routines, one per claiming phase skill
(`/pilot-scope --auto`, `/pilot-spec --auto`, `/pilot-dev --auto`) plus one for
`/pilot-review` (which gets the same bare/no-argument pool over `status:in-review` instead
of a claimed status, since phase 5 doesn't claim — see §6), each on its own schedule — not
one combined routine, so a slow or failing phase never delays the others.

### Interaction modes: pair (default) and `--auto`

The six phase skills split into three groups by which modes they support:

- **`/pilot-story`, `/pilot-qa`** — **pair only**, no `--auto` exists for either. Turning a
  raw idea into a story or a technical need into a ticket is a conversation between the
  drafting agent (PM or architect, §2) and a human, not something worth running unattended
  — there is no value in a story nobody validated; symmetrically, phase 6 is a human
  physically testing shipped behavior, which has no unattended equivalent at all. Neither
  is ever driven by a scheduled Routine as a result (above, "Scheduled sweeps"). Both still
  support `--resume <issue>` for a ticket left mid-pair (above, "Resuming a paused pair
  session") — that's a human deliberately picking back up, not unattended automation.
- **`/pilot-scope`, `/pilot-spec`, `/pilot-dev`** — default to **pair**, with `--auto` to
  opt out of it. These three benefit from a human steering the outcome (a decomposition,
  a spec, an implementation approach) but don't strictly require it every time a Routine
  fires, so both modes stay available.
- **`/pilot-review`** — **auto only**, no pair mode exists for it: reviewers run parallel
  and isolated on purpose (§6), with no natural mid-review checkpoint to pause at —
  reviewing shipped work is a judgment call to render, not a draft to iterate on together.

Both modes still claim (above) immediately, same as always — it's concurrency
bookkeeping, unrelated to the content decision.

**Pair** requires a human live in the same session. The agent stops at its phase's
natural checkpoint(s) — the drafted story, the proposed decomposition, the spec outline,
the implementation plan — and the skill relays that to the human as an ordinary reply in
the same conversation, not a GitHub write; it waits for the human's next message, feeds
it back to the agent, and repeats until they approve. **The skill writes progress into
the ticket immediately at every checkpoint** (a comment, or a partial `issue_write`)
instead of holding it in-conversation until the whole phase is done — the ticket itself
becomes the durable record of how far the pair session got, which is what makes
`--resume` possible (above, "Resuming a paused pair session"): if the session ends before
the phase reaches final approval, nothing beyond the conversation itself is lost.

For phases 2-4 a ticket already exists before the phase starts, so this is
straightforward. **Phase 1 is the one case where no ticket exists yet at the very first
checkpoint** — `/pilot-story` creates it right there (`status:draft`, §3) as soon as the
agent's first draft (a single story, or an Epic + several) is ready to show the human,
instead of holding it in-conversation — the checkpoint the human sees *is* the draft
ticket's current body from that point on. Every checkpoint, including the first, is
written immediately from here, the same as phases 2-4; there's no in-conversation-only
exception left. Either way, the very last thing pair mode does — setting the phase's
completion `status:` (`status:backlog`, unassigned, for phase 1; e.g.
`status:spec-ready` for phase 3) — is the same end-state `--auto` reaches in one pass,
for the phases that have an `--auto` (phase 1 doesn't, below).

**Final consolidation pass, every phase, right before setting the completion `status:`.**
Writing progress checkpoint by checkpoint (above) means the ticket (or, for phase 4, the
diff) was assembled incrementally, round by round of the pair conversation — nothing
guarantees a decision from an early round still squares with one added several rounds
later, or that nothing was left half-written in the seams between them. Once the human
gives final approval, before applying the completion label, the agent re-reads the whole
thing as it now stands — the full ticket body, not just the latest round's delta; the
full diff, not just the last commit, for phase 4 — and fixes anything incoherent or
incomplete it finds, the same way it would if it were seeing the finished result for the
first time. This is also what `pilot-dev` uses in phase 4 as its own self-review of the
implementation before opening the PR — a substitute for a separate reviewer checking the
same thing again in phase 5 (§6), not an addition to it.

**`--auto`** is the old default, before pair mode existed: the agent decides everything
and the skill applies the finished result straight to GitHub in one pass, no human
checkpoint. This is what a scheduled Routine must use for `/pilot-scope`, `/pilot-spec`,
or `/pilot-dev` (above, "Scheduled sweeps") — pair requires a live human, so a Routine's
fired prompt for these three must include `--auto` explicitly now that pair is the
default (the reverse of the old rule, back when `--pair` was opt-in: "never combine with
a scheduled sweep"). `/pilot-story` has no `--auto` and is therefore never
Routine-driven; `/pilot-review` needs no flag either way, it's already auto-only.

`--auto` and `--resume` (above, "Resuming a paused pair session") are mutually exclusive
with each other and with pair mode itself — pick exactly one per run.

This is unrelated to the "ask live" behavior in §3 ("`needs-human` — an orthogonal
flag") — that one is for a genuine blocker the agent can't resolve alone and fires
whether or not pair mode is active; pair is for iterating on a draft together even when
nothing is actually blocking.

---

## 5. Token Efficiency: Isolated Contexts Per Phase

Keeping token cost down per ticket is central to PILOT's design. Two rules keep it cheap:

1. **Each phase is a separate agent context**, not one context that accumulates every
   prior phase's transcript. A phase skill reads only what that phase needs from the
   ticket (its current body, linked parent/children, the relevant `docs/` files) and
   hands that — not the pipeline's history — to a fresh `Agent` call using the matching
   persona in `.claude/agents/pilot-*.md`.
2. **Claim/label bookkeeping is deterministic tool calls in the skill itself**, not
   something the agent reasons about. The skill does the GitHub read/write plumbing
   (§4) directly; only the actual thinking — writing the story, challenging the ticket,
   writing the spec, writing the code, reviewing the PR — goes through an `Agent` call.

A human driving several phases back to back for the same ticket passes forward only the
ticket number between them, the same thing each phase skill itself would read off the
ticket — never a running transcript of the prior phase's `Agent` call.

---

## 6. Phase 5 — Review Consensus

0. Resolve the PR/issue: the number given, or — bare, no argument — every `status:in-review`
   PR that either has no `needs-human` flag yet (fresh, never reviewed) or had one and it
   was just removed (resumed, per §4; re-read the thread for what changed since the
   blocking comment), excluding any that currently carries `on-hold` (§3). Phase 5 doesn't
   claim (below), so there's no assignee to filter on — just the presence/absence of
   `needs-human`/`on-hold`. A ticket phase 5 previously sent to `status:changes-requested`
   is **not** in this pool — it's `/pilot-dev`'s to reclaim (§4), and only re-enters here
   once dev pushes it back to `status:in-review`.
1. Determine reviewers from **the ticket's own `type:`** (§2 "`type:` is never
   inherited" — a `level:task` under a `type:feature` story can itself be `type:tech`, and
   is reviewed as `type:tech`, not as if it inherited `type:feature` from its parent):
   `pilot-pm` + `pilot-architect` + `pilot-techlead` for `type:feature` or `type:e2e`,
   `pilot-architect` + `pilot-techlead` only for `type:tech` or `type:bug`. Three
   distinct, non-overlapping lenses on every reviewed PR: PM checks product fit against
   the story's acceptance criteria (`type:feature`) or that the test actually validates
   the story's end-to-end flow (`type:e2e`); architect checks conformance to the
   security/architecture decisions recorded at scope time; tech lead checks both
   conformance to its own spec *and* general code quality/maintainability — deliberately
   not split out to a fourth reviewer, since `pilot-dev`/`pilot-e2e` already did its own
   self-review pass on the diff before opening the PR in phase 4 (§4 "Interaction modes" —
   the same final-consolidation-pass principle every pair-mode phase follows); a second, separate
   agent re-reviewing the same code from the same technical vantage point would be a
   near-duplicate of that self-review, not a genuinely distinct lens the way PM/architect/
   tech lead are from each other.
2. Before any reviewer votes, **re-run validation on the PR's actual branch** — the tech
   lead reviewer does this as part of forming its verdict, using this project's own
   build/test/lint commands (the same ones `pilot-dev` used in phase 4 — see this
   project's own docs for what those are). Reviewers approve based on a result they
   reproduced themselves, not only on the PR description's claim that tests pass; a
   mismatch (validation fails despite the PR saying otherwise) is an automatic block, and
   always a `change`-tagged one (step 3 below) — something in the code needs fixing, it's
   never a judgment call.
   Once this project has a CI workflow covering the affected area, phase 5 additionally
   requires that check to be green on the PR's head commit (`pull_request_read`
   `get_check_runs` / `get_status`) before any approval — red or pending CI is likewise an
   automatic, `change`-tagged block; skip straight to step 4. Until CI exists (or for
   anything CI doesn't cover), this local re-run is the only safety net PILOT has.
3. Run all reviewers **in parallel, independently** — none sees another's verdict before
   giving its own, to avoid anchoring and to keep the round cheap (no back-and-forth).
   Each reviewer returns a structured verdict: approve, or block with one or more
   specific, actionable points, each tagged either `change` — a concrete code-level fix
   the reviewer can articulate (a missing test, the wrong approach, a security gap with a
   known fix) — or `decision` — a genuine judgment call with no fix to propose until a
   human weighs in. Reviewers default to `change` whenever they can say what should be
   different; `decision` is reserved for when the right answer depends on information or
   a preference only a human has.
4. Aggregate into exactly **one** GitHub comment on the PR:
   - Every blocking point across all reviewers (and any CI/validation failure from step 2,
     which is always `change`) is tagged `decision` → one consolidated comment listing
     every point, grouped by reviewer, and add `needs-human` (`status:in-review` stays
     as-is — §3 "needs-human — an orthogonal flag"). This ticket re-enters phase 5's own
     bare pool (step 0 above) once the flag is cleared — a human's answer here doesn't by
     itself imply new code.
   - Any blocking point is tagged `change` (a CI/validation failure from step 2 always
     counts) → one consolidated comment listing every point — both `change` and
     `decision` ones, marked which is which, grouped by reviewer — add `needs-human`, and
     move the ticket to `status:changes-requested` instead of leaving `status:in-review`
     (§3; §4 "Reclaiming a `status:changes-requested` ticket"). `/pilot-dev`, not this
     skill, picks this back up once the flag is cleared.
   - All reviewers approve → one comment stating all agents approve and that merge is
     still a human action; move the ticket to `status:approved` instead of leaving
     `status:in-review` (§3) — no `needs-human` to add, this isn't a block. Human merge
     is still the last step, PILOT never merges.
5. Never post one comment per reviewer — the aggregation step is what keeps this from
   turning into review-bot noise.
6. **After a human merges the PR**, the `.github/workflows/pilot-status-on-merge.yml`
   GitHub Actions workflow (triggered on `pull_request: closed`, gated on
   `merged == true`) resolves the issue(s) the merge closes via
   `PullRequest.closingIssuesReferences`, sets `status:done` on each, and, for any that's
   a task, runs the cascading-completion check from §3 against its `status:split`
   parent story (never a `level:epic` — that always closes by hand) — this runs
   independently of any live agent session, and is the only place `status:done` gets set
   on an actionable ticket; no phase skill sets it directly. `subscribe_pr_activity`
   remains available to a `/pilot-dev` session for other PR-babysitting purposes (e.g.
   surfacing CI failures or review comments back into the session) — it is simply no
   longer relied on for this step.

   The same workflow also triggers on `issues: closed`, for the task completions
   that never go through a PR merge at all: `status:wont-do` (§3), which the architect
   sets and closes directly in phase 2, and any hand-closed issue. This path runs only
   the cascading-completion check (§3) — never `swapToDone`, since the closing party is
   responsible for the issue's own terminal `status:` label, not this workflow — and only
   when the issue already carries `status:done` or `status:wont-do`; a hand-closed issue
   with neither label is left alone (no terminal status to cascade from). It skips
   entirely when GitHub's own timeline shows the closure came from a merged commit
   reference (`Closes #N`) — that case is the `pull_request: closed` trigger's alone, so
   the same closure is never processed twice.

---

## 7. Phase 6 — Human QA (`type:feature` only)

Every other phase in this document is agent-driven, code-level work. Phase 6 is neither:
it's a human physically exercising the shipped, integrated feature and saying whether it
actually behaves as intended — the one check in PILOT no agent can perform on its own,
because it requires a real environment and a real person's judgment on the experience, not
just the diff. `type:tech`/`type:bug` tickets never reach this phase — they cascade
straight to `status:done` once their tasks are done (§3 "Cascading completion"), the
same as before this phase existed.

### When it fires

A `type:feature` story is always `status:split` (§2 "Three levels" — splitting is never
optional for a feature). Its e2e task depends on every dev task in the split
(§2 "End-to-end test tasks"), so the moment that e2e task reaches
`status:done`, every dev sibling structurally already has too — that's the same "all
tasks done" moment §3's cascading-completion check reacts to. For a `type:feature`
parent specifically, that check sets `status:qa` instead of `status:done`
(`.github/workflows/pilot-status-on-merge.yml`) — unclaimed, unassigned, the fresh-work
pool `/pilot-qa` picks from.

### Steps

1. Resolve the story: the given issue number (must be `status:qa` unclaimed, or
   `status:in-qa` already assigned with no `needs-human`/`on-hold` for an explicit
   `--resume`, same shape as every other phase's paused-pair-session case — §4 "Resuming a
   paused pair session"), or — bare, no argument — the merged pool of unclaimed
   `status:qa` (fresh) and `status:in-qa` with `needs-human` just cleared (resumable),
   highest `priority:` then oldest first, same selection rules as every other phase (§4
   "Picking the next ticket..."). `/pilot-qa` is **pair-only**, like `/pilot-story` — no
   `--auto`, never Routine-driven (§4 "Interaction modes", "Scheduled sweeps"): there is no
   meaningful unattended version of a human manually testing something.
2. **Claim** it per §4: assignee + `status:in-qa`, re-read to confirm.
3. Gather context: the story's acceptance criteria (its own body, or its `status:split`
   parent's if this is being read from a task — it never is here, phase 6 only ever
   runs on the story itself, but the acceptance criteria always live on the story), and
   each dev/e2e task's spec and PR — enough for the `pilot-qa` agent to build a
   concrete manual test plan grounded in what was actually specified and shipped, not just
   the original story text.
4. Call the `Agent` tool with `subagent_type: "pilot-qa"`, passing that context. The agent
   returns a manual test plan: concrete cases to test and how to test each, derived from
   the acceptance criteria and the merged tasks — not the running conversation
   history, per the same isolated-context principle every other phase already follows
   (§5).
5. Show the plan to the human (pair, always — this skill has no `--auto`). The human
   performs the tests for real and reports back, case by case; feed each response back to
   the agent until it reaches a final verdict — either every case confirmed, or one or more
   concrete failures.
6. Apply the result:
   - **All confirmed** → set `status:done` and close the issue (`mcp__github__issue_write`)
     — this is the one place a phase skill sets `status:done` on an actionable ticket
     directly, since there's no PR merge here for
     `.github/workflows/pilot-status-on-merge.yml` to react to (§6 step 6). Nothing to
     cascade further — a `type:feature` story is never itself a task of another
     `status:split` parent.
   - **One or more failures** → add `needs-human` with a comment describing exactly what
     failed and how to reproduce it (`status:in-qa` stays, per §3 "`needs-human` — an
     orthogonal flag"). **Provisional, until the bug-handling side of this phase is
     designed**: this stops here rather than originating a `type:bug` ticket itself — a
     human decides what happens next by hand for now.
7. Report the outcome back to the human. Never invoke `pilot-e2e`/`pilot-dev` from this
   skill — a QA failure is a human decision point, not an automatic handoff back into
   phase 4 (unlike phase 5's `status:changes-requested` loop, §6).
