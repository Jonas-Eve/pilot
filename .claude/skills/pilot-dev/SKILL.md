---
name: pilot-dev
description: "Phase 3 of PILOT: implements a spec'd ticket (status:dev-ready) with pilot-dev (pilot-e2e for a type:e2e task) and opens a PR, or flags needs-human and stops if genuinely blocked. Pair by default, or the project workflow's default (agrees the approach with a live human before coding), --auto or --pair to choose, --auto for a Routine. --resume continues a flagged or mid-pair ticket; it also reclaims a status:changes-requested ticket by pushing to its existing PR; --with, --multi (N devs converge on an approach); bare, it sweeps fresh, resumable and reclaimable work. Use once /pilot-spec has produced a spec."
argument-hint: "<issue number, optional — picks the next dev-ready or can-resume-marked ticket if omitted> [--auto|--pair] [--with <persona>[,...]] [--multi [N]] | <issue number> --resume"
---

# PILOT — Phase 3: Dev

Read `.pilot/pilot-process.md` first — source of truth for labels, states, and the claim
protocol; this skill covers only phase 3's mechanics. Most likely phase to run as several
parallel instances; the claim step below prevents collisions. The roster (`.pilot/pilot-link-roster.md`
"Roster"): the dev (`pilot-e2e` for a `type:e2e` task) leads, no validator; the tech lead,
architect and designer are summonable. Summons and dismissals are recorded in the ticket's
checkpoint comment; `.pilot/pilot-task-advise.md` is passed into a summoned persona's call.

## Steps

