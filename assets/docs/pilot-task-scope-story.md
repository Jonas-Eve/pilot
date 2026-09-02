# PILOT task — Scope an already-created story

Injected by `.claude/skills/pilot-scope/SKILL.md` into the `pilot-architect` persona's
prompt, alongside `docs/pilot-link-bug-tickets.md` in full for step 5's "Prerequisite
(bug)" case.

**Challenging it first**: push back where it matters before deciding how to scope —
ambiguous requirements, technical risk, anything touching this project's own
identity/security/architecture boundaries, or anything out of step with its recorded
system design, network topology, or multi-tenancy model (your own identity's project-doc
habit is what surfaces these). If something needs a human decision to scope responsibly,
say so — don't guess and move on.

You receive an existing `type:feature` or `type:tech` story (its current body — already
scoped once before, if this is a re-scope) — never `type:bug`: a bug is always created
directly as `level:task`, `status:spec-ready`, so it never reaches you here
(`docs/pilot-process.md` §2 "Three levels"). You may also be given its parent Epic and
linked tickets for context; feel free to read further related tickets yourself (a
sibling story under the same Epic, something referenced via "Blocks #M"/"Depends on
#N") — e.g. to avoid proposing a prerequisite a sibling ticket already covers.

**If this is a re-scope of a story whose split already finished once** (the skill
claimed it from `status:qa`/`status:in-qa` into `status:scoping` before calling you —
the one deliberate backward transition in the state machine, `docs/pilot-process.md`
§2 "Re-scoping a `type:feature` story after its split is done") — you're also given
which tasks from the earlier round(s) are already `status:done`, including the
original e2e task(s). Steps 4/4a below still apply, scoped to *this round only*:
propose new tasks for the new work, plus exactly one new `type:e2e` task extending the
existing e2e coverage rather than duplicating it (never reopen or touch the
already-done one), and run the PM coverage check (step 4a) against this round's new
`type:feature` tasks only — the earlier ones were already checked when proposed.

1. Claim the ticket per the protocol in `docs/pilot-process.md` §4 before starting.
2. Challenge it (above).
3. Decide whether it needs building at all: if challenging it convinces you it's out
   of scope, a duplicate, or superseded, propose `status:wont-do` instead of scoping
   it — but only when clear-cut. If it's a judgment call, flag `needs-human` instead
   with a comment stating why and exactly what you need decided. This is a
   phase-2-only option — once a ticket has a spec or code, killing it is always a
   human call (`docs/pilot-process.md` §3). If instead the ticket simply can't move
   forward yet because it depends on unresolved work elsewhere (a global
   restructuring, another ticket/Epic not yet done) — not a decision needing someone's
   judgment — that's `on-hold`, not `needs-human` (`docs/pilot-process.md` §3
   "`on-hold`").
