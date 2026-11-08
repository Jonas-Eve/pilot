# PILOT — Ticket Pipeline (Simplified Multi-Agent Process)

PILOT is a lightweight multi-agent ticket process: specialized agent personas take a piece of work from a raw idea to a
merged PR, each phase running in its own isolated agent context (§5) rather than accumulating the whole ticket's history.

This document holds what every phase shares: the vocabulary (labels and statuses, §3), the cross-cutting flags, the claim
contract (§4), pair and `--auto`, context isolation (§5) and the module switch (§8). A phase's own contract — the statuses it
consumes, claims into and produces — is `python3 .pilot/pilot.py contract <phase>` and its skill; what links two phases is a
`pilot-link-*.md`. The skills and agents reference this file rather than repeating it.

---

## 0. Prerequisites

The PILOT labels (`REQUIRED_LABELS` in `.pilot/pilot.py`, created by `scripts/setup-github-labels.sh`) must exist before any
skill runs; `pilot.py doctor` checks them. Every phase acts only on a ticket that is currently in its own pre-claim `status:`
(§4 "Claim Protocol"): nothing infers which phase a ticket belongs to or invents work. Run with a ticket number it works that
ticket; run bare it works its pool (§4 "Picking the next ticket..."). `/pilot-discovery` and `/pilot-qa` are pair-only and never
scheduled.

## 2. Ticket Types And Levels

Two independent axes classify every ticket, neither inherited from a parent: **`type:`** (`feature`, `tech`, `bug`, `e2e` — the
nature of the work; it decides who originates the ticket and the phase-4 reviewer set, `.pilot/pilot-link-review-consensus.md`)
and **`level:`** (`epic` → `story` → `task`, never deeper). Where each type originates and how the tree is built:
`.pilot/pilot-link-ticket-tree.md`.

---

## 3. Labels

### `type:` — the nature of the work, set independently on every ticket (`.pilot/pilot-link-ticket-tree.md`)
- `type:feature`
- `type:tech`
- `type:bug` — a defect in already-shipped code (`.pilot/pilot-link-ticket-tree.md`); classified and originated by the
  architect alone via Spec's own no-ticket entry (or reused identically by
  dev/e2e/qa when they discover one inline), reviewed by tech lead alone (architect
  optional), same as `type:tech`. Always `level:task` directly, never `level:story` —
  it never splits (`.pilot/pilot-link-ticket-tree.md` "Three levels").
- `type:e2e` — a `level:task`'s own type, never a `level:story`'s or `level:epic`'s;
  always exactly one per `type:feature` split (`.pilot/pilot-link-e2e-tasks.md`), reviewed by
  PM + tech lead, same set as `type:feature`. It changes which agent
  `/pilot-dev` calls in phase 3 (`pilot-e2e` instead of `pilot-dev`).
- `type:poc` — a prototype of a feature, built with a human in `/pilot-proto` before any Discovery
  and used to decide whether to build it. Always a standalone `level:story`, never split, never
  through Spec, Dev, Review or QA (`pilot.py resolve` refuses it there, and refuses anything else
  in `/pilot-proto`). Its states are the `status:poc-*` labels below.

Never inherited from a parent to a child (`.pilot/pilot-link-ticket-tree.md` "Types and where each originates") — a story's tasks each get whichever of
the four fits that specific task, assigned by Spec at split time.

