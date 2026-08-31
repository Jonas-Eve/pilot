---
name: pilot-review
description: "Phase 5 of PILOT (see docs/pilot-process.md): runs the review agents (PM+architect+tech lead for type:feature/type:e2e, architect+tech lead only for type:tech/type:bug) in parallel against an open PR, then posts one consolidated GitHub comment — a joint go-ahead (status:approved), blocking points that are pure judgment calls (needs-human added, status:in-review stays), or blocking points needing actual code changes (needs-human added, moved to status:changes-requested for /pilot-dev). Also re-reviews a PR once a prior needs-human flag on status:in-review is cleared, and with no argument sweeps every status:in-review PR ready for review/re-review (e.g. from a scheduled cron Routine), skipping any on-hold. A human always does the actual merge — PILOT never merges. Use once /pilot-dev has opened a PR ready for review."
argument-hint: "<PR number, or issue number, optional — sweeps status:in-review PRs ready for review/re-review if omitted>"
disable-model-invocation: true
---

# PILOT — Phase 5: Test & Validate

Read `docs/pilot-process.md` first — source of truth for labels, states, and the
review-consensus mechanics (§6); this skill covers only phase 5's mechanics.

## Steps

1. Resolve the PR(s) per `docs/pilot-process.md` §6 step 0: the given PR/issue number, or
   if none — every `status:in-review` PR either never reviewed (no `needs-human`/`on-hold`
   yet) or blocked and just had `needs-human` cleared (resumed; re-read the thread for
   what changed), excluding any still carrying `on-hold`. Phase 5 doesn't claim, so no
   assignee is involved, just this label check. `status:changes-requested` tickets are
   not in this pool — `/pilot-dev` reclaims those; this skill sees it again only once dev
   pushes back to `status:in-review`. For each, read its linked issue
   (`mcp__github__pull_request_read`, `mcp__github__issue_read`) and **its own** `type:`
   label to decide the reviewer set — never a parent's, `type:` is never inherited
   (`docs/pilot-process.md` §2 "`type:` is never inherited" — a `type:tech` task under a
   `type:feature` story's split is reviewed as `type:tech`, not `type:feature`):
   - `type:feature` or `type:e2e` → `pilot-pm`, `pilot-architect`, `pilot-techlead`
   - `type:tech` or `type:bug` → `pilot-architect`, `pilot-techlead` (no PM)

   Together these cover every dimension phase 5 checks, nothing dropped silently
   (`docs/pilot-process.md` §6): PM — product fit against acceptance criteria
   (`type:feature`) or whether the test validates the end-to-end flow (`type:e2e`);
   architect — conformance to the security/architecture decisions recorded at scope time;
   tech lead — conformance to its own spec *and* general code quality/maintainability. If
   a future edit changes what any agent's file says it checks, re-verify this list still
   adds up to full coverage.
2. Once this project has a CI workflow covering the affected area, check it's green on
   the PR's head commit (`mcp__github__pull_request_read` `get_check_runs`/`get_status`)
   before proceeding — red or pending CI is an automatic, `change`-tagged block (step 4),
   skip straight there. Until that workflow exists, this check is a no-op and the tech
   lead's own re-run in step 3 is the only safety net.
3. Call the `Agent` tool once per reviewer, **in parallel** (independent calls in the
   same turn, not sequential), `subagent_type` set to that reviewer's persona name
   (`pilot-pm`, `pilot-architect`, `pilot-techlead`) — none sees another's verdict. Pass
   only what each needs: the PR diff/description plus, for the PM, the linked story's
   acceptance criteria (and its own spec too, for a `type:e2e` task); for the architect,
   its own recorded security/architecture decisions from the ticket; for the tech lead,
   its own spec from the ticket (it re-runs validation on the PR branch itself as part of
   forming its verdict, per `docs/pilot-process.md` §6). Each reviewer's persona
   (`.claude/agents/pilot-*.md`) already tags every blocking point `change` or
   `decision` — no extra instruction needed here.
4. Collect the verdicts. Aggregate into exactly **one** GitHub comment on the PR
   (`mcp__github__pull_request_review_write` / `add_comment_to_pending_review`, or
   `add_issue_comment` on the PR):
   - All blocking points across all reviewers (plus a CI/validation failure from step 2,
     always `change`) tagged `decision` → one comment listing every point, grouped by
     reviewer role, add `needs-human` on the issue (`status:in-review` stays as-is — an
     orthogonal flag, `docs/pilot-process.md` §3). This ticket re-enters this skill's own
     bare pool (step 1) once the flag is cleared.
   - Any blocking point tagged `change` (a step-2 CI/validation failure always counts) →
     one comment listing every point — marked `change`/`decision`, grouped by reviewer
     role — add `needs-human`, and move the ticket to `status:changes-requested` instead
     of leaving `status:in-review` (`docs/pilot-process.md` §3/§6/§4 "Reclaiming a
     `status:changes-requested` ticket"). `/pilot-dev`, not this skill, picks it back up
     once the flag is cleared.
   - All approved → one comment stating all reviewing agents approve and that a human
     still needs to merge; move the ticket to `status:approved` instead of leaving
     `status:in-review` (`docs/pilot-process.md` §3).
5. Never post a separate comment per reviewer.
6. Report the outcome back to the human. Never merge — that's always a human action,
   even after every reviewer approves. Once a human does merge, the
   `.github/workflows/pilot-status-on-merge.yml` GitHub Actions workflow sets
   `status:done` and, if it's a task with a `status:split` parent, runs the
   cascading-completion check against that parent (never a `level:epic` — that always
   closes by hand, see `docs/pilot-process.md` §3) — a standalone `type:bug` task has no
   parent at all, so the check simply finds none and stops there
   (`docs/pilot-process.md` §3 "Cascading completion") — see `docs/pilot-process.md` §6;
   this skill's own job ends at the consolidated comment.
