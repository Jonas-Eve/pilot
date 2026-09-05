# PILOT link — Multi-instance consensus (`--multi <N>`)

Injected whole by `pilot-scope`/`pilot-spec`/`pilot-dev`/`pilot-review`'s own `SKILL.md`
into the consensus-check `Agent` call only, alongside that same call's own duty task doc
(below) — never by `.claude/agents/pilot-*.md`, which carry only identity now, and never
into the N ensemble instances themselves (they run the ordinary, unmodified duty). See
`.pilot/pilot-process.md` §4 for the generic claim protocol and interaction modes this
builds on.

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
fresh claim — every one of `pilot-scope`/`pilot-spec`/`pilot-dev`/`pilot-review`'s own
`SKILL.md` routes both the explicit-`--resume` and the implicit-`can-resume` case back
through that skill's own ordinary `Agent`-calling step, so `--multi` (and the "invalid with
`--resume`" check above) apply there exactly the same way they do to a fresh claim.

For `/pilot-dev` only, no effect on reclaiming a `status:changes-requested` ticket (its own
task doc's "Reconciling an ensemble" section below covers why): the phase-5 review already
specified exactly what to fix, so that path never proposes an approach to ensemble on in
the first place, pair or `--auto` alike — whether a given ticket, or one a bare pool
resolves to, turns out to be a reclaim isn't always known upfront, so `--multi` silently
proceeds as a single instance there instead of erroring.

## Mechanics

### One ensemble round

Call the `Agent` tool N times in parallel, `subagent_type` the persona already in use for
this phase (or, in `/pilot-review`, for the specific role being ensembled), identical
prompt and inputs each time — the ordinary duty, unmodified, its own task doc included —
each instance fully isolated from the others — none sees any other's output, the same
independence guarantee `/pilot-review`'s existing multi-persona parallelism already relies
on (`.pilot/pilot-process.md` §4).

### Consensus check

One further `Agent` call, same persona, `subagent_type` unchanged. Pass it: that same
duty's own task doc (the one already used for the N-instance round — its own "Reconciling
an ensemble" section, below, is what tells the persona this invocation is a comparison, not
a fresh proposal), all N raw outputs from the round just run, and, on a retry round below,
the prior round's disagreement summary too. Its only job, per that section, is to compare,
never to invent a new answer no instance actually produced:

- **Every substantive decision point agrees** (allowing for surface differences in
  wording/structure) → name which one instance's output to adopt verbatim. Pick any one of
  the agreeing instances — they're substantively interchangeable at that point.
- **Any substantive point genuinely diverges** → report exactly which point(s) diverge and
  quote each instance's differing position verbatim, without picking a winner itself.

What counts as a "substantive decision point" is that duty's own call, not this doc's —
each caller's own task doc states it, right where that duty's real substance is already
defined, rather than restated here where a future edit to one could quietly drift from the
other: `.pilot/pilot-task-scope-story.md` (`/pilot-scope`), `.pilot/pilot-task-write-spec.md`
(`/pilot-spec`), `.pilot/pilot-task-implement.md` (`/pilot-dev`, `pilot-e2e` inherits it
unchanged), and, for `/pilot-review`, whichever of `.pilot/pilot-task-review-product-fit.md`,
`.pilot/pilot-task-review-architecture.md`, `.pilot/pilot-task-review-spec-conformance.md`
matches the role being ensembled.

### Retry, then escalate — capped at two rounds

- Round 1 disagrees → run **one** more ensemble round: same N, same original inputs, plus
  the consensus check's disagreement summary appended so the fresh instances can reconsider
  it — then run the consensus check again.
- That second round still disagrees → stop ensembling on that point. For `/pilot-scope`,
  `/pilot-spec`, and `/pilot-dev` (still at the proposed-approach stage — nothing
  implemented yet, so nothing to push or clean up), add `needs-human`
  (`.pilot/pilot-process.md` §3) with a comment quoting every divergent point and each
  round's differing positions verbatim, never summarized away — a human decides directly,
  the same as any other blocking judgment call. For `/pilot-review`, don't add
  `needs-human` directly — fold the divergence into
  one `decision`-tagged point in that role's list instead (its own task doc's "Reconciling
  an ensemble" section), scoped to the specific contested point only; the rest of that
  role's reconciled points, and the other roles' own ensembles, proceed normally, and step
  6's aggregation adds `needs-human` the ordinary way once it sees that point.
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