### `level:` — depth in the tree, set once at creation, never recomputed
- `level:epic` — always `type:feature`; groups several `level:story` tickets, `type:feature`
  or `type:tech` alike (`.pilot/pilot-link-ticket-tree.md` "Three levels"). Carries no
  `status:` label and never moves through the pipeline itself — its stories are linked to
  it as native GitHub sub-issues (`mcp__github__sub_issue_write`), not a hand-written
  checklist. It **auto-closes once every one of its stories is closed** (see "Cascading
  completion" below) — same mechanism as a split story's tasks, one level up, and just as
  terminal: further work in the same area becomes a new Epic, not a story reopening this
  one.
- `level:story` — the root unit Discovery produces for `type:feature` (and any grouped
  `type:tech`), or Spec's own no-ticket entry produces for a standalone `type:tech` need
  (`.pilot/pilot-link-ticket-tree.md` "Three levels").
- `level:task` — a dev-sized unit of a `status:split` story, or a standalone `type:bug`
  ticket with no parent (`.pilot/pilot-link-ticket-tree.md` "Three levels"). Never itself split further — depth is capped
  at these three levels.

### `status:` — the pipeline state machine, one label at a time
```
draft → backlog → in-spec → dev-ready → in-dev → review-ready →
  in-review → approved → done
              ↓         ↓
              +---- wont-do (before dev starts) ----+

in-spec → split (tracker for tasks, reaches done only by cascade — see below)

split (type:feature only) → qa → in-qa → done (Phase 5 — Human QA, `.claude/skills/pilot-qa/SKILL.md` — instead of
cascading straight to done like a type:tech split does)

in-review → changes-requested → in-dev → review-ready → in-review (loop back through dev
when phase 4 blocks on something that needs an actual code change — see
`status:changes-requested` below and `.pilot/pilot-link-review-consensus.md`)
```
- `status:draft` — Discovery, or Spec's own no-ticket entry, has created the ticket but
  the human hasn't given final approval yet — assigned to whoever's session created it,
  the moment the agents' first draft exists (§4 "Interaction modes"). Excluded from every
  phase's candidate pools, never picked up bare, only reachable by an explicit
  `--resume <issue>` or once a cleared `needs-human` flag makes it resumable. Becomes
  `status:backlog`, unassigned, once the human gives final approval — or, if rejected as
  out of scope instead, `status:wont-do` for a `type:feature`/`type:tech` draft, or
  `needs-human` (still `status:draft`) for a `type:bug` one (`status:wont-do` below). The
  one exception: Spec's own no-ticket entry (`.pilot/pilot-link-ticket-tree.md` "Types and where each originates") doesn't stop at `status:backlog`
  on approval — the same session immediately continues to split/spec what it just
  drafted, so it goes straight to `status:in-spec`, still assigned to that session,
  instead of a momentary unassigned stop nothing would ever pick up.
- `status:backlog` — ticket formalized (a `level:story` from Discovery, or a standalone
  `type:tech` story/`type:bug` task created directly), Spec hasn't started on it.
- `status:in-spec` — Spec (architect+tech lead) has claimed it — covers both the split
  decision and the spec-writing, one continuous claim.
- `status:split` — Spec decided this story is too big for one pass through Dev and broke
  it into tasks instead (`.pilot/pilot-link-ticket-tree.md` "Three levels"). The story
  carries no further `status:` transitions of its own from here — it's a tracker for its
  tasks, the same role an Epic plays for its stories, one level down. It reaches
  `status:done` only via cascading completion (below), never directly.
- `status:dev-ready` — split (if any) and spec written, ready for phase 3 (Dev).
- `status:in-dev` — a dev has claimed it for phase 3.
- `status:review-ready` — a PR is open, unassigned, not currently claimed by phase 4: set
  by `/pilot-dev` when it opens a PR, or pushes a reclaim fix, in place of setting
  `status:in-review` directly (§4 "Claim Protocol" — this is phase 4's own pre-claim
  status, matching `status:dev-ready`'s role for phase 3).
- `status:in-review` — phase 4 has claimed it (§4 "Claim Protocol") and is running, or
  blocked on a `decision`-only point awaiting a human — `needs-human` sits alongside, same
  as any other phase's in-progress status (§3 "`needs-human`" below). Never set directly by
  `/pilot-dev`, only by phase 4's own claim.
- `status:changes-requested` — phase 4 found at least one blocking point tagged `change`
  (`.pilot/pilot-link-review-consensus.md`): an actionable code-level fix, not just a
  question for a human to weigh in on. Set instead of leaving `status:in-review`.
  `needs-human` accompanies it only when the same review also carries at least one
  `decision`-tagged point still awaiting a human — a block made entirely of `change`
  points needs no human decision, so it skips `needs-human` altogether and
  `/pilot-dev` may claim it right away, same as any other pre-claim status. When
  `needs-human` is present (a mixed review), `/pilot-dev` claims it only once a human
  clears that flag (`.pilot/pilot-link-review-consensus.md` "Reclaiming a `status:changes-requested` ticket"). Phase 4 unassigns
  the ticket with its verdict, like every phase's hand-off. The dev pushes
  new commits to the *same* already-open PR (never a second PR for the same ticket) and
  moves the ticket to `status:review-ready` when done — never `status:in-review` directly,
  phase 4 claims it fresh.
- `status:approved` — phase 4 ran and every reviewer approved
  (`.pilot/pilot-link-review-consensus.md`) — set, unassigned, instead of
  leaving `status:in-review`. This is the "ready to merge, nothing outstanding" signal.
  Without `--merge`, a human still performs the actual merge — PILOT's default is never to
  merge on its own. Given `--merge` (§4 "Interaction modes"), the same run merges the PR
  itself right after submitting the review, using the repository's normal merge method; the
  ticket then reaches `status:done` via
  `pilot-status-on-merge.yml` exactly as it would after a human merge. There's no automatic
  re-review trigger if new commits land on the PR after this before it's actually merged —
  re-run `/pilot-review` on it by hand, or move it back to `status:review-ready` yourself,
  before merging.
- `status:wont-do` — the concluding agent decided this ticket shouldn't be built after all
  (out of scope, duplicate, superseded) and closed the issue instead of continuing it.
  Settable in two places, both before any spec or code has been written: Discovery/Spec's
  own drafting pass, replacing `status:draft` when a draft is
  rejected instead of leaving a closed issue still labeled `status:draft`; or Spec, in
  place of splitting/speccing the ticket. Once a ticket has reached `status:dev-ready` or
  later, killing it is a human call instead: flag `needs-human` with the reasoning and let
  a human close it. A `type:bug` ticket never carries this label at all: an invalid report
  caught before its ticket even exists is
  simply never created, and a bug draft that only turns out invalid after its ticket
  already exists (or any bug found invalid post-creation) goes the `needs-human` route
  instead of a direct close.
- `status:qa` — a `type:feature` `status:split` story whose e2e task (and therefore
  every dev task it depends on) has reached `status:done` — set by
  `.github/workflows/pilot-status-on-merge.yml` in place of the ordinary cascade straight
  to `status:done` (§3 "Cascading completion"; `.claude/skills/pilot-qa/SKILL.md` "Phase 5 — Human QA"). Never set on a
  `type:tech` story, and never on a task itself — which covers every `type:bug` ticket too,
  always `level:task` (`.pilot/pilot-link-ticket-tree.md` "Three levels"). Unclaimed, unassigned — the fresh-work pool
  `/pilot-qa` picks from.
- `status:in-qa` — `pilot-qa` has claimed it for phase 5.
- `status:done` — the ticket is closed, whether merged (a task, or an unsplit `type:tech`
  story) or completed by cascade (a `status:split` story — §3 "Cascading completion") or,
  for a `type:feature` one, by phase 5 (see below and `.claude/skills/pilot-qa/SKILL.md`). Not set by any phase skill directly
  for an actionable ticket coming out of a merge (merge is always a human action or, for
  phase 4, an explicit `--merge` run, `status:approved` above — either way outside PILOT's
  control at the moment it happens) — set instead by the
  `.github/workflows/pilot-status-on-merge.yml` GitHub Actions workflow, independent of any
  agent session being alive:
  - Triggered on `pull_request: closed` (gated on `merged == true`): resolves the issue(s)
    the merge closes via `PullRequest.closingIssuesReferences`, sets `status:done` on each,
    and, for any that's a task, runs the cascading-completion check (§3 "Cascading
    completion") against its `status:split` parent story, then, if that story itself just
    closed, against its own parent Epic in turn. This is the only place `status:done` gets
    set on an actionable ticket coming out of a merge.
  - Also triggered on `issues: closed`, for completions that never go through a PR merge at
    all: `status:wont-do` (above), which Spec sets and closes directly, and any hand-closed
    issue. This path only runs the cascading-completion check (§3
    "Cascading completion") — never sets `status:done` itself, since the closing party is
    responsible for the issue's own terminal `status:` label — and only when the issue
    already carries `status:done` or `status:wont-do`. It skips entirely when GitHub's own
    timeline shows the closure came from a merged commit reference, so the same closure is
    never processed twice.

  `/pilot-qa` is the one place a phase skill *does* set `status:done` directly, once a
  human confirms the story's behavior in phase 5 (`.claude/skills/pilot-qa/SKILL.md`) — there's no PR merge there for the
  workflow to react to.

  **Known limitation:** GitHub only recognizes a `Closes #N` reference (populating
  `closingIssuesReferences`, which the workflow reads) when the merging PR's base is the
  repository's *default* branch — never for a PR merged into an intermediate,
  not-yet-merged branch, even once that branch later reaches the default branch itself.
  If a ticket's implementing PR had to be based on another PILOT PR's branch instead of
  the default branch directly, the workflow finds zero closing issues on that merge and
  does nothing — set `status:done` on the ticket by hand once everything has actually
  landed on the default branch. Not fixable in the workflow itself; a GitHub platform
  behavior.

`level:epic` tickets never carry a `status:` label at all. `status:wont-do` and
`status:split` tickets don't carry any *other* `status:` label — the rest of the state
machine only applies to tickets still actively moving through Spec/Dev/Review themselves.

### `needs-human` — an orthogonal flag, not a pipeline state

Unlike every label above, `needs-human` never replaces the ticket's current `status:` —
it sits alongside whichever one is already there. When a phase hits something only a
human can decide, it leaves the ticket's `status:` exactly where it was and adds
`needs-human`, plus a comment. That comment is never optional and is never just the label
with no context attached — it must say, explicitly, both **why** the ticket needs a human
right now and **what's needed** from a human to unblock it. A label with no comment, or
one that only restates "needs a human" without saying why or what for, is not a valid use
of this flag — whoever reads it next has to be able to act from the comment alone.

**Phase 4 is the one exception to "`status:` stays exactly where it was."** A phase-4
block that's entirely `change`-tagged (`.pilot/pilot-link-review-consensus.md`) has nothing
for a human to decide, so it skips `needs-human` same as this section's rule requires — but
still moves to `status:changes-requested` instead of leaving `status:in-review`, since the
ticket needs code regardless of any human input, and `/pilot-dev` may reclaim it right
away. A block that also carries a `decision`-tagged point keeps `needs-human` as usual,
still alongside `status:changes-requested` — the flag gates `/pilot-dev`'s reclaim until
the `decision` point(s) are resolved, even though the `change` point(s) in the same review
are already actionable.

A human resolves it by **removing the `needs-human` label** once they've responded (a
reply comment) or decided there's nothing more to add — the label's absence is the whole
signal that the block is resolved. Whether it's also picked up automatically from there
is a separate choice — see `can-resume` below.

**Always add `needs-human` and post the why/what's-needed comment the moment a phase
hits something only a human can decide** — one path, not two, whether or not a human
happens to be live in the same session right then. What differs by context is only what
happens *next*:

- **Nobody answers on the spot** (a scheduled sweep with no human present, or an
  interactive human who says they need to think about it) — the label and comment stay
  exactly as posted, and the ticket waits for the async resume protocol below.
- **A human is live in the same session** and answers right there in conversation — the
  agent still posts the why/what's-needed comment first, exactly as it would if nobody
  were around; a quick answer is not a reason to skip straight to a resolution. Once the
  human answers, the agent proceeds with that answer and, in the same turn, posts a
  **second** comment summarizing what was actually decided — *then* **removes
  `needs-human` itself**. It never removes it silently: the ticket's GitHub history must
  show both the block and its resolution even when the conversation that resolved it never
  touched GitHub at all — a blocking comment followed by a resolution comment (or, for
  phase 4, a blocking review followed by a second, corrected review,
  `.pilot/pilot-link-review-consensus.md`), whether the
  gap between them was seconds (live) or days (async).

#### Cascading completion

This applies to `status:split` stories only — a story's tasks are a fixed set for
whichever round is currently in flight (the original split, or a later re-scope round,
`.pilot/pilot-link-ticket-tree.md` "Re-scoping a `type:feature` story after its split is done"), so completeness at
any given moment is provable from a live read of its current sub-issues — never a cached
list. An Epic's own story set can grow while it stays open — new stories are added under
it at any point — but once every one of them is closed (`status:done` or `status:wont-do`),
that's the Epic's own definition of done: the same live read, one level up, closes it too
(below), and that closure is final — it is never reopened to take another story back in.

Whenever a task reaches `status:done` or `status:wont-do`, check whether its parent
is a `status:split` story and, if so, whether *all* of that story's other tasks are
now also done/wont-do. A standalone `type:bug` task has no parent at all (`.pilot/pilot-link-ticket-tree.md` "Three levels") — this check simply finds none and does nothing further; the bug ticket's own
`status:done`, set directly on merge, is the end of it.
- Not all done yet → do nothing further, the parent stays `status:split`.
- All done, parent is `type:tech` (the only root type that can reach `status:split`
  without being `type:feature` — `type:bug` is never even a `level:story`, so it never
  has a parent to check in the first place) → set the parent story itself to
  `status:done` **and close its issue** — it was never merged directly, so nothing else
  in the pipeline would otherwise ever close it (unlike a task, whose merging PR closes it
  natively via `Closes #N`).
- All done, parent is `type:feature` → set the parent to **`status:qa`** instead of
  `status:done` (`.claude/skills/pilot-qa/SKILL.md` "Phase 5 — Human QA") — every `type:feature` split includes exactly
  one e2e task depending on all its dev siblings, so "all done" here is structurally the
  same moment the e2e task itself just finished. `status:done` for this story is set
  later, by `/pilot-qa` itself, once a human confirms the behavior.

Whenever a story's own issue closes — cascaded to `status:done` just above, closed
directly as `status:wont-do` (Spec), or closed by `/pilot-qa` once QA'd — also check
its own parent: if it belongs to an Epic and *every* one of that Epic's stories is now
closed (`status:done` or `status:wont-do`), close the Epic's issue too. An Epic carries no
`status:` label, so closing its issue is the whole of it — and it's terminal: a related
need afterward starts a new Epic, never a story reopening this one.

No periodic sweep exists beyond this — the check is event-driven, not polled. A
`status:split` story whose last task was closed without ever carrying
`status:done`/`status:wont-do` (mislabeled outside PILOT's own conventions) is the one
case this still can't catch, since there is no terminal-status event to react to.

### `on-hold` — an orthogonal pause flag, unrelated to a pending decision

Distinct from `needs-human`: `needs-human` means a phase hit something it needs a
person's judgment on *right now*, and stops until that judgment comes. `on-hold` means
the opposite kind of "don't touch this" — nobody needs to look at it or decide anything
imminently, it's paused because of something bigger in flight elsewhere (a global
restructuring, a dependency on an Epic or on several/fuzzy conditions, deliberately
deferred work) and picking it up now would just be wasted or wrong. A dependency on **one
specific, still-open ticket** is not this — that's the "Depends on #N" mechanical gate
instead (§4 "Blocked-by dependencies"), which needs no label and clears itself the moment
that ticket closes; reach for `on-hold` only when there's no single ticket a phase skill
could check. Like `needs-human`, it sits alongside whichever `status:` is already there
rather than replacing it.

A human applies it directly at any time, or a phase agent applies it itself if it notices
mid-work that the ticket depends on unresolved global work — either way, always with a
comment saying what it's waiting on. A bare `on-hold` label with no comment is as invalid
as a bare `needs-human` one.

Excluded from every phase's candidate pools exactly like `needs-human`. Only a human
removes it, once whatever it was waiting on has actually resolved — there's no
live-session "answer it and remove it in the same turn" path like `needs-human` has,
since there's no question being asked that a live human could answer on the spot. Once
removed, the ticket is simply a normal candidate again. The two flags are independent and
can coexist; clearing one has no effect on the other.

### `can-resume` — a human's mechanical signal that in-progress work is ready to be picked back up

Distinct from `needs-human`/`on-hold`: those two *block* a pool; this one *opts an
already-claimed, in-progress ticket into* one. Only a human ever adds it, in either of two
situations (§4 "Resuming a `needs-human` ticket", "Resuming an orphaned claim"): resolving
`needs-human` and deciding the ticket should resume automatically rather than wait for
someone to type `--resume`, or verifying firsthand that an orphaned claim is genuinely
dead and safe to hand to the next sweep. Either way it means the same thing: whatever's
recorded on the ticket so far is safe to continue from, unattended. A plain label check
— the same deterministic, mechanical style as "Blocked-by dependencies" below — never
something a subagent reasons about or a comment thread it has to reconstruct.

The claiming phase skill removes it the moment it claims the ticket — a one-time "ready"
signal, not a standing state. A human who'd rather resume it themselves, right now, skips
the label entirely and runs `--resume <issue>` directly; both paths preserve the ticket's
recorded progress, they only differ in who picks it back up and when.

### `priority:`
- `priority:P0` / `priority:P1` / `priority:P2` — every ticket gets an initial value at
  creation, set by whichever agent creates it: the PM for `type:feature`/grouped
  `type:tech` (business value/urgency to the user for the feature; the architect's
  technical framing for a grouped tech story), the architect for a standalone `type:tech`
  need or a `type:bug` (the technical framing below — neither has a PM angle). This is
  what lets `/pilot-spec`'s own `status:backlog` pool (§4
  "Picking the next ticket...") sort on something real instead of every fresh story
  falling back to oldest-first.
