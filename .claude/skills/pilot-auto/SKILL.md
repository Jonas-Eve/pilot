---
name: pilot-auto
description: "Dispatcher over PILOT's three auto-capable sweeps: tries /pilot-review --auto, then /pilot-dev --auto, then /pilot-spec --auto and stops at the first that processes a candidate. Takes an optional subset (review, dev, spec in any order) to narrow it, or one issue number to try against each phase in turn. Flags: --merge (review only), --multi, --again (keep draining the pools), --next (ride one ticket through the whole chain). Never invokes /pilot-discovery or /pilot-qa, adds no mechanic of its own. Use from a scheduled Routine, or when you do not know which phase a ticket is in."
argument-hint: "[review] [dev] [spec] [--merge] [--with <persona>[,...]] [--multi [N]] [--again|--next] — any subset, any order; --merge forwards to /pilot-review only, --multi forwards to whichever phase claims a ticket, --again sweeps a new candidate each pass until one finds nothing, --next rides whichever candidate the first pass claims through the whole chain instead | <issue number> [--merge] [--multi [N]] [--next|--continue] — tries that ticket against each phase in order, --auto mode; --next keeps re-dispatching it until done, needs-human, orphaned, or closed"
---

# PILOT — Auto Dispatch

Read `.pilot/pilot-process.md` first. This skill adds nothing to its state machine, claim protocol or labels: it only sequences three existing bare/`--auto` sweeps (the last
section), each of which builds and processes its own pool or, given one ticket, resolves it and reports nothing to do when the ticket is not in its own territory
(`.pilot/pilot-process.md` §4 "Claim Protocol"). Never re-implement that resolution here: this command does not read a ticket's `status:`, does not know the label taxonomy and does
not decide which phase a ticket belongs to; it tries each phase in a fixed order and relays whichever one did something.

It never runs pair (unattended dispatch is its whole point), so it always drives `/pilot-review`, `/pilot-dev` and `/pilot-spec` with `--auto`; to pair through a ticket, call that phase's
skill directly. It never passes `--resume` either: recovering an orphaned claim is a human's call (`.pilot/pilot-process.md` §4 "Resuming an orphaned claim"), since nothing on the ticket
tells an orphan from work in progress elsewhere. If a phase decides a ticket looks orphaned it reports that and asks for `--resume`: relay it, never retry with it.

## Determining the mode

- No argument → **sweep mode**, all three phases in the fixed order below, each working its own pool.
- One or more of `review`, `dev`, `spec` (any order) → **sweep mode** restricted to that subset, still in the fixed order; skipped phases are never invoked, not even to check their
  pool (`/pilot-auto dev spec` tries `/pilot-dev --auto`, then `/pilot-spec --auto`).
- A single issue number → **ticket-dispatch mode**: the same fixed order, all three phases, each tried against that one ticket. Never with a subset, never more than one number. The
  ticket may be a `level:epic` or a `status:split` story: each phase's own resolution handles it (`.pilot/pilot-link-epic-descent.md`), never a reason to refuse the number or to resolve it here.
- Anything else (a token that is not a subset name or an issue number, such as `discovery`, `qa` or a typo; more than one number; a number with a subset) → invalid: say which part
  did not match and invoke nothing.

Optional flags: `--merge` combines with any mode and is forwarded to `/pilot-review` only, when review is actually tried. `--with <persona>[,...]` is forwarded verbatim to whichever phase
claims a ticket (`.pilot/pilot-link-roster.md` "Roster"; each phase refuses a name outside its own list). `--multi <N>` combines with every mode and with `--again`/`--next`, forwarded
unconditionally: it only changes how the one claimed ticket is worked (`.pilot/pilot-link-agent-dialogue.md` for Spec and Dev, `.pilot/pilot-link-multi-consensus.md` for Review).
`--again` combines only with sweep mode (invalid with an issue number). `--next` (alias `--continue`) combines with any input: it changes what happens after the first pass. `--again`
and `--next` never combine with each other (a fresh candidate each time vs. the one just claimed).

## Why the fixed order

Finish in-flight work before starting new work: `/pilot-review` first (open PRs reach `status:approved`, `status:changes-requested` or flagged), then `/pilot-dev --auto` (advance
`status:dev-ready`, reclaim `status:changes-requested` and resumable tickets), then `/pilot-spec --auto` last, which pulls in new work only once nothing further along needs attention. A
subset keeps that relative order. For one ticket the order does not change correctness (a ticket carries one `status:` at a time, so at most one phase claims it); it is kept for
consistency, and a phase that is not the ticket's own bails out at its claim check before any subagent work.

