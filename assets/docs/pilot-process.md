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
  always exactly one per `type:feature` split when the workflow has it (`.pilot/pilot-link-e2e-tasks.md`), reviewed by
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

### `status:` — the pipeline state, one label at a time

Each status is produced by one phase and consumed by another; `python3 .pilot/pilot.py contract` lists them per phase and checks that they
compose. A ticket carries one `status:` at a time.
- `status:draft` — created, awaiting the human's final approval, assigned to the creating session. In no pool; reachable only by an explicit
  `--resume` or a cleared `needs-human`. Approval → `status:backlog` (unassigned); rejection → `status:wont-do` (a `type:bug` draft goes
  `needs-human` instead, still `draft`). Spec's own no-ticket entry goes straight to `status:in-spec` on approval, still assigned.
- `status:backlog` — formalized (a `level:story` from Discovery, or a standalone `type:tech` story or `type:bug` task); Spec has not started.
- `status:in-spec` — Spec has claimed it: the split decision and the spec, one continuous claim.
- `status:split` — Spec broke the story into tasks. It keeps no further `status:` of its own, a tracker for its tasks like an Epic for its stories,
  and reaches `status:done` (or `status:qa`) only by cascade (`.pilot/pilot-link-cascade.md` "Cascading completion").
- `status:dev-ready` — spec written, ready for Dev.
- `status:in-dev` — a dev has claimed it.
- `status:review-ready` — a PR is open and unclaimed: phase 4's pre-claim status, set by `/pilot-dev` when it opens the PR or pushes a reclaim fix,
  never `status:in-review` directly.
- `status:in-review` — phase 4 has claimed it (`needs-human` may sit alongside, blocked on a `decision`-only point). Only phase 4's own claim sets it.
- `status:changes-requested` — phase 4 found a blocking `change` point (`.pilot/pilot-link-review-consensus.md`), set instead of leaving
  `status:in-review`, unassigned. `needs-human` accompanies it only when the same review also carries a `decision` point awaiting a human; a pure-`change`
  block needs none and `/pilot-dev` may claim it at once. The dev pushes to the *same* PR (never a second one) and sets `status:review-ready`.
- `status:approved` — every reviewer approved (`.pilot/pilot-link-review-consensus.md`): ready to merge, unassigned. A human merges unless `--merge` was
  given (§4 "Interaction modes"); later commits trigger no re-review — re-run `/pilot-review` or move it back to `status:review-ready` before merging.
- `status:wont-do` — decided not to build, issue closed. Set only before any spec or code exists (Discovery or Spec drafting, replacing `status:draft`, or Spec
  in place of splitting); from `status:dev-ready` on, killing it is a human call (`needs-human` with the reasoning). A `type:bug` never carries it: an invalid
  report is never created, and one invalid after creation goes `needs-human`.
- `status:qa` — (only in a workflow with human QA, `python3 .pilot/pilot.py workflow show`) a `type:feature` `status:split` story whose every task is done, set by the merge workflow, unassigned: `/pilot-qa`'s pool. Never on a
  `type:tech` story or a task (so never on a `type:bug`).
- `status:in-qa` — `pilot-qa` has claimed it.
- `status:done` — closed: merged (a task, or an unsplit `type:tech` story), cascaded (a `status:split` story) or confirmed in phase 5 (a `type:feature`
  story). The merge workflow `.github/workflows/pilot-status-on-merge.yml` sets it (`.pilot/pilot-link-cascade.md`); `/pilot-qa` is the one phase that sets it directly.

`level:epic` tickets never carry a `status:` label at all; `status:wont-do` and `status:split` tickets carry no *other* `status:`.

### `needs-human` — an orthogonal flag, not a pipeline state

`needs-human` never replaces the ticket's `status:`: it sits alongside it. When a phase hits something only a human can decide, it leaves `status:` where it
was and adds `needs-human` plus a comment (`pilot.py flag`). The comment is never optional and must say **why** the ticket needs a human now and **what is
needed** to unblock it; a bare label, or one that only restates "needs a human", is invalid.

Phase 4 alone moves `status:` with it: a block made only of `change` points needs no human, so it skips `needs-human` and moves to `status:changes-requested`
(reclaimable at once); a block that also carries a `decision` point keeps `needs-human` alongside `status:changes-requested`, gating `/pilot-dev`'s reclaim until
the `decision` is resolved (`.pilot/pilot-link-review-consensus.md`).

