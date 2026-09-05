---
name: pilot-auto
description: "Convenience dispatcher over PILOT's four auto-capable phase sweeps (see .pilot/pilot-process.md): tries /pilot-review --auto, then /pilot-dev --auto, then /pilot-spec --auto, then /pilot-scope --auto, in that order, stopping at the first one that actually finds and processes at least one candidate. Takes an optional subset (review/dev/spec/scope, any combination, any order) to restrict which phases it tries this run, e.g. 'spec scope' to dispatch only those two — still evaluated finish-before-start, just narrowed to the given ones; omit for all four. An optional --merge, combined with review being in scope, is forwarded only to /pilot-review (the other three have no such flag), merging an approved PR itself instead of leaving it for a human. An optional --again, sweep mode only (full set or a subset), keeps re-running the same dispatch after each candidate instead of stopping at the first, draining every phase's pool in this one invocation until a full pass finds nothing. Given a single issue number instead, tries that same fixed order against that one ticket instead of a pool — each phase's own claim protocol reports nothing to do when the ticket isn't currently in that phase's pre-claim status, so this command never inspects the ticket's status: itself, it just tries each phase in turn and stops at the first that claims it. An optional --next (alias --continue), ticket-dispatch mode only, keeps re-dispatching that same ticket after each phase advance instead of stopping there, until a pass finds nothing left to do for it, a phase flags needs-human, or it closes — internalizing the documented `/loop /pilot-auto <ticket>` pattern into one command. Lets a scheduled Routine (or a human) fire one bare command instead of picking which phase needs attention, or hand it one ticket without knowing which phase it's currently in. Never invokes /pilot-story or /pilot-qa — both are pair-only, no bare/--auto mode exists for either, and neither is ever a valid subset token or dispatch target. Adds no phase, claim, or label mechanic of its own: each invoked skill still resolves and processes its own candidate (pool or given ticket) exactly as it would standalone."
argument-hint: "[review] [dev] [spec] [scope] [--merge] [--again] — any subset, any order, space-separated; omit subset for all four, --merge forwards to /pilot-review only, --again sweeps repeatedly until a full pass finds nothing | <issue number> [--merge] [--next|--continue] — try that one ticket against each phase in the same order, in --auto mode; --next keeps re-dispatching it until nothing's left, needs-human, or it closes"
---

# PILOT — Auto Dispatch

