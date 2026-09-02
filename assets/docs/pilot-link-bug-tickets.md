# PILOT link — Prerequisite bug tickets (phase 2, phase 4, phase 6)

Read by `.claude/skills/pilot-scope/SKILL.md` and `.claude/agents/pilot-architect.md`
(phase 2), `.claude/agents/pilot-dev.md`/`pilot-e2e.md` (phase 4), and
`.claude/skills/pilot-qa/SKILL.md`/`.claude/agents/pilot-qa.md` (phase 6) — the three
phases that can originate one of these; no other skill/agent needs it. See
`docs/pilot-process.md` §2/§3/§4 for the generic ticket types, labels, and claim
protocol this builds on.

Distinct from a prerequisite *tech* ticket (`docs/pilot-process.md` §2 "Prerequisite tech
tickets" — a new technical need, no defect implied): while scoping (phase 2),
implementing/testing (phase 4), or manually confirming shipped behavior (phase 6), the
architect, dev/`pilot-e2e`, or `pilot-qa` may run into something that looks like a concrete
**defect** in already-shipped code outside the ticket's own scope — not an ambiguity in
what's being built (phase 4's own spec-deviation path, `pilot-dev.md`, still covers that).
Most commonly this happens while writing or running an end-to-end test task, or during a
phase-6 manual test case, but isn't limited to either case.

**Classify it before creating anything** — the same read `/pilot-story --bug` gives a raw
report (`docs/pilot-process.md` §2 intro): genuinely a code defect against something
already agreed on, or actually a new/different need in disguise. If it's not a bug, don't
create a `type:bug` ticket at all: treat it as a prerequisite *tech* ticket instead if it's
a new technical need, or, if it needs an actual product/judgment decision, leave it for a
human to take through phase 1 themselves rather than originating anything —
`docs/pilot-process.md` §7 "Phase 6 — Human QA" covers the phase-6 version of this
specifically.

If it genuinely is a bug, originate a new ticket for it using the same linking mechanics as
a prerequisite tech ticket (`docs/pilot-process.md` §2 "Prerequisite tech tickets"), just
`type:bug` instead of `type:tech` — with one difference: create it directly as `type:bug`,
`level:task`, `status:spec-ready` — never `level:story`/`status:backlog`
(`docs/pilot-process.md` §2 "Three levels" — a bug never goes through phase 2's own
scoping pass). Written directly (the same quality bar as `/pilot-story --bug`'s own phase-1
output — what's broken, how observed, root cause/fix if known), unassigned, standalone —
never as a sub-issue of the ticket being worked. Link the two: "Blocks #M" on the new
ticket, "Depends on #N" in the discovering ticket's own body — always a hard blocker, since
the discovering ticket cannot be finished until the bug is fixed.

**Phase 4 and phase 6 need one thing phase 2 doesn't: unclaiming, not just linking.** A
ticket phase 2 is scoping isn't claimed by phase 3/4 yet, so recording "Depends on #N" and
finishing the scoping pass normally is enough — the gate (`docs/pilot-process.md` §4
"Blocked-by dependencies") does the rest once phase 3/4 later try to claim it. A ticket
phase 4 is *implementing*, or phase 6 is *confirming*, by contrast, is already claimed and
mid-phase (`status:in-dev` or `status:in-qa`, assigned) — the gate only ever fires when a
phase builds a candidate pool or claims a ticket, so leaving it claimed would just sit
there with nothing ever rechecking it. So from phase 4 (`pilot-dev` or `pilot-e2e`) or
phase 6 (`pilot-qa`), also unclaim the ticket being worked before stopping: clear its
assignee and move it back to its own pre-claim `status:` (`status:dev-ready` for phase 4,
`status:qa` for phase 6) — never push a broken or partial commit (phase 4), or finish the
QA pass as if nothing were wrong (phase 6), in the meantime. For phase 4, first push
whatever's already done to a branch (creating one if none exists yet) and comment on the
ticket naming it, so whichever agent claims it next — the same one or a different one —
resumes from that branch instead of starting over (`pilot-dev.md`/`pilot-e2e.md` cover the
claim-time check for this). The ticket is now an ordinary `status:dev-ready`/`status:qa`
candidate again, gated only by "Depends on #N" like any other — no flag to remove, no
`--resume` to remember: the moment the bug ticket reaches `status:done`, the next run
(bare, or an explicit ticket number — `docs/pilot-process.md` §4 extends its
explicit-number check to phase 6 too) picks it back up on its own.
