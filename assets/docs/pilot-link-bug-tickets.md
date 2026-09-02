# PILOT link — Prerequisite bug tickets (phase 2, phase 4, phase 6)

Injected by `.claude/skills/pilot-scope/SKILL.md`, `pilot-dev/SKILL.md`, and
`pilot-qa/SKILL.md` into their respective duty's prompt — each passes "Classify and
originate" below (identical for all three, the single canonical version of that mechanic)
plus its own phase section only, never the other two's. Also cited, without restating any
of it, by `docs/pilot-process.md`'s own generic text,
`docs/pilot-task-formalize-bug-report.md`, and
`.github/workflows/pilot-status-on-merge.yml`. Never by `.claude/agents/pilot-*.md`, which
carry only identity now. See `docs/pilot-process.md` §2/§3/§4 for the generic ticket
types, labels, and claim protocol this builds on.

Distinct from a prerequisite *tech* ticket (`docs/pilot-process.md` §2 "Prerequisite tech
tickets" — a new technical need, no defect implied): while scoping (phase 2),
implementing/testing (phase 4), or manually confirming shipped behavior (phase 6), the
architect, dev/`pilot-e2e`, or `pilot-qa` may run into something that looks like a concrete
**defect** in already-shipped code outside the ticket's own scope — not an ambiguity in
what's being built (phase 4's own spec-deviation path, `pilot-dev.md`, still covers that).
Most commonly this happens while writing or running an end-to-end test task, or during a
phase-6 manual test case, but isn't limited to either case.

## Classify and originate

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

## Phase 2 (scoping — not yet claimed by phase 3/4)

A ticket phase 2 is scoping isn't claimed by phase 3/4 yet, so recording "Depends on #N"
above and finishing the scoping pass normally is enough — no unclaiming needed. The gate
(`docs/pilot-process.md` §4 "Blocked-by dependencies") does the rest once phase 3/4 later
try to claim it.

## Phase 4 (implementing — already claimed)

Unlike phase 2, a ticket phase 4 is implementing is already claimed and mid-phase
(`status:in-dev`, assigned) — the gate only ever fires when a phase builds a candidate pool
or claims a ticket, so leaving it claimed would just sit there with nothing ever
rechecking it. So also unclaim the ticket being worked before stopping: first push
whatever's already done to a branch (creating one if none exists yet) and comment on the
ticket naming it, so whichever agent claims it next — the same one or a different one —
resumes from that branch instead of starting over (`pilot-dev.md`/`pilot-e2e.md` cover the
claim-time check for this); never push a broken or partial commit. Then clear the
assignee and move it back to `status:dev-ready`. The ticket is now an ordinary
`status:dev-ready` candidate again, gated only by "Depends on #N" like any other — no flag
to remove, no `--resume` to remember: the moment the bug ticket reaches `status:done`, the
next run picks it back up on its own.

## Phase 6 (confirming — already claimed)

Same reasoning as phase 4 above: a ticket phase 6 is confirming is already claimed and
mid-phase (`status:in-qa`, assigned), so also unclaim it before stopping — comment on the
ticket naming the new bug ticket(s), clear the assignee, and move it back to `status:qa`;
never finish the QA pass as if nothing were wrong in the meantime. No branch/commit
involved here, unlike phase 4 — nothing was pushed. The ticket is now an ordinary
`status:qa` candidate again, gated only by "Depends on #N" like any other — no flag to
remove, no `--resume` to remember: the moment the bug ticket reaches `status:done`, the
next run (bare, or an explicit ticket number — `docs/pilot-process.md` §4 extends its
explicit-number check to phase 6 too) picks it back up on its own.
