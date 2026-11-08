# PILOT link — ticket types, levels and the tree

Read by `pilot-discovery`, `pilot-spec` and `pilot-qa`, and cited by the link docs for bug tickets, e2e tasks and epic descent. `.pilot/pilot-process.md` §3 holds the vocabulary (the labels and what they mean);
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
  the architect validates them (`.pilot/pilot-link-roster.md` "Roster"), anticipating architecture (interfaces, infra
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
"Prerequisite tech/bug tickets" in `.pilot/pilot-link-split-tickets.md` and `.pilot/pilot-link-bug-tickets.md`); and the PM's own
involvement when a `type:feature` story gets split — see "Three levels" below.

## `type:` is never inherited

Each task the architect+tech lead create when splitting a
story gets its own `type:`, assigned for what that specific task actually is — not copied
from the story above it. A `type:feature` story's split is typically a mix: one or more
`type:feature` tasks doing the user-facing work, sometimes a `type:tech` task alongside
them for a technical enabler the feature tasks depend on (a migration, a shared piece of
infra) — free to block the feature tasks the ordinary way ("Dependencies between tasks of
the same split", `.pilot/pilot-link-split-tickets.md`) — and always exactly one `type:e2e` task
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
