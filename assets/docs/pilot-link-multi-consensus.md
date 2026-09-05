# PILOT link — Multi-instance consensus (`--multi <N>`)

Read directly by `pilot-scope`/`pilot-spec`/`pilot-dev`/`pilot-review`'s own `SKILL.md` to
run their own comparison logic — never injected into any `Agent` call, and never read by
`.claude/agents/pilot-*.md`, which carry only identity now and never need to know they're
part of an ensemble: every one of the N instances runs its ordinary duty, unmodified, same
task doc, same prompt, as if it were the only one. See `.pilot/pilot-process.md` §4 for the
generic claim protocol and interaction modes this builds on.

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
(e.g. `pilot-auto/SKILL.md`'s "Determining the mode"). `--multi 1` is valid syntax but a
no-op, identical to omitting the flag — one instance has nothing to reconcile against, so
it's adopted directly with no comparison step at all. This is orthogonal to which ticket
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

For `/pilot-dev` only, no effect on reclaiming a `status:changes-requested` ticket: the
phase-5 review already specified exactly what to fix, so that path never proposes an
approach to ensemble on in the first place, pair or `--auto` alike — whether a given
ticket, or one a bare pool resolves to, turns out to be a reclaim isn't always known
upfront, so `--multi` silently proceeds as a single instance there instead of erroring.

## Mechanics

### One ensemble round

Call the `Agent` tool N times in parallel, `subagent_type` the persona already in use for
this phase (or, in `/pilot-review`, for the specific role being ensembled), identical
prompt and inputs each time — the ordinary duty, unmodified — each instance fully isolated
from the others — none sees any other's output, the same independence guarantee
`/pilot-review`'s existing multi-persona parallelism already relies on
(`.pilot/pilot-process.md` §4).

### Consensus check — the skill's own comparison, no further `Agent` call

Once all N return, **the skill itself compares their raw outputs directly** — never a
further `Agent` call: the skill already holds the same duty's task doc (read to build each
instance's prompt) and all N outputs in its own context, and judging whether they
substantively agree doesn't need a fresh persona-framed context the way, say, actually
writing a spec or reviewing a PR does. Never invent a new answer no instance actually
produced:

- **Every substantive decision point agrees** (allowing for surface differences in
  wording/structure) → adopt any one of the agreeing instances' output verbatim — they're
  substantively interchangeable at that point.
- **Any substantive point genuinely diverges** → note exactly which point(s) diverge and
  quote each instance's differing position verbatim, without picking a winner.

What counts as a "substantive decision point" is specific to each caller:

- **`/pilot-scope` (architect)**: split y/n; the resulting task set and each task's own
  `type:`/priority; security/architecture decisions; recorded dependencies; a wont-do
  verdict; any prerequisite ticket(s) and hard-blocker status; any `needs-human` flag.
- **`/pilot-spec` (tech lead)**: the technical approach/design decisions in the spec; any
  blocking conflict raised against the architect's decisions.
- **`/pilot-dev` (dev/e2e)**: the ensemble runs at the **proposed-approach stage only**
  (`pilot-dev/SKILL.md` step 3) — never on finished code, so there's nothing to push or
  diff to compare: N instances each propose an implementation approach, never touching
  code yet. A substantive decision point here is the approach itself (overall design,
  which files/layers it touches, the tradeoff it makes) — surface differences in how it's
  worded don't count. Once reconciled (or approved by a live human in pair mode, same as
  any single-agent proposal), exactly **one** further `Agent` call implements it
  (`pilot-dev/SKILL.md` step 4) — the only extra `Agent` call this feature ever adds beyond
  the N ensemble instances, since implementing is still real, dedicated work a fresh
  persona-framed context is worth spending on.
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
  the skill's own disagreement summary from the round just compared, appended so the fresh
  instances can reconsider it — then the skill compares again.
- That second round still disagrees → stop ensembling on that point. For `/pilot-scope`,
  `/pilot-spec`, and `/pilot-dev` (still at the proposed-approach stage — nothing
  implemented yet, so nothing to push or clean up), add `needs-human`
  (`.pilot/pilot-process.md` §3) with a comment quoting every divergent point and each
  round's differing positions verbatim, never summarized away — a human decides directly,
  the same as any other blocking judgment call. For `/pilot-review`, don't add
  `needs-human` directly — fold the divergence into one `decision`-tagged point in that
  role's list instead (above), scoped to the specific contested point only; the rest of
  that role's reconciled points, and the other roles' own ensembles, proceed normally, and
  step 6's aggregation adds `needs-human` the ordinary way once it sees that point.
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
