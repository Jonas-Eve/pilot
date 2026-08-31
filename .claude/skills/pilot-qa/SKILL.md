---
name: pilot-qa
description: "Phase 6 of PILOT (see docs/pilot-process.md): human QA for a type:feature story once every task — including its mandatory e2e one — has merged (status:qa). Builds a manual test plan from the story's acceptance criteria and its merged tasks, walks a human through testing it live, and reports the verdict. Pair-only, no --auto — there's no unattended version of a human testing something, so this is never Routine-driven. On a full pass, sets status:done and closes the issue. On a failure, adds needs-human with exactly what failed (the bug-handling flow for this case is still being designed — a human decides what happens next by hand for now). Also resumes a ticket left mid-pair session with --resume <issue number>, and runs bare with no argument to pick up the next status:qa (fresh) or status:in-qa-with-needs-human-cleared (resumable) ticket, skipping anything still on-hold. Use once a type:feature story's tasks have all merged and it's ready for a human to confirm the shipped behavior."
argument-hint: "<issue number> | --resume <issue number>"
disable-model-invocation: true
---

# PILOT — Phase 6: Human QA

Read `docs/pilot-process.md` before running this if you haven't already — it's the source
of truth for labels, states, and the claim protocol, and §7 specifically covers this phase;
this skill only covers the mechanics of running it.

## Steps

1. Determine the input:
   - An issue number given with `--resume`: it must be `status:in-qa`, already assigned,
     with **no** `needs-human` and **no** `on-hold` — a session left mid-pair
     (`docs/pilot-process.md` §4 "Resuming a paused pair session"). Read the full ticket
     and comment thread to reconstruct which cases were already confirmed, then claim it
     the same way — overwrite the assignee, same as any paused-pair resume. Skip to step 5
     with that reconstructed state as the starting point. If the ticket doesn't match,
     report that and stop.
   - An issue number given without `--resume` that's `status:in-qa` with **no**
     `needs-human`/`on-hold`, whose thread shows a `needs-human` block that was later
     cleared → a resume, not a fresh claim (`docs/pilot-process.md` §4 "Resuming a
     `needs-human` ticket"). Skip the claim in step 2, it's already claimed.
   - An issue number given without `--resume`, `status:in-qa`, already assigned, **no**
     `needs-human`/`on-hold`, but with no `needs-human` history in its thread → looks like a
     session left mid-pair. Report that and ask the human to re-run with `--resume` rather
     than proceeding.
   - An issue number that still carries `needs-human` or `on-hold` → not resolved yet,
     report that and stop.
   - An issue number otherwise: it must be `status:qa` — if it isn't (still `status:split`,
     already `status:done`, or any other type's ticket that never reaches `status:qa` at
     all, `docs/pilot-process.md` §7 "When it fires"), report that and stop rather than
     claiming it.
   - No argument → per `docs/pilot-process.md` §4 "Picking the next ticket...": the merged
     pool of unclaimed `status:qa` (fresh) and `status:in-qa` with `needs-human` just
     cleared (resumable — a ticket left mid-pair is never in this pool, only reachable via
     an explicit `--resume <issue>`), excluding any `on-hold`, highest `priority:` then
     oldest first. This phase has no `--auto` and is never Routine-driven
     (`docs/pilot-process.md` §4 "Interaction modes", "Scheduled sweeps") — bare mode here
     is only ever an interactive human picking up the next thing to test.
2. **Claim** it per `docs/pilot-process.md` §4: set assignee + `status:in-qa`, re-read to
   confirm the claim held.
3. Gather context: the story's own body (acceptance criteria) and, for each of its dev and
   e2e tasks, the spec (phase 3) and the merged PR (`mcp__github__issue_read`,
   `mcp__github__pull_request_read`) — not the running conversation history.
4. Call the `Agent` tool with `subagent_type: "pilot-qa"`, passing that context. The agent
   returns a manual test plan: concrete cases and how to test each.
5. Walk the human through it (pair, always — this skill has no `--auto`): show the plan,
   then go case by case — ask them to run one, report what happened, feed that back to the
   agent, move to the next — until every case is reported. Write progress into the ticket
   as you go (a comment per case or a short batch), the same incremental-checkpoint
   discipline every other pair-mode phase follows (`docs/pilot-process.md` §4 "Interaction
   modes") — this is what makes `--resume` possible if the session ends before a final
   verdict.
6. Apply the agent's verdict:
   - **Approved** (every case confirmed): set `status:done` and close the issue
     (`mcp__github__issue_write`) — this is the one phase that sets `status:done` directly
     on an actionable ticket, since there's no PR merge here for
     `.github/workflows/pilot-status-on-merge.yml` to react to. Nothing else to cascade — a
     `type:feature` story is never itself a task of another `status:split` parent.
   - **Failed** (one or more cases): add `needs-human` with a comment listing exactly what
     failed, per case, as the agent reported it (`status:in-qa` stays,
     `docs/pilot-process.md` §3 "`needs-human`"). Don't originate a ticket or attempt a fix
     yourself — that mechanism doesn't exist yet for this phase (`docs/pilot-process.md`
     §7 step 6); a human decides what happens next.
7. Report the outcome (approved + closed, or the failing cases) back to the human. Never
   invoke `pilot-e2e`/`pilot-dev` from this skill — a QA failure is a human decision point,
   not an automatic handoff into phase 4.

Do not run this against a `type:tech`/`type:bug` ticket, or against a task itself —
neither ever reaches `status:qa` (`docs/pilot-process.md` §7 "When it fires").
