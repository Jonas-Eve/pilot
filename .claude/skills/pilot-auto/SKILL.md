---
name: pilot-auto
description: "Convenience dispatcher over PILOT's four auto-capable phase sweeps (see docs/pilot-process.md): tries /pilot-review, then /pilot-dev --auto, then /pilot-spec --auto, then /pilot-scope --auto, in that order, stopping at the first one that actually finds and processes at least one candidate. Takes an optional subset (review/dev/spec/scope, any combination, any order) to restrict which phases it tries this run, e.g. 'spec scope' to dispatch only those two — still evaluated finish-before-start, just narrowed to the given ones; omit for all four. Given a single issue number instead, skips sweep mode entirely and dispatches that one ticket straight to whichever phase currently owns its status: label, in --auto mode — e.g. status:dev-ready goes to /pilot-dev --auto, status:in-review goes to /pilot-review — reporting a status with no auto-capable phase (status:draft, status:approved, status:split, a closed or level:epic ticket) instead of guessing. Lets a scheduled Routine (or a human) fire one bare command instead of picking which phase needs attention, or hand it one ticket without knowing which phase it's currently in. Never invokes /pilot-story or /pilot-qa — both are pair-only, no bare/--auto mode exists for either, and neither is ever a valid subset token or dispatch target. Adds no phase, claim, or label mechanic of its own: each invoked skill still resolves and processes its own candidate (pool or explicit ticket) exactly as it would standalone."
argument-hint: "[review] [dev] [spec] [scope] — any subset, any order, space-separated; omit for all four | <issue number> — dispatch that one ticket to whichever phase its status: belongs to, in --auto mode"
disable-model-invocation: true
---

# PILOT — Auto Dispatch

Read `docs/pilot-process.md` first if you haven't — this skill adds nothing to the state
machine, claim protocol, or labels described there. It only sequences four already-existing
bare/`--auto` sweeps (`docs/pilot-process.md` §4 "Scheduled sweeps"), each of which already
knows how to build and process its own candidate pool, or — in ticket-dispatch mode — reads
one ticket's current `status:` label and hands it to the one phase skill that owns that
status, which then resolves and claims it exactly as if invoked directly. Never
re-implement either skill's own pool-building or ticket-resolution logic here — always let
the invoked skill do it.

Never runs pair: this command's whole purpose is unattended dispatch, so it always drives
`/pilot-dev`, `/pilot-spec`, and `/pilot-scope` with `--auto`. Someone wanting to pair
through a specific ticket should call that phase's own skill directly instead. This also
means ticket-dispatch mode never passes `--resume`: that flag continues a **pair** session a
live human was driving, which this command never runs. If the target skill's own resolution
decides the ticket looks like an abandoned mid-pair session, it reports that and stops
asking for `--resume` — relay that exactly as any other outcome, don't retry with it.

## Determining the mode

No argument → **sweep mode**, the full set, all four, in the fixed order below (steps 1-4).

One or more of `review`, `dev`, `spec`, `scope` (any order, space-separated) → **sweep
mode**, restricted to that subset, but still tried in the fixed order below, skipped phases
simply never invoked at all — not even to check their pool. E.g. `/pilot-auto spec scope`
tries `/pilot-spec --auto` first, then `/pilot-scope --auto` if nothing there; `/pilot-auto
dev` tries only `/pilot-dev --auto`, reporting idle immediately if its pool is empty, without
ever touching review/spec/scope.

