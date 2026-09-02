---
name: pilot-review
description: "Phase 5 of PILOT (see docs/pilot-process.md): claims a status:review-ready PR (assignee + status:in-review, docs/pilot-process.md §4 'Claim Protocol'), then runs the review agents (PM+architect+tech lead for type:feature/type:e2e, architect+tech lead only for type:tech/type:bug) in parallel, and posts one consolidated GitHub comment — a joint go-ahead (status:approved), blocking points that are pure judgment calls (needs-human added, status:in-review stays), or blocking points needing actual code changes (needs-human added, moved to status:changes-requested for /pilot-dev). Also resumes a ticket once a prior needs-human flag is cleared, recovers a claim orphaned by a crashed run via --resume <issue>, and with no argument sweeps every ready/resumable PR (e.g. from a scheduled cron Routine), skipping any on-hold. A human always does the actual merge — PILOT never merges. Use once /pilot-dev has opened a PR ready for review."
argument-hint: "<PR number, or issue number, optional — sweeps ready PRs if omitted> | <issue number> --resume"
---

# PILOT — Phase 5: Test & Validate

Read `docs/pilot-process.md` first — source of truth for labels, states, the claim
protocol, and the review-consensus mechanics (§4, §6); this skill covers only phase 5's
mechanics.

## Steps

1. Resolve the ticket:
   - Given `--resume`: must be `status:in-review`, assigned, no `needs-human`/`on-hold`.
     Follow `docs/pilot-process.md` §4 "Resuming an orphaned claim" instead of step 2 below
     — already claimed. Mismatch → report and stop.
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

   Together these cover every dimension phase 5 checks (`docs/pilot-process.md` §6): PM —
   product fit / e2e-flow validation; architect — conformance to recorded
   security/architecture decisions; tech lead — spec conformance and code quality. If a
   future edit changes what any agent's file checks, re-verify this still adds up to full
   coverage.
4. Once this project has a CI workflow covering the affected area, check it's green on the
   PR's head commit before proceeding — red/pending CI is an automatic `change`-tagged
   block (step 6). Until then, this is a no-op and the tech lead's own re-run in step 5 is
   the only safety net.
5. Call the `Agent` tool once per reviewer, **in parallel**, `subagent_type` set to that
   persona — none sees another's verdict. Pass only what each needs: the PR diff/
   description plus, for the PM, the linked story's acceptance criteria (and its own spec,
   for `type:e2e`); for the architect, its recorded decisions; for the tech lead, its own
   spec (it re-runs validation on the PR branch itself, `docs/pilot-process.md` §6). When
   resuming (step 1's needs-human-resume branch), also pass the original blocking
   comment's `decision`-tagged points and whatever's in the thread after it — a specific
   reply, or "no reply — treat as approved as proposed" if none
   (`docs/pilot-process.md` §4 "Resuming a `needs-human` ticket") — so reviewers don't
   re-raise a point a human already answered. Each persona
   (`.claude/agents/pilot-*.md`) already tags blocking points `change`/`decision`.
6. Collect the verdicts. Aggregate into exactly **one** GitHub comment on the PR:
   - All blocking points tagged `decision` → one comment grouped by reviewer, add
     `needs-human` (`status:in-review` stays — this ticket re-enters the resumable half of
     step 1's pool once cleared).
   - Any blocking point tagged `change` (a step-4 CI/validation failure always counts) →
     one comment listing every point (marked which is which), add `needs-human`, move to
     `status:changes-requested` (`/pilot-dev` reclaims once cleared).
   - All approved → one comment stating so and that a human still needs to merge; move to
     `status:approved`.
7. Never post a separate comment per reviewer.
8. Report the outcome. Never merge. Once a human merges,
   `.github/workflows/pilot-status-on-merge.yml` sets `status:done` and runs the
   cascading-completion check (`docs/pilot-process.md` §3, §6) — this skill's own job ends
   at the consolidated comment.