Read `.pilot/pilot-process.md` first if you haven't — this skill adds nothing to the state
machine, claim protocol, or labels described there. It only sequences four already-existing
bare/`--auto` sweeps (`.pilot/pilot-process.md` §4 "Scheduled sweeps"), each of which already
knows how to build and process its own candidate pool — or, given a single ticket instead of
a pool, already knows how to resolve that one explicit ticket, including cleanly reporting
nothing to do when it isn't currently in that phase's own territory (§4 "Claim Protocol",
step 2: "stop... or report nothing to do, if a specific ticket number was requested
explicitly"). Never re-implement any of that resolution logic here — this command doesn't
read a ticket's `status:` label, doesn't know the label taxonomy, and doesn't decide which
phase a ticket belongs to; it only tries each phase in a fixed order and relays whichever one
says it actually did something. Always let the invoked skill do that deciding.

Never runs pair: this command's whole purpose is unattended dispatch, so it always drives
`/pilot-review`, `/pilot-dev`, `/pilot-spec`, and `/pilot-scope` with `--auto`. Someone
wanting to pair through a specific ticket should call that phase's own skill directly
instead. This also
means it never passes `--resume`: that flag recovers a claim orphaned by an abandoned pair
session or a crashed `--auto`/phase-5 run (`.pilot/pilot-process.md` §4 "Resuming an orphaned
claim") — a deliberate human call this command never makes on its own, since nothing on the
ticket distinguishes an orphan from one genuinely still in progress elsewhere. If a target
skill's own resolution decides a given ticket looks orphaned, it reports that and stops,
asking for `--resume` — relay that exactly as any other outcome, don't retry with it.

## Determining the mode

No argument → **sweep mode**, the full set, all four, in the fixed order below (steps 1-4),
each working its own pool.

One or more of `review`, `dev`, `spec`, `scope` (any order, space-separated) → **sweep
mode**, restricted to that subset, but still tried in the fixed order below, skipped phases
simply never invoked at all — not even to check their pool. E.g. `/pilot-auto spec scope`
tries `/pilot-spec --auto` first, then `/pilot-scope --auto` if nothing there; `/pilot-auto
dev` tries only `/pilot-dev --auto`, reporting idle immediately if its pool is empty, without
ever touching review/spec/scope.

A single issue number (e.g. `/pilot-auto 48`) → **ticket-dispatch mode**: the same fixed
order below, all four phases, each tried against that one ticket instead of its pool. Never
combined with a subset — a subset narrows *which pool-driven phases* run, which has no
meaning once there's a specific ticket to try against all of them; never more than one issue
number either. Either combination is invalid (below).

Any other input — a token that isn't one of the four subset names and isn't a bare issue
number (`story`, `qa`, a typo), more than one issue number, or an issue number mixed with a
subset token — → invalid; report which part didn't match a valid mode and stop without
invoking anything.

An optional trailing `--merge` combines with either mode above (sweep, restricted sweep, or
ticket-dispatch) — it never changes which mode applies on its own, it only adds to step 1
below, and only takes effect when `review` is actually tried (in scope for a restricted
subset, or reached before something else claims the ticket in dispatch mode).

`--again` only combines with sweep mode (full set or a restricted subset) — invalid
alongside an issue number, same as any other mode mismatch above. `--next` (alias
`--continue`) only combines with ticket-dispatch mode — invalid with no argument or a
subset, since there's no single ticket to keep advancing. Neither ever combines with the
other, since sweep mode and ticket-dispatch mode already can't. See "Repeating a run"
below for what each one actually does.

## Why the fixed order

Finish in-flight work before starting new work: `/pilot-review` first (get open PRs to
`status:approved`/`status:changes-requested`/flagged, so they're mergeable or back with a
dev), then `/pilot-dev --auto` (advance `status:dev-ready` work, including reclaiming
`status:changes-requested`/resumable tickets), then `/pilot-spec --auto`, then
`/pilot-scope --auto` last — only pull in genuinely new work once nothing already further
along the pipeline needs attention this run. A restricted subset keeps this same relative
order, just narrowed — it never reorders the four.

For a single ticket in dispatch mode, this ordering doesn't change correctness — a ticket
carries exactly one `status:` label at a time (`.pilot/pilot-process.md` §3), so at most one of
the four phases will ever actually claim it, whichever order they're tried in. The fixed
order is kept anyway, purely for consistency with sweep mode and because it costs nothing:
each phase that isn't the ticket's own bails out at its own claim check, before spinning up
any subagent work.

## Steps

For each of the four below that's in the subset (all four, if a ticket number or no argument
was given — never combined with a subset, above), in this order, stopping at the first one
that actually does something:

1. `/pilot-review` (`Skill` tool). Sweep mode: `args: "--auto"` (append `--merge` if given,
   above), resolving its own pool. Ticket-dispatch mode: `args: "<issue number> --auto"`
   (`--merge` appended the same way). `--auto` is required here now that this phase
   defaults to pair (`.pilot/pilot-process.md` §4 "Interaction modes") — unattended dispatch
   is this command's whole point. Either way, let it resolve and process exactly as it
   would standalone (`.pilot/pilot-process.md` §4 "Picking the next ticket...").
   - Nothing to review (empty pool, or — given a ticket — it isn't a PR/doesn't currently
     belong to phase 5) → continue to the next phase.
   - Otherwise (it reviewed the PR/pool, whatever the verdict) → stop here; this run's result
     is exactly what it reported. Don't run anything after it.
2. `/pilot-dev` (`Skill` tool). Sweep mode: `args: "--auto"`, resolving its own pool — fresh
   `status:dev-ready`, resumable, or reclaimable `status:changes-requested`
   (`.pilot/pilot-process.md` §4 "Picking the next ticket..."). Ticket-dispatch mode: `args:
   "<issue number> --auto"`.
   - Nothing to do (empty pool, or the given ticket isn't currently phase 4's) → continue to
     the next phase.
   - Otherwise → stop here; this run's result is exactly what it reported.
3. `/pilot-spec` the same way (`args: "--auto"` or `args: "<issue number> --auto"`).
   - Nothing to do → continue to the next phase.
   - Otherwise → stop here; this run's result is exactly what it reported.
4. `/pilot-scope` the same way (`args: "--auto"` or `args: "<issue number> --auto"`).
   - Nothing to do → nothing in the requested subset (or: this ticket doesn't currently
     belong to any of the four) needed attention this run; report that and stop.
   - Otherwise → stop here; this run's result is exactly what it reported.

Never invoke `/pilot-story` or `/pilot-qa` at any point, regardless of mode — both are
pair-only, with no `--auto` or bare/explicit-ticket candidate resolution
(`.pilot/pilot-process.md` §4 "Interaction modes"), so neither can ever be a valid subset token
or dispatch target. A ticket that's actually `status:draft` (phase 1) or a phase-6 candidate
(`status:qa`/`status:in-qa` picked up by `/pilot-qa` rather than the phase-2 re-scope path)
simply gets "nothing to do" from all four tried phases — report that, don't guess why.

## Repeating a run: `--again` and `--next`

Without either flag, one run above is exactly one iteration: stop at the first phase that
does something, or report nothing to do. Both flags instead repeat that same run —
iteration after iteration, each one the steps above in full — until a stopping condition
below is met. Never combine the two: each is valid only in the one mode described here,
already stated above.

**`--again`** (sweep mode, full set or a restricted subset): after one iteration claims
and processes a candidate, immediately run another iteration of the same subset from step
1 — a fresh pool read each time, since the candidate just processed no longer belongs to
that phase's pool. Keep going until one full iteration finds nothing across every phase in
the subset — the pool(s) are empty, not just this one candidate. This drains the subset's
pool(s) in a single invocation instead of processing one candidate and stopping.

**`--next`** (alias `--continue`, ticket-dispatch mode only): after one iteration's phase
advances the given ticket, immediately run another iteration of all four phases against
that same ticket number. Keep going until any of:
- an iteration finds nothing to do for it across all four phases (it's left their
  territory entirely — merged, `status:done`/`status:wont-do`, or now a phase-1/phase-6
  candidate instead, `.pilot/pilot-process.md` §4);
- the phase that just ran flagged `needs-human` on it — stop the same way a live pair
  session would, nothing to gain from immediately retrying a ticket now waiting on a
  human;
- the ticket is now closed.

This internalizes the `/loop /pilot-auto <ticket> [--merge]` pattern
(`.pilot/pilot-process-companion.md`) into one command — each iteration is still its own
isolated `Agent` call with no memory of the previous one beyond what's now on the ticket
itself (`.pilot/pilot-process.md` §5), exactly as if a human had re-run the command by
hand each time.

## Report

**Sweep mode**: relay whichever phase's own report was the stopping point, prefixed with
which phase actually ran (e.g. "Ran `/pilot-dev --auto`: ..."). If every phase in the subset
found nothing, report that the subset is idle this run, naming which phases were actually
tried (all four, or the requested subset) — never imply a phase was checked when the subset
skipped it entirely.

**Ticket-dispatch mode**: relay whichever phase's own report was the stopping point, prefixed
with which phase actually claimed the ticket (e.g. "Ticket #48 → ran `/pilot-dev 48 --auto`:
..."). If all four reported nothing to do with it, relay that verbatim (each phase's own
"nothing to do" reason, if it gave one) rather than inferring or restating why in terms of
`status:` labels this command never read.

**With `--again` or `--next`**: report each iteration in the same style as above, in order,
not just the last one, then a one-line summary — for `--again`, how many candidates were
processed and across which phases before the subset went idle; for `--next`, how many
phase-advances the ticket went through and which of the three stopping conditions ended it
(nothing left to do, `needs-human` flagged, or closed).