## Steps

For each phase in the subset (all three for a ticket number or no argument), in order, stopping at the first that does something:

1. `/pilot-review` (`Skill` tool): `args: "--auto"` (sweep) or `"<issue number> --auto"` (dispatch), with `--merge` and/or `--multi <N>` appended if given. `--auto` is required: the phase
   defaults to pair. Nothing to review (empty pool, or the ticket is not a PR or not phase 4's) → next phase; otherwise stop here, the result being what it reported.
2. `/pilot-dev` the same way (`--multi <N>` appended if given): its pool is fresh `status:dev-ready`, resumable and reclaimable `status:changes-requested`
   (`.pilot/pilot-process.md` §4 "Picking the next ticket..."). Nothing to do → next phase; otherwise stop.
3. `/pilot-spec` the same way. Nothing to do → report that nothing in the requested subset (or: this ticket belongs to none of the three) needed attention this run; otherwise stop.

Never invoke `/pilot-discovery` or `/pilot-qa`, in any mode: both are pair-only (`.pilot/pilot-process.md` §4 "Interaction modes"), so neither is a valid subset token or target. A ticket that is
`status:draft` or a phase-5 candidate simply gets "nothing to do" from all three: report it, do not guess why.

## Repeating a run: `--again` and `--next`

Without either flag one run is one iteration. Both flags repeat the same run, always keeping the original subset, `--merge` and `--multi`, until a stopping condition below; each iteration is
still an isolated `Agent` context with only what is on the ticket (`.pilot/pilot-process.md` §5).

**`--again`** (sweep mode only): after an iteration processes a candidate, run another from step 1 with a fresh pool read, so each iteration handles a *different* ticket; stop when a full
iteration finds nothing across the subset (the pools are empty, not just one candidate).

**`--next`**: after the first iteration, re-dispatch the same one ticket through all three phases, whatever the original command. Given an issue number, every iteration targets it. Given none,
the first iteration is an ordinary sweep (the subset or the full set); the phase that claims a candidate fixes the ticket number for every later iteration, which then tries all three phases
whatever the subset (the subset only shaped the first pick). A first sweep that finds nothing pins no ticket: report idle and stop.

Keep re-dispatching until: an iteration finds nothing to do for the ticket across all three phases (merged, `status:done`/`status:wont-do`, or now a Discovery or phase-5 candidate); the
phase that just ran flagged `needs-human`; a phase reports the ticket looks orphaned and asks for `--resume` (relay it, never retry with it); or the ticket is closed.

## Report

- **Sweep mode:** relay the stopping phase's own report prefixed with which phase ran ("Ran `/pilot-dev --auto`: ..."). If every phase in the subset found nothing, report the subset idle,
  naming the phases actually tried, never implying one was checked when the subset skipped it.
- **Ticket-dispatch mode:** relay the stopping phase's report prefixed with the phase that claimed the ticket ("Ticket #48 → ran `/pilot-dev 48 --auto`: ..."). If all three had nothing to do,
  relay each phase's own reason verbatim, never restated in terms of `status:` labels this command never read.
- **With `--again` or `--next`:** report each iteration in order, then one line: for `--again`, how many candidates were processed across which phases before the subset went idle; for
  `--next` with no issue number, first name the ticket the first iteration pinned; either way, how many phase-advances happened and which stopping condition ended it (nothing left,
  `needs-human`, orphaned, closed).

## Scheduled sweeps

Each phase skill is meant to also run **bare, on a timer**: a Routine whose prompt is the literal command. `/pilot-spec`, `/pilot-dev` and `/pilot-review` default to pair mode
(`.pilot/pilot-process.md` §4 "Interaction modes"), so that command must include `--auto` (still no ticket number computed by the Routine), since pair needs a live human. `/pilot-discovery`
and `/pilot-qa` are pair-only and never driven by a Routine. Beyond that flag nothing is special-cased: "picking the next ticket when none is specified" (`.pilot/pilot-process.md` §4) covers fresh
and resumed work alike. Use three independent Routines, one each for `/pilot-spec --auto`, `/pilot-dev --auto` and `/pilot-review --auto` (add `--merge` if the Routine should also merge once
every reviewer approves, `.pilot/pilot-process.md` §3 "`status:approved`"), each on its own schedule, so a slow or failing phase never delays the others.
