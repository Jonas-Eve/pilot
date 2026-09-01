---
name: pilot-auto
description: "Convenience dispatcher over PILOT's four auto-capable phase sweeps (see docs/pilot-process.md): tries /pilot-review, then /pilot-dev --auto, then /pilot-spec --auto, then /pilot-scope --auto, in that order, stopping at the first one that actually finds and processes at least one candidate. Takes an optional subset (review/dev/spec/scope, any combination, any order) to restrict which phases it tries this run, e.g. 'spec scope' to dispatch only those two — still evaluated finish-before-start, just narrowed to the given ones; omit for all four. Lets a scheduled Routine (or a human) fire one bare command instead of picking which phase needs attention, and lets several Routines split the four phases by cadence without each reimplementing dispatch. Never invokes /pilot-story or /pilot-qa — both are pair-only, no bare/--auto mode exists for either, and neither is ever a valid subset token. Adds no phase, claim, or label mechanic of its own: each invoked skill still resolves and processes its own candidate pool exactly as it would standalone."
argument-hint: "[review] [dev] [spec] [scope] — any subset, any order, space-separated; omit for all four"
disable-model-invocation: true
---

# PILOT — Auto Dispatch

Read `docs/pilot-process.md` first if you haven't — this skill adds nothing to the state
machine, claim protocol, or labels described there. It only sequences four already-existing
bare/`--auto` sweeps (`docs/pilot-process.md` §4 "Scheduled sweeps"), each of which already
knows how to build and process its own candidate pool. Never re-implement that pool-building
logic here — always let the invoked skill do it.

Never runs pair: this command's whole purpose is unattended dispatch, so it always drives
`/pilot-dev`, `/pilot-spec`, and `/pilot-scope` with `--auto`. Someone wanting to pair
through a specific ticket should call that phase's own skill directly instead.

## Determining the subset

No argument → the full set, all four, in the fixed order below (steps 1-4).

One or more of `review`, `dev`, `spec`, `scope` (any order, space-separated) → only that
subset, but still tried in the fixed order below, skipped phases simply never invoked at
all — not even to check their pool. E.g. `/pilot-auto spec scope` tries `/pilot-spec --auto`
first, then `/pilot-scope --auto` if nothing there; `/pilot-auto dev` tries only
`/pilot-dev --auto`, reporting idle immediately if its pool is empty, without ever touching
review/spec/scope.

Any other token (`story`, `qa`, a typo, anything else) → invalid; report which token didn't
match one of the four and stop without invoking anything.

## Why the fixed order

Finish in-flight work before starting new work: `/pilot-review` first (get open PRs to
`status:approved`/`status:changes-requested`/flagged, so they're mergeable or back with a
dev), then `/pilot-dev --auto` (advance `status:dev-ready` work, including reclaiming
`status:changes-requested`/resumable tickets), then `/pilot-spec --auto`, then
`/pilot-scope --auto` last — only pull in genuinely new work once nothing already further
along the pipeline needs attention this run. A restricted subset keeps this same relative
order, just narrowed — it never reorders the four.

## Steps

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

## Report

Relay whichever phase's own report was the stopping point, prefixed with which phase
actually ran (e.g. "Ran `/pilot-dev --auto`: ..."). If every phase in the subset found
nothing, report that the subset is idle this run, naming which phases were actually tried
(all four, or the requested subset) — never imply a phase was checked when the subset
skipped it entirely.
