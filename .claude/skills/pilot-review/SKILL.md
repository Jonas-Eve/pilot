---
name: pilot-review
description: "Phase 5 of PILOT (see docs/pilot-process.md): runs the review agents (PM+architect+tech lead for type:feature, architect+tech lead only for type:tech) in parallel against an open pull request, then posts one consolidated GitHub comment — a joint go-ahead (status:approved), blocking points that are pure judgment calls for a human (needs-human added, status:in-review stays), or blocking points that need actual code changes (needs-human added, moved to status:changes-requested for /pilot-dev to address). Also re-reviews a PR once a human clears a prior needs-human flag on status:in-review, and runs bare with no argument to sweep every status:in-review PR ready for review or re-review (e.g. from a scheduled cron Routine), skipping any that's on-hold. A human always does the actual merge, PILOT never merges. Use once /pilot-dev has opened a PR and it's ready for review."
argument-hint: "<PR number, or issue number, optional — sweeps status:in-review PRs ready for review/re-review if omitted>"
disable-model-invocation: true
---

# PILOT — Phase 5: Test & Validate

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the review-consensus mechanics (§6); this skill
only covers the mechanics of running phase 5.

## Steps

1. Resolve the PR(s) per `docs/pilot-process.md` §6 step 0: the given PR/issue number, or
   if none — every `status:in-review` PR that's either never been reviewed (no
   `needs-human` or `on-hold` yet) or was blocked and just had `needs-human` cleared
   (resumed; re-read the thread for what changed), excluding any still carrying
   `on-hold`. Phase 5 doesn't claim, so there's no assignee involved, just this label
   check. A ticket currently `status:changes-requested` is not in this pool —
   `/pilot-dev` reclaims those; this skill only sees it again once dev pushes it back to
   `status:in-review`. For each, read its linked issue
   (`mcp__github__pull_request_read`, `mcp__github__issue_read`) and its `type:` label to
   decide the reviewer set:
   - `type:feature` → `pilot-pm`, `pilot-architect`, `pilot-techlead`
   - `type:tech` → `pilot-architect`, `pilot-techlead` (no PM)

   Together these cover every dimension phase 5 checks, with nothing dropped silently
   (`docs/pilot-process.md` §6): PM — product fit against the story's acceptance
   criteria (feature only); architect — conformance to the security/architecture
   decisions recorded at scope time; tech lead — both conformance to its own spec *and*
   general code quality/maintainability. If a future edit changes what any one agent's
   own file says it checks, re-verify this list still adds up to full coverage.
2. Once this project has a CI workflow covering the affected area, check it's green on
   the PR's head commit (`mcp__github__pull_request_read` `get_check_runs`/`get_status`)
   before going further — red or pending CI is an automatic, `change`-tagged block (step
   4 below), skip straight to step 4. Until that workflow exists, this check is a no-op
   (there's nothing to check yet) and the tech lead reviewer's own re-run in step 3 is the
   only safety net.
3. Call the `Agent` tool once per reviewer, **in parallel** (independent calls in the
   same turn, not sequential), with `subagent_type` set to that reviewer's persona name
   (`pilot-pm`, `pilot-architect`, `pilot-techlead`) — none should see another's verdict.
   Each call passes only what that reviewer needs: the PR diff/description, and for the
   PM, the linked story's acceptance criteria; for the architect, its own recorded
   security/architecture decisions from the ticket; for the tech lead, its own spec from
   the ticket (the tech lead re-runs validation on the PR branch itself as part of
   forming its verdict, per `docs/pilot-process.md` §6). Each reviewer's persona
   (`.claude/agents/pilot-*.md`) already knows to tag every blocking point `change` or
   `decision` — no extra instruction needed here.
4. Collect the verdicts. Aggregate into exactly **one** GitHub comment on the PR
   (`mcp__github__pull_request_review_write` / `add_comment_to_pending_review`, or
   `add_issue_comment` on the PR):
   - Every blocking point across all reviewers (plus a CI/validation failure from step 2,
     which is always `change`) is tagged `decision` → one comment listing every point,
     grouped by reviewer role, and add `needs-human` on the issue (`status:in-review`
     stays as-is — it's an orthogonal flag, `docs/pilot-process.md` §3). This ticket
     re-enters this skill's own bare pool (step 1 above) once the flag is cleared.
   - Any blocking point is tagged `change` (a CI/validation failure from step 2 always
     counts) → one comment listing every point — marked `change`/`decision`, grouped by
     reviewer role — add `needs-human`, and move the ticket to `status:changes-requested`
     instead of leaving `status:in-review` (`docs/pilot-process.md` §3/§6/§4 "Reclaiming a
     `status:changes-requested` ticket"). `/pilot-dev`, not this skill, picks it back up
     once the flag is cleared.
   - All approved → one comment stating all reviewing agents approve and that a human
     still needs to merge; move the ticket to `status:approved` instead of leaving
     `status:in-review` (`docs/pilot-process.md` §3).
5. Never post a separate comment per reviewer.
6. Report the outcome back to the human. Never merge — that's always a human action,
   even after every reviewer approves. Once a human does merge, the
   `.github/workflows/pilot-status-on-merge.yml` GitHub Actions workflow sets
   `status:done` and, if it's a sub-ticket, runs the cascading-completion check against
   its `status:split` parent story (never a `type:epic` — that always closes by hand,
   see `docs/pilot-process.md` §3) — see `docs/pilot-process.md` §6; this skill's own job
   ends at the consolidated comment.