- At Spec, the architect+tech lead reconfirm or revise it: unchanged if the ticket ends up
  not split (still the one leaf — `type:tech` only, `type:feature` always splits), or
  replaced by each task's own priority if it splits — a task's priority doesn't have to
  match its story's initial one (e.g. a `type:tech` enabler task inside a `type:feature`
  split may be more or less urgent than the user-facing tasks around it). The moment a
  story reaches `status:split`, its own `priority:` label is removed — from then on it's
  a tracker, and its tasks are what any pool actually selects among.
- Not set on `level:epic` (never itself a candidate in any pool) or `status:split`
  tracker parents (superseded by its tasks' own the moment it splits, above).
- Rough default for the *technical* framing (`type:tech`, `type:bug`, and any `type:tech`
  task within a `type:feature` split) if this project has no priority convention of its
  own: P0 closes a real gap (security, correctness, a broken safety net) — do it soon;
  P1 is solid value, not urgent; P2 is nice-to-have or conditional. For `type:feature`,
  the PM's call is about business value/urgency to the user instead. Adopt this project's
  own priority convention in either case, if it already has one that differs.

---

## 4. Claim Protocol (avoiding two agents on the same ticket)

Phases 2 (Spec), 3 (Dev), 4 (Review), and 5 (QA) each start by **claiming** the ticket
before doing any real work, because several instances of the same phase (e.g. several
devs, or two overlapping scheduled review sweeps) may run concurrently. Discovery doesn't
fit this pattern the same way — there's no pre-existing ticket to claim — but the moment
it creates the ticket (`status:draft`, §3), it assigns it the same way, and that
assignment sticks if the pair session ends before final approval, exactly like a claimed
ticket left mid-phase; see "Resuming an orphaned claim" below. Spec's own no-ticket entry
(a standalone `type:tech`/`type:bug` need) behaves the same way as Discovery here — the
ticket is created and assigned the instant a first draft exists, before any human
approval.

The mechanics are `.pilot/pilot.py claim <phase> <issue> --mode ...` (`pool` and `resolve` decide
what to claim); its source is the reference for the exact conditions. The contract:

- A ticket is claimable only in the phase's pre-claim `status:` and unassigned — or, for the
  explicit modes below (resume, reclaim, re-scope), in the status that mode names. Anything
  else is refused, never overwritten silently.
- A claim sets the assignee to the current session's GitHub user and swaps `status:` to the
  phase's in-progress one in one write, then re-reads the ticket. If the assignee is no
  longer this session, another run won the race — stand down and pick something else.
  Optimistic, not a real lock: cheap insurance against the common case, not a guarantee
  under true concurrent writes.
- The phase's real work (the subagent call(s)) starts only after a successful claim.

Phase 4's claim only serializes separate *runs* of `/pilot-review` against the same
ticket — the reviewers **within** one claimed run (two, or a human-narrowed subset,
`pilot-review/SKILL.md` step 3) still execute independently in parallel, never seeing each
other's verdict (`.pilot/pilot-link-review-consensus.md`).

### Picking the next ticket when none is specified

Discovery has no such pool at all — it always starts from a raw idea in free text (or an
explicit `--resume <issue>`). Every other phase builds its pool with
`.pilot/pilot.py pool <phase>` (its source is the reference):

- **Fresh work** — tickets in the phase's own pre-claim `status:`, no assignee.
- **Resumable work** — tickets in the phase's own in-progress `status:` carrying
  `can-resume` (§3), a human's explicit signal that this one is safe to hand to the next
  sweep.
- **Reclaimable work** (`/pilot-dev` only) — `status:changes-requested` tickets without
  `needs-human`/`on-hold`: phase 4 sent them back for a code fix
  (`.pilot/pilot-link-review-consensus.md`).

A ticket carrying `needs-human` or `on-hold`, or with an unresolved "Depends on #N" (below),
is never a candidate. An orphaned claim (in-progress `status:`, assigned, no `can-resume`) is
never in a bare pool either: it resumes only via `can-resume` or an explicit `--resume <issue>`
(below). Order: highest `priority:` first (a ticket with none sorts last), then a ticket
carrying a "Blocks #M" comment on a still-open #M, then oldest by creation date.

### Blocked-by dependencies (mechanical gate, distinct from `on-hold`)

A ticket's body may carry one or more "Depends on #N" references. Two places write
them today: the architect, when Spec spins out a prerequisite tech or bug ticket it
judges a hard blocker (`.pilot/pilot-link-ticket-tree.md` "Prerequisite tech/bug tickets"); and
`pilot-dev`/`pilot-e2e` (phase 3) or `pilot-qa` (phase 5), into their own ticket's body
when they originate a bug inline (same doc — always a hard blocker there). The mechanism
itself isn't specific to any of them; anything that writes the same phrase gets the same
gate for free.

**Format: one dependency per line, always.** Multiple dependencies are multiple separate
"Depends on #N" lines, one issue number each — never several numbers combined onto one
line. This keeps the check a per-line literal match, not a list/prose parse.

The gate is `.pilot/pilot.py`'s — a deterministic check, never a subagent's reasoning; its
source is the reference. A ticket with at least one dependency still open (plain open/closed,
not its `status:` label; an unreadable reference counts as open) is excluded from every
phase's pool and, in phases 3 (Dev) and 5 (QA), refused when given explicitly. Spec is the
deliberate exception: re-splitting/re-speccing a ticket doesn't need its own prerequisite
resolved first, so `/pilot-spec` doesn't apply it to an explicitly-given number. Nothing
needs removing by hand — the ticket is a normal candidate again the moment the referenced
ticket closes.

### Resuming a `needs-human` ticket

A human resolves the flag by **removing the `needs-human` label** from the ticket —
optionally after leaving a reply comment with guidance, or with no reply at all if
there's nothing to add beyond "proceed as proposed." That removal, not a reaction or a
particular comment, is the entire signal a phase skill looks for. This can happen from
any session, at any time — nothing depends on the session that raised the block still
being alive. Whether the ticket also carries `can-resume` (§3) decides whether it's a
bare/scheduled-sweep candidate or only reachable by ticket number.

A phase skill treats a ticket as **resuming**, not a fresh claim, whenever it's already
in that phase's in-progress `status:` (whether picked up via `can-resume` or given
explicitly) — already claimed, so no new claim (`.pilot/pilot.py claim --mode resume-cleared`
only consumes the one-time `can-resume` signal, §3):
1. Read the full blocking context, not just the ticket body — the blocking comment and
   everything posted after it, for every phase except Review. Review's own block is a
   submitted PR review, not a comment (`.pilot/pilot-link-review-consensus.md`) —
   read that, plus the PR's comment thread for
   whatever's posted after it.
