---
name: pilot-review
description: "Phase 4 of PILOT: claims a status:review-ready PR and runs the reviewers in parallel (PM and tech lead for type:feature/type:e2e, tech lead alone for type:tech/type:bug, the architect optional), then submits one GitHub PR review (Approve, Request changes or Comment) and the matching label: status:approved, or status:changes-requested (a pure code-level verdict never sets needs-human, so it is reclaimable at once; a judgment call adds it). Pair by default (a live human gets a last look and can resolve a needs-human block live), --auto for a Routine; --merge merges an all-approve PR; --with architect, --only <roles>, --multi, --resume; bare, it sweeps ready PRs. Use for a status:review-ready PR."
argument-hint: "<PR number, or issue number, optional — sweeps ready PRs if omitted> [--auto] [--merge] [--with architect] [--multi [N]] | <issue or PR number> --only <pm|architect|techlead>[,...] [--merge] | <issue number> --resume [--merge]"
---

# PILOT — Phase 4: Review

Read `.pilot/pilot-process.md` first (labels, states, the claim protocol §4) and `.pilot/pilot-link-review-consensus.md` (the `change`/`decision` tags contract); this
skill covers only phase 4's mechanics, including the reviewer set (step 3). `--with architect` adds the architect to that set, in a sweep too (the only persona
summonable here, `.pilot/pilot-link-roster.md` "Roster"); `--only` (step 3) fixes the exact set instead; nothing can be summoned mid-review.

Mode: pair by default (`.pilot/pilot-process.md` §4 "Interaction modes"). Every outcome is checkpointed as a pending GitHub PR review the moment it is decided
(step 7). An all-approve or pure-`change` outcome (no `decision` point, so no `needs-human`) gets a pre-submission pause (step 8); an outcome carrying
`needs-human` always submits at once (step 9) and pair's value comes after, in the live resolution of step 10. `--auto` skips both pauses (required for a scheduled
Routine, `.claude/skills/pilot-auto/SKILL.md` "Scheduled sweeps"). `--merge` (step 12) works with either mode; without it this skill never merges. `--multi <N>`
runs N instances of each role selected in step 3 (roles × N simultaneous `Agent` calls), reconciled per role before step 6's aggregation
(`.pilot/pilot-link-multi-consensus.md`); invalid with `--resume`. `--only <list>` is valid only with an explicit PR/issue number, never a sweep and never with
`--auto`: dropping a role is a human's call, so step 8's pause always stays as the last check.

## Steps

