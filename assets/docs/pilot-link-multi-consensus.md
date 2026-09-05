# Multi Consensus: `--multi <N>`

Shared by `/pilot-scope` (architect), `/pilot-spec` (tech lead), `/pilot-dev` (dev/e2e),
and `/pilot-review` (each of its already-selected reviewer roles — PM, architect, tech
lead, `pilot-review/SKILL.md` step 3). `/pilot-story` and `/pilot-qa` never support it —
both are pair-only, human-conversation phases this ensemble shape doesn't fit.
`/pilot-auto` forwards it (below) but implements none of this itself.

## What it changes

`--multi <N>` (a positive integer) runs
**N independent instances of the same persona on the same claimed ticket**, instead of
one, to increase the odds a genuinely better proposal surfaces or a real gap gets caught —
not N different tickets, and not N different personas. Omitted entirely is today's
unchanged behavior (a single instance, no ensemble). **`--multi` given with no value
defaults to `N=2`** — the smallest ensemble that still has something to reconcile. A
malformed value instead (not a positive integer — `0`, negative, non-numeric) is invalid:
report exactly that and stop, same posture as any other malformed invocation in this repo
(e.g. `pilot-auto/SKILL.md`'s "Determining the mode"). This is orthogonal to which ticket
gets claimed: the ordinary claim protocol and pool-picking (`.pilot/pilot-process.md` §4)
are completely unaffected — still exactly one ticket claimed per invocation. It's also
orthogonal to pair vs `--auto` (`.pilot/pilot-process.md` §4 "Interaction modes"): the
reconciled result below is what pair's existing checkpoint shows the human, or what
`--auto` applies straight through — exactly as if a single agent had produced it.

**Invalid combined with the literal `--resume` flag** — knowable from the command line
alone, report and stop. That flag recovers one specific paused pair session's exact
in-progress state (`.pilot/pilot-process.md` §4 "Resuming an orphaned claim") — continuing
one interrupted train of thought, not a fresh multi-perspective ask. An implicit resume via
`can-resume` (a previously-blocked ticket, now cleared) is different: the persona is
genuinely reconsidering given new information, which benefits from the same ensemble as a
fresh claim — `--multi` applies there normally, wherever a phase's own steps route it
through the persona's ordinary `Agent` call.

## Mechanics

### One ensemble round

Call the `Agent` tool N times in parallel, `subagent_type` the persona already in use for
this phase (or, in `/pilot-review`, for the specific role being ensembled), identical
prompt and inputs each time, each instance fully isolated from the others — none sees any
other's output, the same independence guarantee `/pilot-review`'s existing multi-persona
parallelism already relies on (`.pilot/pilot-process.md` §4).

### Consensus check

One further `Agent` call, same persona, given all N raw outputs from the round just run
(plus, on a retry round below, the prior round's disagreement summary). Its only job is to
compare, never to invent a new answer no instance actually produced:

- **Every substantive decision point agrees** (allowing for surface differences in
  wording/structure) → name which one instance's output to adopt verbatim. Pick any one of
  the agreeing instances — they're substantively interchangeable at that point.
- **Any substantive point genuinely diverges** → report exactly which point(s) diverge and
  quote each instance's differing position verbatim, without picking a winner itself.

What counts as a "substantive decision point" is specific to each caller:

- **`/pilot-scope` (architect)**: split y/n; the resulting task set and each task's own
  `type:`/priority; security/architecture decisions; recorded dependencies; a wont-do
  verdict; any prerequisite ticket(s) and hard-blocker status; any `needs-human` flag.
- **`/pilot-spec` (tech lead)**: the technical approach/design decisions in the spec; any
  blocking conflict raised against the architect's decisions.
- **`/pilot-dev` (dev/e2e)**: the ensemble runs at the **proposed-approach stage only**
  (`pilot-dev/SKILL.md` step 3) — never on finished code, so there's no branch to push or
  diff to compare: N instances each propose an implementation approach, never touching
  code yet. A substantive decision point here is the approach itself (overall design,
  which files/layers it touches, the tradeoff it makes) — surface differences in how it's
  worded don't count. Once reconciled (or approved by a live human in pair mode, same as
  any single-agent proposal), exactly **one** further `Agent` call implements it
  (`pilot-dev/SKILL.md` step 4) — the ensemble's job ends at the approach, it's never
  re-run on the code. Only a fresh claim — a reclaim (`.pilot/pilot-process.md` §4
  "Reclaiming a `status:changes-requested` ticket") never goes through this
  proposed-approach stage in the first place, pair or `--auto` alike (the phase-5 review
  already specified exactly what to fix, so `pilot-dev/SKILL.md` step 3 implements that fix
  directly in one call) — there's no approach for `--multi` to ensemble on, so it silently
  has no effect there rather than erroring; whether a given ticket, or one a bare pool
  resolves to, turns out to be a reclaim isn't always known upfront.
- **`/pilot-review`, per role** (run once per role actually in this PR's reviewer set,
  `pilot-review/SKILL.md` step 3): a `change`/`decision`-tagged point
  (`.pilot/pilot-link-review-consensus.md`) that only some of the N instances raised is
  **not** disagreement — union it in as extra coverage, deduplicated against equivalent
  points from other instances; that's the whole value of ensembling a reviewer. Genuine
  disagreement is narrower: two instances reaching *opposite* judgments about the
  identical point (one clears it, another blocks on it) — only that triggers a retry,
  scoped to the contested point, never the whole role's review. Still unresolved after
  that retry → fold it into that role's own point-list as one `decision`-tagged point
  quoting every differing position verbatim, rather than escalating separately — step 6's
  existing tag-based aggregation already turns any `decision` point into `needs-human`, so
  this reuses that path instead of adding a second one. The reconciled per-role
  point-list is what step 6's existing cross-role aggregation already consumes, unchanged.

### Retry, then escalate — capped at two rounds

- Round 1 disagrees → run **one** more ensemble round: same N, same original inputs, plus
  the consensus check's disagreement summary appended so the fresh instances can reconsider
  it — then run the consensus check again.
- That second round still disagrees → stop ensembling on that point. For `/pilot-scope`,
  `/pilot-spec`, and `/pilot-dev` (still at the proposed-approach stage, above — nothing
  implemented yet, so nothing to push or clean up), add `needs-human`
  (`.pilot/pilot-process.md` §3) with a comment quoting every divergent point and each
  round's differing positions verbatim, never summarized away — a human decides directly,
  the same as any other blocking judgment call. For `/pilot-review`, don't add
  `needs-human` directly — fold the divergence into
  one `decision`-tagged point in that role's list instead (above), scoped to the specific
  contested point only; the rest of that role's reconciled points, and the other roles'
  own ensembles, proceed normally, and step 6's aggregation adds `needs-human` the
  ordinary way once it sees that point.
- Consensus reached at round 1 or round 2 → proceed with that round's adopted output
  through the phase's normal remaining steps, exactly as if only one agent had run. Never a
  third round.

## `/pilot-auto` forwarding

An optional `--multi <N>` on `/pilot-auto` forwards verbatim to whichever phase actually
runs, in both sweep mode and ticket-dispatch mode alike (unlike `--merge`'s review-only
scope) — it changes nothing about which ticket gets claimed, only how the claiming phase
works the one ticket it claims. Invalid combined with `--resume`, same as above (`/pilot-
auto` never passes `--resume` itself, `pilot-auto/SKILL.md`, so this never actually arises
in practice).