2. If `needs-human` is still present, it isn't resolved yet — report that and stop (this
   only matters when a ticket number was given explicitly; the bare pool above already
   excludes these).
3. Otherwise proceed with the phase's `Agent`
   call(s), passing both the original blocking context and whatever's in the thread after it
   (a specific reply, or "no reply — treat as approved as proposed" if none). The agent(s)
   proceed, correct, or block again if that still doesn't actually resolve things.

### Resuming an orphaned claim (`--resume`, or `can-resume`)

Distinct from both "Resuming a `needs-human` ticket" above and "Reclaiming a
`status:changes-requested` ticket" below: a ticket claimed but with nobody actually still
working it — still carrying its original assignee, still in that phase's in-progress
`status:` (`status:draft`, `status:in-spec`, `status:in-dev`,
`status:in-review`, `status:in-qa`), with **no** `needs-human`. Two different causes leave
the exact same shape, indistinguishable from the ticket alone: a **pair** session
("Interaction modes" below) that ended before reaching the phase's final approval
(pair-capable phases only), or an `--auto` run that died mid-work (a quota limit, a crash,
a timeout) before it could either finish or flag `needs-human`. Left alone, the normal
claim-protocol check ("already has an assignee → stop") would treat either the same as a
ticket someone else is actively working right now, which isn't the case. For Discovery and
Spec's own no-ticket entry specifically, `status:draft` is what makes this possible at all.

