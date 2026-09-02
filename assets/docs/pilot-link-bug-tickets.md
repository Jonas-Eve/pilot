# PILOT link — Prerequisite bug tickets (phase 2, phase 4, phase 6)

Injected whole by `.claude/skills/pilot-scope/SKILL.md`, `pilot-dev/SKILL.md`, and
`pilot-qa/SKILL.md` — the phase-specific delta (whether the discovering ticket needs
unclaiming, and how) lives in each duty's own task doc instead, never here. See
`docs/pilot-process.md` §2/§3/§4 for the generic ticket types, labels, and claim protocol
this builds on.

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
