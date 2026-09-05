# Multi Consensus: `--multi <N>`

Shared by `/pilot-scope` (architect), `/pilot-spec` (tech lead), `/pilot-dev` (dev/e2e),
and `/pilot-review` (each of its already-selected reviewer roles — PM, architect, tech
lead, `pilot-review/SKILL.md` step 3). `/pilot-story` and `/pilot-qa` never support it —
both are pair-only, human-conversation phases this ensemble shape doesn't fit.
`/pilot-auto` forwards it (below) but implements none of this itself.

## What it changes

`--multi <N>` (a positive integer; omitted or `1` is today's unchanged behavior) runs
**N independent instances of the same persona on the same claimed ticket**, instead of
one, to increase the odds a genuinely better proposal surfaces or a real gap gets caught —
not N different tickets, and not N different personas. This is orthogonal to which ticket
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

For `/pilot-dev` only, also no effect on reclaiming a `status:changes-requested` ticket
(below) — pushing more commits to one already-open PR's own branch doesn't compose with N
independent branches. Whether a given ticket, or one a bare pool resolves to, turns out to
be a reclaim isn't always known upfront, so `--multi` silently proceeds as a single
instance there instead of erroring.

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
- **`/pilot-dev` (dev/e2e)**: substantive equivalence of implementation approach and
  outcome — same overall approach, passing the same validation/tests, no materially
  different tradeoff — never byte-for-byte code identity. Each of the N instances works
  its own branch (never share one); the adopted instance's branch is what gets opened as
  the PR. Only a fresh claim — reclaiming a `status:changes-requested` ticket
  (`.pilot/pilot-process.md` §4 "Reclaiming a `status:changes-requested` ticket") is
  continuing one specific existing line of work (more commits on one already-open PR's own
  branch), not a fresh candidate to ensemble, so `--multi` silently has no effect there
  (proceeds as a single dev) rather than erroring — whether a given ticket, or one a bare
  pool resolves to, turns out to be a reclaim isn't always known upfront.
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
- That second round still disagrees → stop ensembling on that point. For `/pilot-scope`
  and `/pilot-spec`, add `needs-human` (`.pilot/pilot-process.md` §3) with a comment
  quoting every divergent point and each round's differing positions verbatim, never
  summarized away — a human decides directly, the same as any other blocking judgment
  call. For `/pilot-dev`, the same, plus push every instance's branch (never merge them)
  and link each one in the comment so the human can compare real diffs; no PR is opened
  yet. For `/pilot-review`, don't add `needs-human` directly — fold the divergence into
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