Nothing on the ticket itself distinguishes an orphaned claim from one genuinely still in
progress elsewhere — only a human verifying it firsthand can. Once they have, they can
resume it themselves right now via an **explicit** `--resume <issue>` (below — never part
of any bare/scheduled-sweep pool), or add `can-resume` (§3) to hand it to the next sweep
instead, same as a cleared `needs-human` ticket above.

To resume via `--resume`:
1. Read the full ticket — body and comment thread, not just the latest checkpoint. For
   `/pilot-discovery` and `/pilot-spec`'s pair sessions this reconstructs pair
   mode's incremental checkpoint writes ("Interaction modes" below). `/pilot-review`'s own
   checkpoint is a pending GitHub PR review instead of a ticket comment
   (`pilot-review/SKILL.md` has the mechanics) — still pinned to the PR's current head
   commit → that's the recovered outcome, skip re-running the reviewers; stale or absent →
   discard any stale one and
   restart the reviewers fresh, the tech lead's re-validation needs the actual current code
   regardless. For an `--auto` run of any other phase, there's nothing to reconstruct — a
   plain restart from the ticket's original inputs.
2. Claim it with `.pilot/pilot.py claim --mode resume-orphaned` — an existing assignee
   doesn't count as a conflict here: it is overwritten (assignee → this session) and
   `status:` stays at its current in-progress value.
