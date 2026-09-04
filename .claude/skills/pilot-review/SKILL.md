---
name: pilot-review
description: "Phase 5 of PILOT (see docs/pilot-process.md): claims a status:review-ready PR (assignee + status:in-review, docs/pilot-process.md §4 'Claim Protocol'), then runs the review agents (PM+architect+tech lead for type:feature/type:e2e, architect+tech lead only for type:tech/type:bug) in parallel, and submits a GitHub PR review (Approve/Request changes/Comment, matching the verdict) plus the matching label — status:approved; a pure code-level verdict moves straight to status:changes-requested with no needs-human, so /pilot-dev can reclaim it immediately; a verdict blocking on any judgment call (alone or alongside code-level points) adds needs-human too (status:in-review stays for a pure judgment call, status:changes-requested for a mixed one), gating /pilot-dev's reclaim on a human clearing it. Defaults to pair mode: an all-approve or pure-code-level verdict gets a live human's last look before it's submitted; a verdict carrying any judgment call always submits first (the block must reach GitHub before any resolution, even a live one), then a live human can resolve it right there, submitting one corrected follow-up review. --auto skips every pause, applying each verdict straight through (required for a scheduled cron Routine). --merge, combinable with either mode, merges the PR itself once the final verdict is all-approve — omitted, a human always merges by hand, same as before. Also resumes a ticket once a prior needs-human flag is cleared, recovers a claim orphaned by a crashed run via --resume <issue>, and with no argument sweeps every ready/resumable PR (e.g. --auto from a scheduled cron Routine), skipping any on-hold. Use once /pilot-dev has opened a PR ready for review."
argument-hint: "<PR number, or issue number, optional — sweeps ready PRs if omitted> [--auto] [--merge] | <issue number> --resume [--merge]"
---

# PILOT — Phase 5: Test & Validate

Read `docs/pilot-process.md` first — source of truth for labels, states, and the claim
protocol (§4) — and `docs/pilot-link-review-consensus.md` for the shared `change`/`decision`
tags contract; this skill covers only phase 5's mechanics, including how it picks the
reviewer set (step 3).

Mode: pair by default. Every outcome is checkpointed as a pending GitHub PR review the
moment it's decided (step 7), the same durable-immediately discipline every other
pair-capable phase applies to its own ticket writes. For an all-approve or a pure-`change`
outcome (no `decision` point at all — nothing here needs a human, so no `needs-human`
either), step 8 is then a pre-submission checkpoint; for an outcome carrying `needs-human`
(decision-only, or mixed `change`+`decision`), that outcome always submits immediately
(step 9) and pair's value comes after, in step 10's live resolution. `--auto` skips step
8's pause and step 10's live engagement, applying every outcome straight through (required
for a scheduled Routine, `docs/pilot-process.md` §4 "Scheduled sweeps"). `--merge` is a
separate, orthogonal flag (step 12) usable with either mode — without it, this skill never
merges.

## Steps

1. Resolve the ticket:
   - Given `--resume`: must be `status:in-review`, assigned, no `needs-human`/`on-hold`.
     Follow `docs/pilot-process.md` §4 "Resuming an orphaned claim" instead of step 2 below
     — already claimed. Check for an existing pending review under this run's own identity
     (`mcp__github__pull_request_read` method `get_reviews`): still pinned to the PR's
     current head commit → skip straight to step 8 with its already-computed outcome
     (step 8 itself routes on/around the pair pause exactly as it would for a fresh run) —
     no need to re-run reviewers. Stale (commit no longer matches) or none found → discard
     any stale one (`mcp__github__pull_request_review_write` method `delete_pending`) and
     resume normally from step 3. Mismatch → report and stop.
   - Given (or pooled) without `--resume`, `status:in-review`, assigned, no
     `needs-human`/`on-hold`, thread shows a `needs-human` block later cleared → resume,
     not a fresh claim. Follow `docs/pilot-process.md` §4 "Resuming a `needs-human` ticket"
     instead of step 2 — already claimed.
   - Given without `--resume`, `status:in-review`, assigned, no `needs-human`/`on-hold`, no
     `needs-human` history → looks orphaned; report and ask the human to re-run with
     `--resume` rather than proceeding.
   - `status:in-review` still carrying `needs-human`/`on-hold` → not resolved yet; report
     and stop.
   - Otherwise, or none given → per `docs/pilot-process.md` §4 "Picking the next
     ticket...": the given ticket, or the merged pool of unclaimed `status:review-ready`
     (fresh) and `status:in-review` with `needs-human` just cleared (resumable — handled by
     the second bullet above, not here), excluding `on-hold`, ordered by highest
     `priority:`, then a ticket named in another open ticket's "Blocks #M" before one that
     isn't, then oldest first (`mcp__github__search_issues`). `status:changes-requested`
     tickets are never in this pool — `/pilot-dev` reclaims those (§4).