Flag and comment the moment a phase hits such a blocker, whether or not a human is live. What differs is what follows:
- **Nobody answers on the spot** — the flag and comment stay, and the ticket waits for the resume protocol (§4).
- **A human is live in the same session** and answers there — the agent still posts the why/what comment first, proceeds with the answer, posts
  a **second** comment saying what was decided, then removes `needs-human` itself. Never silently: the ticket's history shows the block and its resolution (for phase
  4, a blocking review followed by a corrected one).

Otherwise a human resolves it by removing the label, optionally after a reply: its absence is the whole signal. Whether the ticket is then picked up automatically is
`can-resume`.

### `on-hold` — an orthogonal pause flag, not a pending decision

The ticket is paused for something bigger in flight (a restructuring, a dependency on an Epic or on several or fuzzy conditions, deliberately deferred work). A
dependency on **one specific open ticket** is not this: that is the "Depends on #N" gate (§4 "Blocked-by dependencies"). It sits alongside `status:`, takes a comment
saying what it waits on (a bare label is invalid), and excludes the ticket from every pool like `needs-human`. A human applies it, or a phase agent that notices mid-work
the ticket depends on unresolved global work; only a human removes it, once what it waited on has resolved (no live-session answer path). The two flags are independent.

### `can-resume` — a human's signal that in-progress work can be picked back up

`needs-human` and `on-hold` block a pool; `can-resume` opts an already-claimed, in-progress ticket into one. Only a human adds it: after resolving `needs-human` when the
ticket should resume unattended, or after verifying firsthand that an orphaned claim is dead (§4 "Resuming a `needs-human` ticket", "Resuming an orphaned claim"). It means
whatever is recorded on the ticket is safe to continue from. A plain label check, never something a subagent reasons about. The claiming phase removes it as it claims; a
human who prefers resumes at once with `--resume <issue>`.

### `workflow:` — one ticket's own workflow profile (optional)
`workflow:standard` / `workflow:lean` on a ticket overrides the project's profile for that ticket and its tasks, when the project allows it (`python3 .pilot/pilot.py workflow show --ticket <N>`
gives the route). Set before Dev starts and then frozen (`pilot.py set` refuses to change it once the ticket is in Dev); Spec copies it from a story to every task it creates (`inherit_labels`).
Without a `workflow` block in `.pilot/state.json` the label is ignored.