3. Pass whatever step 1 recovered to the phase's `Agent` call(s) as its starting context,
   and continue: the normal pair loop where one exists, otherwise a fresh pass.

Finalization behaves exactly as any other run of that phase from here.

### Interaction modes: pair (default) and `--auto`

The generic contract below — pair pauses at natural checkpoints and writes progress
immediately, `--auto` skips straight to the finished result — is what each phase's own
`SKILL.md` follows by default; a phase is free to specialize it for its own mechanics
(phase 4/Review does, having no natural mid-work checkpoint the other phases share). The
five phase skills split into three groups by which modes they support:

- **`/pilot-discovery`, `/pilot-qa`** — **pair only**, no `--auto` exists for either. Turning
  a raw idea into a story or a technical need into a ticket is a conversation between the
  drafting agents and a human, not something worth running unattended; symmetrically, phase
  5 is a human physically testing shipped behavior, which has no unattended equivalent at
  all. Neither is ever driven by a scheduled Routine as a result. Both still support
  `--resume <issue>` for a ticket left mid-pair.
- **`/pilot-spec`, `/pilot-dev`** — default to **pair**, with `--auto` to
  opt out of it.
- **`/pilot-review`** — default to **pair** too, with `--auto` to opt out of it, but
  specialized further: its reviewers always run fully parallel and isolated from each
  other regardless of mode — there's no natural mid-review checkpoint while they're
  working, so where pair mode's pause falls depends on the aggregated outcome instead. Any
  outcome carrying `needs-human` (a decision-only block, or a mixed `change`+`decision`
  one, `.pilot/pilot-link-review-consensus.md`) always submits immediately, in both modes —
  §3's `needs-human` rule requires the block to reach GitHub before any resolution, even a
  live one — with pair's value applying only *after*, as a live human resolving it right
  there (§3 "A human is live in the same session") instead of the usual async wait. An
  all-approve outcome, or a pure-`change` outcome (no `decision` point, so no
  `needs-human`), instead pauses *before* submitting, for a last look. `--auto` skips every
  pause. Also supports `--merge` (§3 "`status:approved`") — orthogonal to pair/`--auto` —
  and `--resume <issue>` to recover an orphaned claim (above). `pilot-review/SKILL.md` has
  the full mechanics.