A single issue number (e.g. `/pilot-auto 48`) → **ticket-dispatch mode** ("Ticket-dispatch
mode" below) — routes that one ticket to whichever phase its current `status:` belongs to.
Mutually exclusive with sweep mode: never combine an issue number with a subset token, and
never give more than one issue number — either is invalid (below).

Any other input — a token that isn't one of the four subset names and isn't a bare issue
number (`story`, `qa`, a typo), more than one issue number, or an issue number mixed with a
subset token — → invalid; report which part didn't match a valid mode and stop without
invoking anything.

## Sweep mode

### Why the fixed order

Finish in-flight work before starting new work: `/pilot-review` first (get open PRs to
`status:approved`/`status:changes-requested`/flagged, so they're mergeable or back with a
dev), then `/pilot-dev --auto` (advance `status:dev-ready` work, including reclaiming
`status:changes-requested`/resumable tickets), then `/pilot-spec --auto`, then
`/pilot-scope --auto` last — only pull in genuinely new work once nothing already further
along the pipeline needs attention this run. A restricted subset keeps this same relative
order, just narrowed — it never reorders the four. This ordering logic is specific to sweep
mode's own multi-phase-per-run search; ticket-dispatch mode below invokes exactly one phase,
chosen directly by the ticket's status, never "tried" in any order.

### Steps

For each of the four below that's in the subset (all of them, if none was given), in this
order, stopping at the first one that finds something:

1. `/pilot-review` (`Skill` tool, no argument — already auto-only, `docs/pilot-process.md`
   §4 "Interaction modes"). Let it resolve and process its own pool exactly as it would
   running standalone (`docs/pilot-process.md` §6 step 0).
   - It reports no `status:in-review` PR was ready to (re-)review (empty pool) → continue
     to the next phase in the subset.
   - Otherwise (it reviewed one or more PRs, whatever the verdicts) → stop here; this run's
     result is exactly what it reported. Don't run anything after it.
2. `/pilot-dev` with `--auto` (`Skill` tool, `args: "--auto"`). Let it resolve its own
   pool — fresh `status:dev-ready`, resumable, or reclaimable `status:changes-requested`
   (`docs/pilot-process.md` §4 "Picking the next ticket...").
   - Nothing to do (empty pool) → continue to the next phase in the subset.
   - Otherwise → stop here; this run's result is exactly what it reported.
3. `/pilot-spec` with `--auto` the same way.
   - Nothing to do → continue to the next phase in the subset.
   - Otherwise → stop here; this run's result is exactly what it reported.
4. `/pilot-scope` with `--auto` the same way.
   - Nothing to do → nothing in the requested subset needed attention this run; report
     that and stop.
   - Otherwise → stop here; this run's result is exactly what it reported.

Never invoke `/pilot-story` or `/pilot-qa` at any point, regardless of the subset — both are
pair-only, with no `--auto` or bare candidate pool (`docs/pilot-process.md` §4 "Interaction
modes"), so neither can ever be a valid subset token or something this command finds work
in.

## Ticket-dispatch mode

Given a single issue number, read it (`mcp__github__issue_read`) and route it to whichever
phase currently owns its `status:` label, invoked exactly as a human or Routine would invoke
that phase directly on that same ticket — `--auto` added for the three phases that default to
pair, nothing added for `/pilot-review` (already auto-only, no `--auto` flag exists for it).
This is a status→phase lookup only: the target skill still runs its own full resolution
(needs-human/on-hold checks, "Depends on #N" gating, the claim protocol, mid-pair-session
detection) on the ticket exactly as it would for any explicitly-given issue number
(`docs/pilot-process.md` §4) — never pre-filter or second-guess any of that here.

Always read the **issue** number, never a PR number: `docs/pilot-process.md` sets every
`status:` label on the ticket (the issue) itself, never on its PR (`/pilot-dev` "set
`status:in-review` on the ticket" — `.claude/skills/pilot-dev/SKILL.md`). This is true even
for phase 5: `/pilot-review` accepts either a PR or an issue number itself
(`docs/pilot-process.md` §6 step 0), so passing the same issue number straight through to it
resolves correctly without pilot-auto needing to know the PR number at all.

1. Read the issue's `status:` label (and `level:`, and open/closed state).
2. Look it up in the table below and invoke the matching skill (`Skill` tool) with
   `args: "<issue number> --auto"` (`/pilot-review`: `args: "<issue number>"`, no `--auto`).
   Do this for exactly one phase — never fall back to a different one if the invoked skill
   reports it couldn't proceed (e.g. still blocked by `needs-human`); relay that outcome
   instead (see "Report" below).

   | `status:` | Phase invoked |
   |---|---|
   | `status:backlog`, `status:scoping` | `/pilot-scope --auto` |
   | `status:qa`, `status:in-qa` | `/pilot-scope --auto` — the re-scope entry point (`docs/pilot-process.md` §2 "Re-scoping a `type:feature` story after its split is done"), a valid explicit-ticket target for phase 2 even though it's never part of phase 2's own bare pool |
   | `status:spec-ready`, `status:in-spec` | `/pilot-spec --auto` |
   | `status:dev-ready`, `status:in-dev` | `/pilot-dev --auto` |
   | `status:changes-requested` | `/pilot-dev --auto` — reclaimed exactly as `docs/pilot-process.md` §4 "Reclaiming a `status:changes-requested` ticket" describes |
   | `status:in-review` | `/pilot-review` (no `--auto` — already auto-only) |

3. No phase in the table applies — report which of these it is and stop, without invoking
   anything:
   - `status:draft` — phase 1 (`/pilot-story`) is pair-only, no `--auto` exists for it
     (`docs/pilot-process.md` §4 "Interaction modes"); a human has to pair it through, or
     resume it explicitly with `/pilot-story --resume <issue>` if it was left mid-pair.
   - `status:approved` — every phase-5 reviewer already approved; nothing left for any
     PILOT phase to do, it's waiting on a human to merge the PR.
   - `status:split` — a tracker for its own sub-issue tasks, never itself spec'd or built
     (`docs/pilot-process.md` §3); point at its tasks instead — each carries its own
     `status:` and is a valid dispatch target on its own.
   - `status:wont-do`, `status:done`, or the issue is simply closed — terminal
     (`docs/pilot-process.md` §3); nothing further runs on a closed ticket.
   - `level:epic` with no `status:` label at all — an Epic is never itself scoped, spec'd,
     or built (`docs/pilot-process.md` §2 "Three levels"); point at its stories instead.
   - No `status:` and no `level:epic` either — this isn't a ticket PILOT's state machine
     recognizes; report that and ask the human to check the issue number.

## Report

**Sweep mode**: relay whichever phase's own report was the stopping point, prefixed with
which phase actually ran (e.g. "Ran `/pilot-dev --auto`: ..."). If every phase in the subset
found nothing, report that the subset is idle this run, naming which phases were actually
tried (all four, or the requested subset) — never imply a phase was checked when the subset
skipped it entirely.

**Ticket-dispatch mode**: relay the invoked phase's own report, prefixed with which phase the
ticket's `status:` routed it to (e.g. "Ticket #48 was `status:dev-ready` → ran `/pilot-dev
48 --auto`: ..."). If the status had no auto-capable phase, report exactly which case from
step 3 applied and why nothing was invoked.