### `priority:`
`priority:P0` / `P1` / `P2`, set at creation by whoever creates the ticket: the PM for `type:feature` and a grouped `type:tech` (business value and urgency for the
feature, the architect's technical framing for a grouped tech story), the architect for a standalone `type:tech` or a `type:bug`. It orders `pool`. At Spec the architect and
tech lead reconfirm it, or each task of a split gets its own (independent of its story's); a story's own `priority:` is removed when it reaches `status:split`. Never on a
`level:epic` or a `status:split` tracker. Default technical framing absent a project convention: P0 closes a real gap (security, correctness, a broken safety net) — soon; P1
solid value, not urgent; P2 nice-to-have or conditional. The project's own convention wins.

---

## 4. Claim Protocol (avoiding two agents on the same ticket)

Spec, Dev, Review and QA start by **claiming** the ticket before any real work, because several instances of a phase may run concurrently. Discovery, and Spec's own
no-ticket entry, have no ticket to claim: the moment they create one (`status:draft`) they assign it the same way, and that assignment sticks if the pair session ends before
final approval, like a claimed ticket left mid-phase (see "Resuming an orphaned claim").

The mechanics are `.pilot/pilot.py claim <phase> <issue> --mode ...` (`pool` and `resolve` decide what to claim); its source is the reference for the exact conditions. The contract:

- A ticket is claimable only in the phase's pre-claim `status:` and unassigned — or, for the explicit modes below (resume, reclaim, re-scope), in the status that mode names.
  Anything else is refused, never overwritten silently.
- A claim sets the assignee to the current session's GitHub user and swaps `status:` to the phase's in-progress one in one write, then re-reads the ticket. If the assignee is no
  longer this session, another run won the race — stand down and pick something else. Optimistic, not a real lock.
- The phase's real work (the subagent call(s)) starts only after a successful claim.

Phase 4's claim only serializes separate *runs* of `/pilot-review` on a ticket; the reviewers **within** one claimed run still execute independently in parallel, never seeing each
other's verdict (`.pilot/pilot-link-review-consensus.md`).

### Picking the next ticket when none is specified

Discovery has no pool (it starts from a raw idea or `--resume`). Every other phase builds its pool with `.pilot/pilot.py pool <phase>` (its source is the reference): fresh work (the phase's
pre-claim `status:`, unassigned), resumable work (its in-progress `status:` with `can-resume`) and, for `/pilot-dev`, reclaimable work (`status:changes-requested` without
`needs-human`/`on-hold`). A ticket carrying `needs-human` or `on-hold`, or with an unresolved "Depends on #N", is never a candidate; an orphaned claim (in-progress, assigned, no
`can-resume`) is never in a bare pool and resumes only via `can-resume` or an explicit `--resume`. Order: highest `priority:` first (none sorts last), then a ticket with a "Blocks #M"
comment on a still-open #M, then oldest.

### Blocked-by dependencies (mechanical gate, distinct from `on-hold`)

A ticket's body may carry "Depends on #N" references, written by the architect for a prerequisite (`.pilot/pilot-link-split-tickets.md` "Prerequisite tech/bug tickets") and by
`pilot-dev`/`pilot-e2e`/`pilot-qa` for a bug found inline; anything that writes the phrase gets the gate. **One dependency per line, always**, one issue number each, never several on a
line: the check is a per-line literal match.

The gate is `.pilot/pilot.py`'s, never a subagent's reasoning: a ticket with a dependency still open (plain open/closed, not its `status:`; an unreadable reference counts as open) is
excluded from every pool and refused when given explicitly in Dev and QA. Spec is the exception: re-splitting or re-speccing needs no prerequisite resolved. Nothing is removed by hand — the
ticket is a candidate again the moment the referenced one closes.

### Resuming a `needs-human` ticket

A human resolves the flag by removing the label (optionally after a reply): that removal is the entire signal, from any session at any time. Whether the ticket also carries `can-resume`
decides if it is a bare-sweep candidate or only reachable by number. A ticket already in the phase's in-progress `status:` is **resuming**, not a fresh claim (`pilot.py claim --mode
resume-cleared` only consumes the one-time `can-resume`):
1. Read the full blocking context: the blocking comment and everything after it (for Review, the submitted PR review, `.pilot/pilot-link-review-consensus.md`, plus the PR's comments after it).
2. `needs-human` still present → not resolved: report and stop (matters only when a number was given; the bare pool excludes these).
3. Otherwise run the phase's `Agent` call(s) with the original blocking context and what followed it (a reply, or "no reply — treat as approved as proposed"); they proceed, correct, or block again.

### Resuming an orphaned claim (`--resume`, or `can-resume`)

Distinct from resuming a `needs-human` ticket and from reclaiming a `status:changes-requested` one: a ticket still carrying its original assignee, in the phase's in-progress `status:`
(`draft`, `in-spec`, `in-dev`, `in-review`, `in-qa`), with **no** `needs-human`. A pair session that ended before final approval, or an `--auto` run that died mid-work, leaves this same shape,
which the plain "has an assignee → stop" check would read as someone actively working. For Discovery and Spec's no-ticket entry, `status:draft` is what makes this possible.

Only a human verifying it firsthand can tell it is dead. They resume it now with an **explicit** `--resume <issue>` (never in a bare pool) or add `can-resume` to hand it to the next sweep. To
resume via `--resume`:
1. Read the full ticket (body and comments), which rebuilds pair mode's checkpoints. `/pilot-review`'s checkpoint is a pending PR review (`pilot-review/SKILL.md`): pinned to the PR's current head
   → the recovered outcome; stale or absent → discard it and restart the reviewers fresh. An `--auto` run of another phase has nothing to rebuild: restart from the ticket's original inputs.
2. `pilot.py claim --mode resume-orphaned` — an existing assignee is no conflict: it is overwritten, `status:` stays.
3. Pass what step 1 recovered to the phase's `Agent` call(s) and continue (the pair loop where one exists, else a fresh pass). Finalization is as in any run.

### Interaction modes: pair and `--auto`

Each phase's own `SKILL.md` follows this contract and may specialize it. Discovery and QA are **pair only** (no `--auto`, never driven by a scheduled Routine; both support `--resume`). Spec, Dev and
Review take `--auto` or `--pair` when given, else the ticket's `mode` from `python3 .pilot/pilot.py workflow show --ticket <N>` (`pair` unless the project's workflow defaults to `auto`;
a project with no `workflow` block is pair). A ticket a risk signal makes pair only is never run unattended: an unattended run passes `--auto` to `pilot.py pool`/`resolve`/`claim`,
which leave it out or refuse it. `--auto` is what a scheduled Routine uses (`.claude/skills/pilot-auto/SKILL.md` "Scheduled sweeps"). Review specializes pair: its reviewers always
run in parallel and isolated, so an outcome carrying `needs-human` submits at once in both modes (the block must reach GitHub before any resolution) and a live human resolves it afterwards
("A human is live in the same session", `needs-human` above), while an all-approve or pure-`change` outcome pauses before submitting for a last look (`pilot-review/SKILL.md`). Both modes claim immediately, the same way.

**Pair** needs a human live in the session. The agent(s) stop at the phase's natural checkpoint(s) — the drafted story, the proposed split and spec, the implementation plan — and the skill relays to
the human, feeds back their reply and repeats until they approve. **The skill writes progress into the ticket at every checkpoint** (typically one comment kept up to date, or a partial `issue_write`), so
the ticket is the durable record that makes `--resume` possible; what stays of that comment at finalization is each phase's own call. Where no ticket exists yet at the first checkpoint (Discovery, and
Spec's no-ticket entry) the skill first runs a framing stage — the PM alone in Discovery, the architect alone in Spec — until the human validates a brief, then creates the ticket (`status:draft`) as soon
as the first draft can be shown; there is nothing to `--resume` during framing. The last thing pair does, setting the phase's completion `status:`, is the end-state `--auto` reaches in one pass.

**Final consolidation, right before the completion `status:`**, for every phase with incremental checkpoints: once the human approves, re-read the whole ticket body (the full diff for Dev) as it now
stands and fix anything incoherent, since a decision from an early round may no longer square with a later one. It is `pilot-dev`'s self-review before opening the PR, a substitute for a second pass in
Review, not an addition. Review has no incremental assembly: each reviewer re-checks its own points once before returning (`.pilot/pilot-link-review-consensus.md`).

**`--auto`** has the agent(s) decide everything and the skill apply the result in one pass, no checkpoint. `--auto`, `--resume` and pair are mutually exclusive — pick one per run. `--with
<persona>[,...]` (`.pilot/pilot-link-roster.md` "Roster") is orthogonal to all of them; `--merge` (Review only, "`status:approved`") only controls whether an all-approve outcome also merges the
PR, with either mode; `--multi <N>` (Discovery, Spec, Dev, Review; `.pilot/pilot-link-agent-dialogue.md`, `.pilot/pilot-link-multi-consensus.md`) runs an ensemble on the one claimed ticket, with either
mode, and is invalid only with `--resume`.

Unrelated to the "ask live" behavior of `needs-human`: that fires for a genuine blocker, pair or not; pair is for iterating on a draft together even when nothing blocks.

## 5. Token Efficiency: Isolated Contexts Per Phase

1. **No phase carries a prior phase's transcript.** A phase skill reads only what it needs from the ticket (its body, linked parent and children, the relevant docs) and hands that, never the
   pipeline's history, to a fresh `Agent` call with the matching persona. The isolation is across phases (and, in Review, between reviewers), not within one: a dialogue is several `Agent` calls,
   one per turn, each re-reading what it needs and receiving the conversation as explicit text, so a longer dialogue costs more, turn for turn.
2. **Claim/label bookkeeping is deterministic tool calls in the skill** (`.pilot/pilot.py`), not agent reasoning; only the thinking — the story, the split and spec, the code, the review — goes through
   an `Agent` call.

A human driving several phases back to back for one ticket passes forward only the ticket number.

---

## 8. Optional modules

A project turns an optional module on in `.pilot/state.json` (`"modules": {"wiki": true, …}`; `python3 .pilot/pilot.py module list|enable|disable`; a module may require another: `enable` refuses until
it is on, `--with-requires` turns both on). A module that is off, or absent from the file, changes nothing: every step that names it is skipped. A module's own skill proposes turning it on at first use,
and with it on `doctor` also requires its folder. The modules: `wiki` (`wiki/`, what the product does: `.pilot/pilot-link-wiki.md`), `architecture` (`architecture/`, how it is built and why:
`.pilot/pilot-link-architecture.md`), `dashboard` (the team page; its tabs follow the modules on), `design` and `proto` (the design system and the prototypes, which need `dashboard`). `wiki` and
`architecture` are read by every agent the same way (`.pilot/pilot-link-knowledge.md`) and only a PR changes either. **When the wiki and the code disagree, the wiki is right**, and a divergence is a human's
call, never settled silently.