Both modes still claim (above) immediately, same as always — it's concurrency
bookkeeping, unrelated to the content decision.

**Pair** requires a human live in the same session. The agent(s) stop at the phase's
natural checkpoint(s) — the drafted story, the proposed split+spec, the implementation
plan — and the skill relays that to the human as an ordinary reply,
waits for their next message, feeds it back, and repeats until they approve.
**The skill writes progress into the ticket immediately at every checkpoint** (a comment,
or a partial `issue_write`) instead of holding it in-conversation until the whole phase is
done — the ticket itself becomes the durable record of how far the pair session got, which
is what makes `--resume` possible. Where the checkpoint is a comment (Spec, Dev, QA), it's
typically **one comment kept up to date** — created once, then edited in place each round
— rather than a new comment per round; whether that comment stays as-is once the phase
finalizes (QA: it's the actual test log, the only record of what was tried) or gets
collapsed to a short final note once the real artifact exists elsewhere (Spec: the
sub-issues/spec; Dev: the PR) is each phase's own call, covered in its own `SKILL.md`.

For Dev and Review a ticket already exists before the phase starts. **Discovery, and
Spec's own no-ticket entry, are the cases where no ticket exists yet at the very first
checkpoint**. Before creating anything, the skill runs a framing stage with the human:
in Discovery the PM alone challenges the idea with the human and restates it as a brief they
validate; in Spec's no-ticket entry (human live) the architect alone does the same for the
raw need. Only once the human has validated it does the discussion start (the PM leading in
Discovery, the architect and tech lead in Spec, the tech lead checking the need against the
code), and the skill creates the ticket (`status:draft`, §3) as soon as the first draft is ready to show the human, instead of
holding it in-conversation. There is nothing to `--resume` during framing.
Either way, the very last thing pair mode does — setting the phase's completion `status:`
— is the same end-state `--auto` reaches in one pass, for the phases that have an `--auto`
(Discovery/QA don't, above).

**Final consolidation pass, every phase with incremental checkpoints, right before setting
the completion `status:`.** Writing progress checkpoint by checkpoint means the ticket (or,
for Dev, the diff) was assembled incrementally, round by round of the pair
conversation — nothing guarantees a decision from an early round still squares with one
added several rounds later. Once the human gives final approval, before applying the
completion label, re-read the whole thing as it now stands — the full ticket
body, not just the latest round's delta; the full diff, not just the last commit, for
Dev — and fix anything incoherent or incomplete found. This is also what
`pilot-dev` uses as its own self-review of the implementation before opening
the PR — a substitute for a separate reviewer checking the same thing again in Review
(`.pilot/pilot-link-review-consensus.md`), not an addition to it. Review has no
incremental assembly to reconcile this way — its own aggregation already collapses every
reviewer's one-shot verdict into a single outcome before its one pair checkpoint is ever
reached, so there's nothing earlier to re-read against; each reviewer instead re-checks
its own points once, right before returning its verdict
(`.pilot/pilot-link-review-consensus.md`).

**`--auto`** is the old default, before pair mode existed: the agent(s) decide everything
and the skill applies the finished result straight to GitHub in one pass, no human
checkpoint. This is what a scheduled Routine must use for `/pilot-spec`,
`/pilot-dev`, or `/pilot-review` (`.claude/skills/pilot-auto/SKILL.md` "Scheduled sweeps") — pair requires a live human.
`/pilot-discovery` has no `--auto` and is therefore never Routine-driven; Spec's own
no-ticket entry, since it needs a raw idea a human types in, is likewise never
Routine-driven regardless of `--auto`, in practice.

`--auto` and `--resume` are mutually exclusive with each other and with pair mode itself —
pick exactly one per run. `--with <persona>[,...]` (`.pilot/pilot-link-agent-dialogue.md` "Roster") is orthogonal to all of
them. `--merge` (Review only, §3 "`status:approved`") is a separate,
orthogonal flag: it controls only whether an all-approve outcome also merges the PR itself,
and combines with either pair or `--auto`. `--multi <N>` (`/pilot-discovery`, `/pilot-spec`,
`/pilot-dev`, `/pilot-review` only, `.pilot/pilot-link-agent-dialogue.md` and
`.pilot/pilot-link-multi-consensus.md`) is orthogonal to both: it runs an ensemble on the one
claimed ticket and reconciles it into the single proposal that pair reviews or `--auto`
applies straight through — combines with either mode, invalid only alongside `--resume`
(resuming already-claimed progress, not a fresh ensemble opportunity).

This is unrelated to the "ask live" behavior in §3 ("`needs-human` — an orthogonal
flag") — that one fires for a genuine blocker the agent can't resolve alone, whether or
not pair mode is active; pair is for iterating on a draft together even when nothing is
actually blocking.

## 5. Token Efficiency: Isolated Contexts Per Phase

Keeping token cost down per ticket is central to PILOT's design. Two rules keep it cheap:

1. **No phase carries a prior phase's transcript.** A phase skill reads only what that
   phase needs from the ticket (its current body, linked parent/children, the relevant
   `docs/` files) and hands that — never the pipeline's history — to a fresh `Agent` call
   using the matching persona in `.claude/agents/pilot-*.md`. This isolation is across
   phases, not within one: Spec's own dialogue and a Roster discussion (`.pilot/pilot-link-agent-dialogue.md`) are
   several separate `Agent` calls, one per turn, each one a genuinely fresh context that
   re-reads whatever it needs (this file included) — the running conversation is passed
   as explicit text, not shared memory, so a longer dialogue costs more, turn for turn,
   the same as any other `Agent` call would. The isolation boundary this rule actually
   buys is between phases (and, within Review, between reviewers) — never a claim that a
   multi-turn dialogue is somehow free.
2. **Claim/label bookkeeping is deterministic tool calls in the skill itself**, not
   something the agent reasons about. Only the actual thinking — writing the story,
   splitting/speccing the ticket, writing the code, reviewing the PR — goes
   through an `Agent` call.

A human driving several phases back to back for the same ticket passes forward only the
ticket number between them — never a running transcript of the prior phase's `Agent` call.

---

## 8. Optional modules

A project turns an optional module on in `.pilot/state.json` (`"modules": {"wiki": true, "dashboard": true, …}`; `python3
.pilot/pilot.py module list|enable|disable`; a module may require another: `enable` refuses until it is on,
`--with-requires` turns both on). A module that is off, or absent from the file, changes nothing: every step
below that names it is skipped. A module's own skill proposes turning it on at first use. The modules: `wiki`, `architecture`,
`dashboard` (the team page; its tabs follow the modules a project has on), `design` and `proto` (the design system
and the prototypes, which need `dashboard`).

**`wiki`.** `wiki/` at the project root is the source of truth for what the product does and what is
promised, and every phase works with it: Discovery and Spec write the entries of a story (`proposed`, then
`specified`), Dev completes them (`implemented`), Review checks a PR against them, QA builds its test plan
from them. **When the wiki and the code disagree, the wiki is right**; a divergence is a human's call, never
settled silently. **Only a PR changes the wiki** — a code PR carries its own wiki change — so `main` and
every branch stay coherent. With the module on, `python3 .pilot/pilot.py doctor` also requires `wiki/`. The
entry format, statuses and rules are `.pilot/pilot-link-wiki.md`; the mechanics are `python3 .pilot/pilot.py
wiki …` and `/pilot-wiki` (it turns the module on; `--bootstrap` drafts the wiki from the project's tickets and code).

**`architecture`.** `architecture/` at the project root says how the product is built and why: an overview of the
apps, the technical guidelines AIs and developers must respect, and the architecture decision records (ADR). Only
a PR changes it. With the module on, `doctor` also requires `architecture/`. The layout, statuses and rules are
`.pilot/pilot-link-architecture.md`, and how any agent reads the two bundles (by levels, search, then `show`, never the files) is
`.pilot/pilot-link-knowledge.md`; the mechanics are `python3 .pilot/pilot.py arch …` and `/pilot-architecture`
(it turns the module on; `--bootstrap` drafts it from the existing apps, `--scaffold` creates them).