0. **Preflight**, once per session: `python3 .pilot/pilot.py doctor` — skip it if it already reported `ok: true` earlier in this conversation. `ok: false` (exit 1) or a failure (exit 2, script missing) → report each entry of `failed` (or the error) and stop here, before anything has changed.
1. Resolve the ticket: `python3 .pilot/pilot.py resolve review <issue> [--resume]`. With none
   given, run `python3 .pilot/pilot.py pool review` first — the pool of
   `.pilot/pilot-process.md` §4 "Picking the next ticket..." (fresh `status:review-ready`,
   resumable `status:in-review` + `can-resume`; `needs-human`, `on-hold` and open "Depends on
   #N" excluded; priority, then "Blocks #M", then oldest; `status:changes-requested` tickets
   are never in it: a reclaim is another phase's pool, §4). `pick: null` → report nothing to do;
   otherwise resolve `pick.number` the same way. Act on the returned `action`:
   - `manual` (`reason: pr-number`: a PR number was given) → find the ticket it closes
     (`mcp__github__pull_request_read`, its `Closes #N`) and resolve that ticket here instead.
   - `claim-fresh` → step 2 (mode `fresh`).
   - `resume-orphaned` (`--resume`) → step 2 (mode `resume-orphaned`;
     `.pilot/pilot-process.md` §4 "Resuming an orphaned claim"), then check for an existing
     pending review under this run's own identity (`mcp__github__pull_request_read` method
     `get_reviews`): still pinned to the PR's current head commit → skip straight to step 8
     with its already-computed outcome (step 8 itself routes on/around the pair pause
     exactly as it would for a fresh run) — no need to re-run reviewers. Stale (commit no
     longer matches) or none found → discard any stale one
     (`mcp__github__pull_request_review_write` method `delete_pending`) and resume normally
     from step 3.
   - `resume-cleared` (`can-resume`) → step 2 (mode `resume-cleared`;
     `.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket"), then continue from
     step 3.
   - `ask-resume` → looks orphaned; report and ask the human to re-run with `--resume`, or
     add `can-resume` themselves.
   - `descend` → the number was an Epic or a `status:split` story: `pick` is this phase's own
     bare-pool pick across its open sub-issue tree (`.pilot/pilot-link-epic-descent.md`);
     resolve `pick.number` the same way. `pick: null` → report nothing to do for this ticket.
   - `stop` → report `reason` and stop (`flagged`: unresolved `needs-human`/`on-hold`;
     `resume-mismatch`; `wrong-status`; `assigned`; `closed`; `not-found`).
   Script missing or exiting 2 → report that and stop: `.pilot/pilot.py` ships with
   `/pilot-init`/`/pilot-update` and needs `python3` and a working `gh`.
2. **Claim** it: `python3 .pilot/pilot.py claim review <issue> --mode <mode>` (the mode named
   in step 1) — it applies `.pilot/pilot-process.md` §4 "Claim Protocol" (assignee +
   `status:in-review`, re-read to confirm). Exit 1 with `reason: lost-race` → stand down and
   return to step 1 for a different candidate (bare pool only — report nothing to do if a
   specific ticket was requested). Any other refusal → report `reason` and stop.
2a. **Dashboard** (best-effort): per `.pilot/pilot-link-dashboard.md`, push the `event`/`activity` that `pilot.py claim|set|flag|unflag` return, with `ArtifactData` (`ToolSearch` loads it if deferred) — skipped silently when `dashboardUrl` is absent from `.pilot/state.json`.
3. Read the ticket's linked issue and **its own** `type:` label (never a parent's, `.pilot/pilot-link-ticket-tree.md` "`type:` is never inherited") to pick the **default**
   reviewer set; the architect is never part of a default: it is `rules.review[<type>]` of `python3 .pilot/pilot.py workflow show` (once per run):
   - standard: `type:feature` or `type:e2e` → `pilot-pm`, `pilot-techlead`; `type:tech` or `type:bug` → `pilot-techlead` alone (no PM)
   - a lean workflow: `pilot-techlead` alone for every type
   - Whatever the flags, check whether the PR already carries a submitted review (`mcp__github__pull_request_read` method `get_reviews`) — true after a reclaim fix
     (`.pilot/pilot-link-review-consensus.md` "Reclaiming a `status:changes-requested` ticket"), never for a first round. Found → fetch the latest submitted review's full body
     (every point, marked `change` or `decision`) to pass to every reviewer in step 5. This also feeds `--only`.
   - `--with architect` → the default set plus the architect: never narrows (no prior-review check), valid on any `type:`, in a sweep too, never with `--only`.
   - `--only <list>` (explicit number only) → `<list>` is the **complete, exact** set, never merged with the default (`--only architect` means only the architect; to add the
     architect to the defaults use `--with architect`). `architect` is always legal on any `type:`. Any other name must already be in the ticket's own default (never `pm` on
     `type:tech`/`type:bug` — refuse). If `<list>` **narrows** the default (drops a role it would include; adding `architect` never counts), it needs a prior submitted review:
     none → refuse and report, the full default must run at least once first.

   Together the default set covers every dimension: PM — product fit / e2e-flow validation; tech lead — spec conformance and code quality. The architect already
   cross-examined the split and the spec at Spec time, so its phase-4 pass is worth adding only when the diff raises a fresh architecture/security question the tech lead's
   own check does not settle. All selected reviewers run **in parallel, fully independent** — none sees another's verdict — in pair and `--auto`; nothing later reopens that
   isolation.
4. Once this project has a CI workflow covering the affected area, check it's green on the
   PR's head commit before proceeding — red/pending CI is an automatic `change`-tagged
   block (step 6). Until then, this is a no-op and the tech lead's own re-run in step 5 is
   the only safety net.
5. Call the `Agent` tool once per reviewer — or, with `--multi <N>`, N times per
   reviewer role — **in parallel** (every role's every instance launched together,
   `subagent_type` set to that persona per step 3's independence guarantee). Pass every
   reviewer
   `.pilot/pilot-link-review-consensus.md` in full — the shared verdict format and tagging
   rule, identical for all three, one canonical statement instead of restated per persona
   — plus the matching task doc for what's specific to that persona:
   `.pilot/pilot-task-review-product-fit.md` (PM),
   `.pilot/pilot-task-review-architecture.md` (architect),
   `.pilot/pilot-task-review-spec-conformance.md` (tech lead) — the persona file itself
   (`.claude/agents/pilot-*.md`) carries only identity now, these two together are what
   tell each reviewer what to check and how to report it. Pass only
   what each needs beyond that: the PR diff/description plus, for the PM, the linked
   story's acceptance criteria and any UI/UX description or attached mockup (and its own
   spec, for `type:e2e`); for the architect, its recorded decisions; for the tech lead,
   its own spec (it re-runs validation on the PR branch itself). When a knowledge module is enabled (`.pilot/pilot-process.md` §8), also pass every reviewer
   `.pilot/pilot-link-knowledge.md` in full and, per module on, `.pilot/pilot-link-wiki.md` / `.pilot/pilot-link-architecture.md` in full, plus the PR's
   changes under `wiki/` and `architecture/` (`mcp__github__pull_request_read` `get_files`); with `wiki` on, the entries of the ticket under
   review — and, for a `type:e2e` task, of its parent story — (`python3 .pilot/pilot.py wiki index --ticket <n>`, each with `wiki show <id>`). When step 3 found a prior
   submitted review on this PR — whether reached via step 1's needs-human-resume branch or
   an ordinary reclaim after a pure-`change` fix — also pass its full body (every point,
   change and decision alike, marked which is which) to every reviewer this round, plus,
   if present: whatever's in the PR's comment thread after it — a specific reply resolving
   a `decision` point, or "no reply — treat as approved as proposed" if none
   (`.pilot/pilot-process.md` §4 "Resuming a `needs-human` ticket") — and the dev's own
   reclaim summary comment on the ticket's *issue* (not the PR,
   `.pilot/pilot-link-review-consensus.md` "Reclaiming a `status:changes-requested` ticket").
   `.pilot/pilot-link-review-consensus.md` has how each reviewer is expected to use this
   instead of starting blind.
5a. **Per-role reconciliation** (only when `--multi` ran more than one instance of a
    role): for each such role, reconcile its N verdicts yourself — no further `Agent`
    call — into that role's single point-list per `.pilot/pilot-link-multi-consensus.md`
    — a point only some instances raised is
    coverage, union it in; only two instances reaching opposite judgments about the
    identical point is genuine disagreement, retried once (that role's N instances again,
    that point in context) — still unresolved after that retry → turn it
    into one `decision`-tagged
    point in that role's own list, quoting every differing position verbatim, and let
    step 6's ordinary tag-based aggregation carry it from there (`needs-human` follows
    automatically, same as any other `decision` point — no separate escalation path).
    Continue to step 6 with each ensembled role's single reconciled point-list; a role
    that didn't run as an ensemble passes its one verdict through unchanged.
6. Collect the verdicts. Aggregate into exactly **one** outcome
   (`.pilot/pilot-link-review-consensus.md`):
   - All blocking points tagged `decision`, none `change` → every point, grouped by
     reviewer, `needs-human` added (`status:in-review` stays — this ticket re-enters the
     resumable half of step 1's pool once cleared, unless step 10 resolves it live first).
   - At least one blocking point tagged `change` (a step-4 CI/validation failure always
     counts) and at least one tagged `decision` → every point (marked which is which),
     `needs-human` added, move to `status:changes-requested` (reclaimable once
     cleared — the `decision` point(s) are what it's waiting on).
   - At least one blocking point tagged `change`, none tagged `decision` → every point,
     move to `status:changes-requested`, **no** `needs-human` — nothing here needs a
     human, so it is reclaimable at once.
   - All approved → move to `status:approved`.
7. **Checkpoint it**: create a pending GitHub PR review with the outcome's full body
   already written, no `event` yet (`mcp__github__pull_request_review_write`, method
   `create`, `commitID` pinned to the PR's current head) — durable immediately, so an
   orphaned run recovers it (step 1) instead of redoing steps 3-6.
8. **Pair (default) vs `--auto`** — never for an outcome that carries `needs-human` (`.pilot/pilot-process.md` §3: the block must reach GitHub before any resolution, even a live
   one): it goes straight to step 9. For the all-approve or a pure-`change` outcome pair pauses here for a last look — show the outcome from step 6, wait for confirmation,
   then step 9. `--auto` never pauses.
9. Submit step 7's pending review (`mcp__github__pull_request_review_write`, method `submit_pending`) plus the matching label:
   - All approved → `event: APPROVE`; the body names which role(s) approved this round (all of step 3's set — say so explicitly if `--only` narrowed it) and, per step 12,
     whether this run merges or a human still must; `status:approved`.
   - `change` points, no `decision` → `event: REQUEST_CHANGES`; every point; **no** `needs-human`; `status:changes-requested`.
   - Both tags → `event: REQUEST_CHANGES`; every point, marked; `needs-human` added; `status:changes-requested`.
   - Only `decision` points → `event: COMMENT`; every point grouped by reviewer; `needs-human` added; `status:in-review` stays.

   Apply the label with `python3 .pilot/pilot.py set <issue> --status approved --unassign` or `--status changes-requested --unassign` (the verdict ends this run's claim),
   adding `--add needs-human` where the bullet says so (the decision-only bullet keeps `status:in-review` and the assignee: `--add needs-human` alone).

   If GitHub rejects an `APPROVE`/`REQUEST_CHANGES` because this run's identity is the PR's own author, retry `submit_pending` on that same pending review (never a second
   `create`) with `event: COMMENT`, still applying that bullet's label and `status:`.
10. **Live resolution of a submitted `needs-human` block** (pair only, right after step 9; the decision-only and the mixed outcomes, never the pure-`change` one): engage the
    human as `.pilot/pilot-process.md` §3 "A human is live in the same session" says. If their answer changes the outcome (approved, or only the remaining `change` points),
    submit **one more** review — a fresh `create` with `event` set, same mapping as step 9, plus the matching label; if GitHub rejects it for the same reason, a fresh `create`
    with `event: COMMENT` is the retry. Never fold it into step 9's review. If the answer does not clear the block, or `--auto`, or nobody answers: leave step 9's review and
    `needs-human` standing for a later run.
11. Never more than two reviews per PR (step 9's, plus step 10's correction), never one per reviewer or per `--multi` instance: step 5a reconciles each role to one point-list
    before step 6.
12. **Merge, only with `--merge`:** if the final outcome (step 9, or step 10's correction) is
    `status:approved` and `--merge` was passed, merge the PR now
    (`mcp__github__merge_pull_request`, the repository's normal merge method). Without
    `--merge`, or on any other outcome, never merge — a human merges by hand, same as
    before.
13. Report the outcome, including whether this run merged the PR itself. Once a PR is
    merged (by a human, or by step 12), `.github/workflows/pilot-status-on-merge.yml` sets
    `status:done` and runs the cascading-completion check (`.pilot/pilot-process.md` §3)
    — this skill's own job ends at the submitted review(s) (plus, when `--merge` applied,
    the merge itself).
