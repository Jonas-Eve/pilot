# PILOT link — Prerequisite bug tickets (phase 2, phase 4, phase 6)

Injected whole by `.claude/skills/pilot-scope/SKILL.md`, `pilot-dev/SKILL.md`, and
`pilot-qa/SKILL.md` — the phase-specific delta (whether the discovering ticket needs
unclaiming, and how) lives in each duty's own task doc instead, never here. See
`docs/pilot-process.md` §2/§3/§4 for the generic ticket types, labels, and claim protocol
this builds on.

Distinct from a prerequisite *tech* ticket (`docs/pilot-process.md` §2 "Prerequisite tech
tickets" — a new technical need, no defect implied): a concrete **defect** in
already-shipped code outside your ticket's own scope, most often surfacing while
writing/running an e2e test or a phase-6 manual case, but not limited to those.

**Classify it before creating anything** (`docs/pilot-process.md` §2 intro): genuinely a
code defect against something already agreed on, or actually a new/different need in
disguise. If it's not a bug, don't create a `type:bug` ticket: treat it as a prerequisite
*tech* ticket if it's a new technical need, or leave it for a human via phase 1 if it needs
an actual product/judgment decision.

If it genuinely is a bug, originate a new ticket for it — same linking mechanics as a
prerequisite tech ticket (`docs/pilot-process.md` §2 "Prerequisite tech tickets") but
`type:bug` not `type:tech` — with one difference: create it directly as `type:bug`,
`level:task`, `status:spec-ready`, never `level:story`/`status:backlog`
(`docs/pilot-process.md` §2 "Three levels" — a bug never goes through phase 2's own
scoping pass). Write it directly (what's broken, how observed, root cause/fix if known),
unassigned, standalone — never as a sub-issue of the ticket being worked. Link the two:
"Blocks #M" on the new ticket, "Depends on #N" in the discovering ticket's own body —
always a hard blocker, since the discovering ticket cannot be finished until the bug is
fixed.