2. **Claim** it (fresh case only, above) per `docs/pilot-process.md` §4: assignee +
   `status:in-review`, re-read to confirm. If the assignee changed (race lost), stand down
   and return to step 1 for a different candidate (bare pool only — report nothing to do if
   a specific ticket was requested).
3. Read the ticket's linked issue and **its own** `type:` label (never a parent's,
   `docs/pilot-process.md` §2 "`type:` is never inherited") to pick the reviewer set:
   - `type:feature` or `type:e2e` → `pilot-pm`, `pilot-architect`, `pilot-techlead`
   - `type:tech` or `type:bug` → `pilot-architect`, `pilot-techlead` (no PM)

   Together these cover every dimension phase 5 checks: PM — product fit / e2e-flow
   validation; architect — conformance to recorded security/architecture decisions; tech
   lead — spec conformance and code quality. If a future edit changes what any agent's
   file checks, re-verify this still adds up to full coverage. All reviewers run **in
   parallel, fully independent of each other** — none sees another's verdict — in both
   pair and `--auto`; nothing later in the run reopens that isolation, not even the one
   pair checkpoint.
4. Once this project has a CI workflow covering the affected area, check it's green on the
   PR's head commit before proceeding — red/pending CI is an automatic `change`-tagged
   block (step 6). Until then, this is a no-op and the tech lead's own re-run in step 5 is
   the only safety net.