0. **Preflight**, once per session: `python3 .pilot/pilot.py doctor` — skip it if it already reported `ok: true` earlier in this conversation. `ok: false` (exit 1) or a failure (exit 2, script missing) → report each entry of `failed` (or the error) and stop here, before anything has changed.
1. Resolve the ticket: `python3 .pilot/pilot.py resolve dev <issue> [--resume] [--auto]` (`--auto` on `pool`, `resolve` and `claim` whenever this run is unattended, `.pilot/pilot-process.md` §4 "Interaction modes"). With no issue
   given, run `python3 .pilot/pilot.py pool dev [--auto]` first — the pool of `.pilot/pilot-process.md`
   §4 "Picking the next ticket..." (fresh `status:dev-ready`, resumable `can-resume`,
   reclaimable `status:changes-requested`; `needs-human`, `on-hold` and open "Depends on #N"
   excluded; priority, then "Blocks #M", then oldest; a scheduled cron Routine drives this
   with `--auto` added, `.claude/skills/pilot-auto/SKILL.md` "Scheduled sweeps"). `pick: null` → report nothing to do;
   otherwise the pool has already resolved its pick: act on `pick.action`:
   - `claim-fresh` → step 2 (mode `fresh`).
   - `reclaim` → step 2 (mode `reclaim`): a PR already exists, phase 4 sent it back
     (`.pilot/pilot-link-review-consensus.md` "Reclaiming a `status:changes-requested` ticket"). Then
     skip straight to step 3, passing the phase-4 blocking review instead of a fresh spec.
   - `resume-orphaned` (`--resume`: a ticket left mid-pair session) → step 2 (mode
     `resume-orphaned`), then step 3 invoked with the recovered context as input
     (`.pilot/pilot-process.md` §4 "Resuming an orphaned claim").
   - `resume-cleared` (`can-resume`: a human cleared `needs-human`) → step 2 (mode
     `resume-cleared`), then step 3 invoked with the original blocking context as input
     (`.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket").
   - `ask-resume` → likely mid-pair-session; report and ask the human to re-run with
     `--resume`, or add `can-resume` themselves.
   - `descend` → the number was an Epic or a `status:split` story: `pick` is this phase's own
     bare-pool pick across its open sub-issue tree (`.pilot/pilot-link-epic-descent.md`);
     resolve `pick.number` the same way. `pick: null` → report nothing to do for this ticket.
   - `stop` → report `reason` and stop: `depends-on-open` (name the `depends_on` ticket),
     `flagged` (`flags`: `needs-human`/`on-hold`, unresolved), `assigned`, `wrong-status`,
     `in-progress-unassigned`, `closed`, `not-found`.
   Script missing or exiting 2 → report that and stop: `.pilot/pilot.py` ships with
   `/pilot-init`/`/pilot-update` and needs `python3` and a working `gh`.
2. **Claim** it: `python3 .pilot/pilot.py claim dev <issue> --mode <mode> [--auto]` (the mode named in
   step 1: `fresh`, `reclaim`, `resume-orphaned` or `resume-cleared`) — it applies
   `.pilot/pilot-process.md` §4 "Claim Protocol" (assignee + `status:in-dev`, re-read to
   confirm). Exit 1 with `reason: lost-race` → another instance won; stand down and return
   to step 1 for a different ticket. Any other refusal → report `reason` and stop.
2a. **Pick the persona**: ticket's own `type:e2e` (`.pilot/pilot-link-e2e-tasks.md` — never
    inherited, read off the ticket, not its story) →
    `subagent_type: "pilot-e2e"`; otherwise `"pilot-dev"`. The only thing `type:e2e`
    changes here — claim, pool selection, and everything below apply identically either
    way.
2b. **Dashboard** (best-effort): per `.pilot/pilot-link-dashboard.md`, push the `event`/`activity` that `pilot.py claim|set|flag|unflag` return, with `ArtifactData` (`ToolSearch` loads it if deferred) — skipped silently when `dashboardUrl` is absent from `.pilot/state.json`.
3. Call the `Agent` tool with the `subagent_type` chosen in step 2a. Read
   `.pilot/pilot-task-implement.md` and pass its content as part of the prompt — for
   `pilot-e2e`, also read and pass `.pilot/pilot-task-implement-e2e.md` alongside it, since
   it only documents that persona's differences from the base task. Also pass
   `.pilot/pilot-link-bug-tickets.md` in full — either persona may hit step 3a's bug case
   mid-implementation, and the task doc covers only the phase-3-specific delta itself, not
   the classify/originate mechanic. Pass the ticket's
   spec and the architect's decisions, including any UI/UX description carried into it
   (`.pilot/pilot-task-scope-story.md`) — not the running conversation history or the state
   of any other ticket being worked in parallel. **Resume case** (per step 1, needs-human
   cleared): also pass the original blocking comment and whatever's in the thread after it
   (`.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket"). **Reclaim case** (per
   step 1): pass the phase-5 blocking review — its submitted PR review, fetched via
   `mcp__github__pull_request_read` method `get_reviews` (the body holds the points, not a
   plain issue comment, `.pilot/pilot-link-review-consensus.md`) — with its `change`-tagged
   points to fix, plus any `decision`-tagged points and their resolution, instead of a
   fresh spec — only more commits on the existing PR. When a knowledge module is enabled (`.pilot/pilot-process.md` §8), also pass
   `.pilot/pilot-link-knowledge.md` in full and, per module on, `.pilot/pilot-link-wiki.md` / `.pilot/pilot-link-architecture.md` in full;
   with `wiki` on, the ticket's entries (`python3 .pilot/pilot.py wiki index --ticket <issue>`, each with `wiki show <id>`). The dev
   reads the rest itself, following the guidelines that bear on the ticket.
   - **Without `--multi`** (or on a reclaim, where `--multi` has no effect either way):
     **unless `--auto` was given** (`.pilot/pilot-process.md` §4 "Interaction modes" — pair
     is the default; a fresh claim or paused-pair resume only, never combined with a
     reclaim): first ask for a proposed implementation approach, not the finished
     implementation — the pair-coding checkpoint. Show the human that plan as a normal
     reply, wait for their response, feed it back to the agent, repeat until approved,
     keeping one scratch comment on the ticket updated in place
     (`mcp__github__update_issue_comment` — create it once, edit it each round) rather than
     holding it in-conversation or posting a new comment per round — this is what
     `--resume` picks back up if the session ends before final approval
     (`.pilot/pilot-process.md` §4 "Resuming an orphaned claim"). Requires a human live in
     this session; a scheduled Routine must pass `--auto` instead. Once approved, the same
     `Agent` call proceeds with implementation below — the "ask live" behavior for a
     genuine blocker (§3) still applies during implementation itself; pair mode doesn't
     replace it. **`--auto`**, with neither pair nor `--multi` in play, skips straight to
     implementation in this one call (no scratch comment ever created).
   - **With `--multi <N>`** (a fresh claim, or a resume via `can-resume` per step 1 —
     never a reclaim, never the literal `--resume` flag): N instances, **each asked
     for a proposed implementation approach only, not the finished implementation** — same
     content as the pair-coding checkpoint above, never code — discuss the tradeoffs
     directly with each other instead of proposing in isolation (`.pilot/pilot-link-agent-dialogue.md`
     has the turn-taking mechanics and the escalation criteria — including what happens if
     a human is live in this pair session when they can't converge): no fixed number of
     turns, the instances themselves judge when they've converged on one approach, and
     escalate `needs-human` (quoting the differing positions verbatim) only once a
     disagreement looks genuinely irreconcilable — nothing was implemented yet, so nothing
     to push or clean up either way. Once an approach is settled (reached by convergence,
     or by a live human resolving the escalation), **unless `--auto`**,
     show it to the human as the normal pair-coding checkpoint above (repeat until
     approved, same checkpoint discipline, same single edited scratch comment) — then,
     whether via pair approval or `--auto`
     straight through, make
     **one further, single** `Agent` call (never N again — the ensemble's job ends at the
     approach) with that approach as its explicit plan, to actually implement it.
4. The subagent either implements the ticket, runs the relevant validation, and opens a
   pull request following this project's own PR template if it has one (e.g.
   `.github/pull_request_template.md`) — including a "PILOT ticket" section if the
   template defines one: type, `Closes #<issue>`, spec deviations — or, for a reclaim,
   pushes new commits addressing the blocking review to that same existing PR instead of
   opening a new one — or hits a genuine blocking conflict it can't resolve alone and
   stops without a PR (or without pushing, for a reclaim).