4. Decide the split shape — this branches by `type:` (`docs/pilot-process.md` §2
   "Three levels"; `docs/pilot-link-e2e-tasks.md`):
   - **`type:tech`**: splitting is still your judgment call — fine to leave it as one
     ticket through phases 3-4, in which case reconfirm or revise the `priority:` set at
     phase 1 (`docs/pilot-process.md` §3 — it stays the ticket's own, since it's still
     the one leaf). If you do split, propose one dev-sized task per unit,
     along vertical slices (each a coherent, ideally independently shippable/testable
     piece) rather than by technical layer — a front-end-only or back-end-only task is
     rarely reviewable or testable alone, unless the two are genuinely decoupled (e.g.
     a backend API meant to be consumed later, independently). No e2e task either
     way — skip step 4a.
   - **`type:feature`: always split, never a single unsplit ticket.** Propose one or
     more dev tasks (one is enough for a small story — the only real judgment call
     left is *how many*, and each one's own `type:`, never *whether* to split at all),
     along the same vertical-slice principle above, **plus** go to step 4a for the
     mandatory e2e task. A dev task's own `type:` is whatever fits *that task*, not
     automatically `type:feature`: a technical enabler the feature tasks depend on (a
     migration, shared infra) is its own `type:tech` task in the same split, free to
     block the feature tasks the ordinary way (step 5 "Between tasks of the same
     split").
4a. **`type:feature` only**: propose exactly one additional task titled
    "E2E: <story summary>" (or "E2E: <story summary> (round N)" for a re-scope round,
    per the note above) — covering every case of the story's flow worth exercising,
    not just a happy path — labeled `type:e2e` (its own type, not stacked with
    anything else). It depends on **every** other task from step 4, dev *and* tech
    alike, from *this round* ("Depends on #N", one line per sibling — not a subset,
    and never the earlier round's already-`status:done` tasks,
    `docs/pilot-link-e2e-tasks.md`). Exclude it, and any `type:tech` task from step 4, from
    the PM's coverage check below — tell the PM to check coverage against the
    `type:feature` tasks only, since neither a tech enabler nor the e2e ticket itself
    implements an acceptance criterion.
5. Decide dependencies, split or not:
   - **Prerequisite (tech)** — the ticket (or one of its proposed tasks) depends on
     technical work that isn't part of it at all (infra, CI, a shared library, a
     migration) — no defect implied; applies to a `type:feature` ticket just as much
     as a `type:tech` one. Propose it exactly the way you'd formalize a raw
     `type:tech` need (`docs/pilot-task-formalize-tech-need.md`) — one story, or several
     under a new/reused Epic, each its own `level:story` — **never** as a sub-issue of
     the ticket you're scoping (`docs/pilot-process.md` §2 "Prerequisite tech
     tickets"): that would make it `level:task` and wrongly tie it to this ticket's
     split-tracking lifecycle instead of its own phases 2-5. State whether it's a
     **hard blocker** ("Depends on #N", `docs/pilot-process.md` §4 "Blocked-by
     dependencies") or a plain non-gating reference.
   - **Prerequisite (bug)** — while scoping, you instead run into something that
     looks like a concrete *defect* in already-shipped code outside the ticket's own
     scope, not an ambiguity within it. Classify and, if genuine, originate it per
     the mechanic passed alongside this task doc (`docs/pilot-link-bug-tickets.md`)
     — then finish scoping this ticket normally afterward: it isn't claimed by
     phase 3/4 yet, so recording the dependency is enough, no unclaiming needed.
   - **Between tasks of the same split** — if two of the tasks you're proposing
     depend on each other (e.g. a front-end one consuming an API a back-end one
     creates), record it the same way ("Depends on #N" on the dependent one,
     `docs/pilot-process.md` §2 "Dependencies between tasks of the same split").
6. Label every task `level:task` (never on the story itself once it's `status:split` —
   the story keeps its own `level:story`, but loses its own `priority:` label here,
   superseded by its tasks' own, `docs/pilot-process.md` §3) and its own `type:` per
   steps 4/4a above — never copied from the story, `docs/pilot-process.md` §2 "`type:` is
   never inherited". Set a `priority:P0/P1/P2` on each: for a `type:tech` story's tasks,
   or a `type:tech` enabler task inside a `type:feature` split, use the technical framing
   (`docs/pilot-process.md` §3 — P0 closes a real security/correctness/safety-net gap, P1
   solid value but not urgent, P2 nice-to-have or conditional); for a `type:feature` dev
   task, default to the story's own initial (PM-set) priority unless this specific task's
   urgency genuinely differs from its siblings. Adopt this project's own priority
   convention instead, if it already has one that differs.
7. Write explicit **Security decisions** and **Architecture decisions** sections into
   each ticket's body — the concrete choices made (or the reason none were needed),
   not just a restatement of the requirement. These are what phase 3 builds against
   and what you check conformance against in phase 5 (`docs/pilot-task-review-architecture.md`).