5. Call the `Agent` tool once per reviewer, **in parallel**, `subagent_type` set to that
   persona (per step 3's independence guarantee). Pass every reviewer
   `docs/pilot-link-review-consensus.md` in full — the shared verdict format and tagging
   rule, identical for all three, one canonical statement instead of restated per persona
   — plus the matching task doc for what's specific to that persona:
   `docs/pilot-task-review-product-fit.md` (PM),
   `docs/pilot-task-review-architecture.md` (architect),
   `docs/pilot-task-review-spec-conformance.md` (tech lead) — the persona file itself
   (`.claude/agents/pilot-*.md`) carries only identity now, these two together are what
   tell each reviewer what to check and how to report it. Pass only
   what each needs beyond that: the PR diff/description plus, for the PM, the linked
   story's acceptance criteria (and its own spec, for `type:e2e`); for the architect, its
   recorded decisions; for the tech lead, its own spec (it re-runs validation on the PR
   branch itself). When resuming (step 1's needs-human-resume branch), also pass the
   original blocking review's `decision`-tagged points — the submitted PR review from the
   run that raised the block, fetched via `mcp__github__pull_request_read` method
   `get_reviews` (its body holds the points, not a plain issue comment) — and whatever's
   in the PR's comment thread after it: a specific reply, or "no reply — treat as approved
   as proposed" if none (`docs/pilot-process.md` §4 "Resuming a `needs-human` ticket") —
   so reviewers don't re-raise a point a human already answered.
6. Collect the verdicts. Aggregate into exactly **one** outcome
   (`docs/pilot-link-review-consensus.md`):
   - All blocking points tagged `decision`, none `change` → every point, grouped by
     reviewer, `needs-human` added (`status:in-review` stays — this ticket re-enters the
     resumable half of step 1's pool once cleared, unless step 10 resolves it live first).
   - At least one blocking point tagged `change` (a step-4 CI/validation failure always
     counts) and at least one tagged `decision` → every point (marked which is which),
     `needs-human` added, move to `status:changes-requested` (`/pilot-dev` reclaims once
     cleared — the `decision` point(s) are what it's waiting on).
   - At least one blocking point tagged `change`, none tagged `decision` → every point,
     move to `status:changes-requested`, **no** `needs-human` — nothing here needs a
     human, so `/pilot-dev` may reclaim it immediately.
   - All approved → move to `status:approved`.
7. **Checkpoint it**: create a pending GitHub PR review with the outcome's full body
   already written, no `event` yet (`mcp__github__pull_request_review_write`, method
   `create`, `commitID` pinned to the PR's current head) — durable immediately, so an
   orphaned run recovers it (step 1) instead of redoing steps 3-6.
8. **Pair (default) vs `--auto`** — never for an outcome that carries `needs-human`
   (decision-only, or mixed `change`+`decision`): `docs/pilot-process.md` §3's
   `needs-human` rule requires the block to reach GitHub before any resolution, even a live
   one, so either of those always proceeds straight to step 9, same as `--auto`. For the
   all-approve outcome or a pure-`change` outcome (no `decision` point at all), pair mode
   pauses here — nothing for a human to decide (an approval or a code-level fix isn't a
   judgment call), but still worth a last look before it goes to GitHub: show the outcome
   from step 6, wait for confirmation, then proceed to step 9. `--auto` skips this pause and
   proceeds immediately either way.
9. Submit step 7's pending review (`mcp__github__pull_request_review_write`, method
   `submit_pending`) plus the matching label — the outcome's `event`
   (`docs/pilot-link-review-consensus.md`):
   - All approved → `event: APPROVE`; body states all agents approve and, per step 12,
     whether this run also merges or a human still needs to; `status:approved`.
   - At least one blocking point tagged `change`, none tagged `decision` → `event:
     REQUEST_CHANGES`; body lists every point; **no** `needs-human`; `status:changes-requested`
     — `/pilot-dev` may reclaim it right away, no human step needed.
   - At least one point of each tag → `event: REQUEST_CHANGES`; body lists every point
     (marked which is which); `needs-human` added; `status:changes-requested` — `/pilot-dev`
     reclaims once the `decision` point(s) are cleared.
   - Blocking points all `decision` → `event: COMMENT`; body lists every point grouped by
     reviewer; `needs-human` added; `status:in-review` stays.
10. **Live resolution of a submitted `needs-human` block** (pair mode only, right after
    step 9 submits it; applies to both the decision-only and the mixed `change`+`decision`
    outcome — never the pure-`change` outcome, which never carries `needs-human` to
    resolve): engage the human live the same way any other phase resolves a live
    `needs-human` block (`docs/pilot-process.md` §3 "A human is live in the same session").
    If they answer right there and it changes the outcome, determine the corrected outcome
    (approved, or the remaining `change`-tagged points instead) and submit **one more**
    review — a fresh `create` with `event` set this time, no separate pending step needed
    for a decision made in the same breath — reflecting it, same event mapping as step 9,
    plus the matching label. This keeps GitHub's own review status honest, not just the
    ticket's label; never fold it into step 9's review, that one already went out. If their
    answer doesn't actually clear the block, or `--auto` was given, or nobody answers on the
    spot: leave step 9's review and `needs-human` standing — a genuine async wait like any
    other unresolved `needs-human`, resolved by a later run of this skill.
11. Never submit more than two reviews in one run — step 9's, plus step 10's
    live-resolution correction when it applies — and never one review per reviewer.
12. **Merge, only with `--merge`:** if the final outcome (step 9, or step 10's correction) is
    `status:approved` and `--merge` was passed, merge the PR now
    (`mcp__github__merge_pull_request`, the repository's normal merge method). Without
    `--merge`, or on any other outcome, never merge — a human merges by hand, same as
    before.
13. Report the outcome, including whether this run merged the PR itself. Once the PR is
    merged (by a human, or by step 12), `.github/workflows/pilot-status-on-merge.yml` sets
    `status:done` and runs the cascading-completion check (`docs/pilot-process.md` §3)
    — this skill's own job ends at the submitted review(s) (plus, when `--merge` applied,
    the merge itself).