5. Apply the result:
   - PR opened, or new commits pushed to an existing PR (reclaim case): `python3
     .pilot/pilot.py set <issue> --status review-ready --unassign --pr <PR number>` (phase 4's
     own pre-claim status — never `status:in-review` directly, `.pilot/pilot-process.md` §4
     "Claim Protocol"; `--pr` puts the PR's link in the event the dashboard shows). If step
     3 left a scratch approach-checkpoint comment, collapse it to one concise line (e.g.
     "Approach: <one-line summary> — see PR #<n>") — the PR itself is the real artifact
     now, not the negotiation that led to it.
   - Blocking conflict: nothing further to set — the subagent already added
     `needs-human` and posted its comment itself (`status:in-dev` stays, per
     `.pilot/pilot-process.md` §3).
   - Bug discovered mid-implementation (`.pilot/pilot-link-split-tickets.md` "Prerequisite tech/bug tickets"): nothing further to set — the subagent
     (`pilot-dev` or `pilot-e2e`) already originated the new `type:bug` ticket, linked it
     ("Blocks #M"/"Depends on #N"), pushed its WIP to a branch with a comment naming it,
     cleared the assignee, and moved the ticket back to `status:dev-ready` itself. It's
     now an ordinary `status:dev-ready` candidate again, gated only by the dependency
     (step 1's "Depends on #N" bullet) — no flag to clear, no `--resume` needed;
     whichever future run claims it picks up that branch per step 1's own claim-time
     check (`.pilot/pilot-task-implement.md` step 1).
6. Report the PR URL, or the blocking summary, back to the human. Never merge as part of
   this skill.
