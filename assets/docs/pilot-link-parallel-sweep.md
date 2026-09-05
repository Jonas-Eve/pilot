# Parallel Sweep: `--parallel <N>`

Shared by `/pilot-scope`, `/pilot-spec`, `/pilot-dev`, `/pilot-review` — the four phases
that both have a bare/pool-driven sweep and support `--auto`
(`.pilot/pilot-process.md` §4 "Picking the next ticket...", "Interaction modes").
`/pilot-story` and `/pilot-qa` are pair-only with no `--auto`, so `--parallel` never
applies to either. `/pilot-auto` forwards it (below) but implements none of this itself.

## What it changes

Without `--parallel`, a bare/`--auto` invocation claims and processes exactly one ticket
per run, per `.pilot/pilot-process.md` §4. `--parallel <N>` (a positive integer) claims
and processes **up to N** tickets in that one run instead of one — never more than what
the pool actually has.

## Requirements and invalid combinations

- **Requires `--auto`.** Pair mode is one live human walking one ticket at a time through
  its checkpoints — there's no meaning to pairing N tickets at once. `--parallel` given
  without `--auto` is invalid: report that and stop, same as any other mode mismatch.
- **Never combined with an explicit issue number or `--resume`.** Both already name
  exactly one ticket — "how many to claim" has nothing to act on. Invalid; report and
  stop rather than silently ignoring the flag.
- Omitted, or `--parallel 1`: today's behavior, unchanged.

## Mechanics

1. Build the merged candidate pool exactly as already documented for that phase
   (`.pilot/pilot-process.md` §4 "Picking the next ticket..." — fresh, resumable, and, for
   `/pilot-dev`, reclaimable candidates), in the same order: highest `priority:` first,
   then a ticket referenced by another open ticket's "Blocks #M" before one that isn't,
   then oldest first.
2. Walk down that order, running the ordinary claim protocol
   (`.pilot/pilot-process.md` §4 "Claim Protocol") on each candidate in turn, until either
   N tickets are successfully claimed or the pool is exhausted. A claim lost to a race
   (another concurrent run) is simply skipped — move to the next candidate, never retry
   the lost one and never abort the rest of the walk. Claiming fewer than N (a short pool,
   or every remaining candidate lost its race) is not an error; claiming zero is the
   ordinary "nothing to do."
3. Run the phase's own per-ticket work (its `SKILL.md`'s own steps from the `Agent` call
   onward) for every claimed ticket **in parallel** — one `Agent` call per ticket. For
   `/pilot-review` specifically, this composes with, rather than replaces, its existing
   per-PR reviewer parallelism (`pilot-review/SKILL.md` step 5): each of the N claimed PRs
   still gets its own full reviewer set running in parallel, so a run claiming N PRs makes
   N × (2 or 3) simultaneous `Agent` calls, not N.
4. Apply each ticket's own result and write its own labels/comments/PR the moment its own
   subagent work finishes — one ticket's blocking conflict, bug discovery, or reclaim
   never holds up or changes another's outcome.
5. Report once per ticket (whatever order they finish in), then a one-line summary: how
   many candidates were claimed out of N requested, and how many of those landed in each
   outcome (advanced, blocked/`needs-human`, reclaimed, etc., in that phase's own terms).

## `/pilot-auto` forwarding

An optional `--parallel <N>` on `/pilot-auto` forwards verbatim to whichever of the four
phases actually runs, in sweep mode only (full set or a restricted subset) — the same
posture as `--merge`, except it applies to all four rather than review alone, since all
four already run with `--auto` under `/pilot-auto`. Invalid combined with a single issue
number (ticket-dispatch mode targets exactly one ticket, same as above) or with `--next`
(which pins to one ticket after the first pass — no pool left to claim N from). Combines
with `--again`: each iteration then claims up to N fresh candidates instead of one before
checking whether the subset's pool(s) are actually empty.
