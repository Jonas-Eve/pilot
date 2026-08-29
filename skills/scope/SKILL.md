---
name: scope
description: "Phase 2 of PILOT (see docs/pilot-process.md): the architect agent challenges a ticket and either scopes it as-is, splits it into dev-sized sub-tickets, or decides it shouldn't be built at all (status:wont-do). Handles both entry points — an existing type:feature story from /pilot:story, or a raw technical need in free text with no story (formalized into one or more type:tech stories, grouped under a new or reused type:epic if the need spans several). Defaults to pair mode — walks through the proposed decomposition with a human live in the session, checkpointing progress into the ticket as it goes; pass --auto to finalize straight away instead (needed for a scheduled cron Routine, since pair requires a live human). Also resumes a ticket it previously flagged needs-human once a human clears that flag, resumes a ticket left mid-pair session with --resume <issue number>, and runs bare with no argument to pick up fresh or needs-human-resumable work (e.g. --auto from a scheduled cron Routine), skipping anything still on-hold. Use whenever a ticket needs to be scoped/decomposed, or a purely technical need needs to become a ticket in the first place."
argument-hint: "<issue number> [--auto] | <issue number> --resume | <raw technical need in free text> [--auto]"
disable-model-invocation: true
---

# PILOT — Phase 2: Investigate

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 2.

## Steps

1. Determine the input:
   - An issue number given with `--resume`: it must be `status:scoping`, already
     assigned, with **no** `needs-human` and **no** `on-hold` — a ticket left mid-pair
     session. Follow `docs/pilot-process.md` §4 "Resuming a paused pair session" instead
     of the rest of these steps — skip the claim in step 2, it's already claimed. If the
     ticket doesn't match (wrong status, unassigned, or still carrying `needs-human`/
     `on-hold`), report that and stop.
   - An issue number given without `--resume` that's currently `status:scoping` with
     **no** `needs-human` and **no** `on-hold`, and whose thread shows a `needs-human`
     block that was later cleared → this is a resume, not a fresh claim. Follow
     `docs/pilot-process.md` §4 "Resuming a `needs-human` ticket" instead of the rest of
     these steps — skip the claim in step 2, it's already claimed.
   - An issue number given without `--resume` that's `status:scoping`, already assigned,
     **no** `needs-human`, **no** `on-hold`, but with no `needs-human` history in its
     thread → this looks like a ticket left mid-pair session. Report that and ask the
     human to re-run with `--resume` rather than proceeding.
   - An issue number that's `status:scoping` and still carries `needs-human` or
     `on-hold` → not resolved yet, report that and stop.
   - An issue number otherwise → this is an existing story (`type:feature` or
     `type:tech`) being scoped/re-scoped. Read it (`mcp__github__issue_read`). If it's
     `type:epic`, there's nothing to scope on the epic itself — stop and point at its
     stories instead.
   - Free text with no issue number → a raw technical need with no story yet. Also fetch
     open `type:epic` + `type:tech` issues (title + body, `list_issues`/`search_issues`)
     as reuse candidates for the agent — this may become one fresh `type:tech` story, or
     several under a (new or reused) tech Epic.
   - No argument → per `docs/pilot-process.md` §4 "Picking the next ticket...": the
     merged pool of unclaimed `status:backlog` tickets (fresh) and `status:scoping`
     tickets with `needs-human`/`on-hold` just cleared (resumable — a ticket left mid-pair
     session is never in this pool, only reachable via an explicit `--resume <issue>`),
     highest `priority:` then oldest first. Among fresh candidates, prefer `type:feature`
     over freshly-reported `type:tech` needs unless one is explicitly flagged urgent — ask
     if it's ambiguous. This is what a scheduled cron Routine drives with `--auto` added
     (`docs/pilot-process.md` §4 "Scheduled sweeps").
2. **Claim** the ticket per `docs/pilot-process.md` §4: set assignee + `status:scoping`,
   re-read to confirm the claim held. For a brand-new `type:tech` need (no issue exists
   yet), this happens after step 3 instead — there's nothing to claim before the
   agent has decided whether it's one story or several under an Epic.
3. Call the `Agent` tool with `subagent_type: "pilot-architect"` (if that bare name isn't
   found — this persona ships via the `pilot` plugin — retry as `"pilot:pilot-architect"`),
   passing only what phase
   2 needs: the ticket's current body (or the raw free-text need plus the candidate Epic
   list, for a fresh `type:tech` need), and pointers to this project's own coding
   standards/security conventions and its own architecture docs (wherever it documents
   its identity/tenancy/security boundaries and its target system design, if it has such
   docs). Not the running conversation history.
4. The subagent returns one of: for an existing story — a single scoped ticket body (no
   split needed), a set of sub-tickets each with security/architecture decisions and a
   suggested priority, or a verdict that it shouldn't be built at all; for a fresh
   `type:tech` need — one new story (claim it now, per step 2, before scoping it inline),
   or several new stories under a (new or reused) Epic.
4a. **Unless `--auto` was given** (`docs/pilot-process.md` §4 "Interaction modes" — pair
    is the default for this skill): don't finalize anything yet. Show the human the
    proposed decomposition — split or not, security/architecture decisions, wont-do
    verdict, whatever the agent decided — as a normal reply, wait for their response, and
    feed it back to the agent — repeat until they approve. Once a checkpoint is approved
    **and the ticket being scoped already exists** (an existing story, not a brand-new
    `type:tech` need with no issue yet), write it into the ticket right away (a comment
    summarizing the current proposal, or a partial `issue_write`) instead of holding it
    in-conversation — this is what `--resume` picks back up later if the session ends
    before final approval (`docs/pilot-process.md` §4 "Resuming a paused pair session").
    For a brand-new `type:tech` need with no ticket yet, the first checkpoint (one story
    or several under an Epic) is still held in-conversation until that first creation
    happens, the same as `/pilot:story`. Requires a human live in this session; a
    scheduled Routine must pass `--auto` instead. Once approved, continue to step 5 as
    normal — its GitHub write is then just the remaining piece (final labels, any
    still-unwritten sub-issues), since earlier checkpoints were already saved.
5. Apply the result (`mcp__github__issue_write`, `mcp__github__sub_issue_write`):
   - No split: update the ticket body with the decisions, set `status:spec-ready`.
   - Split into sub-tickets: create the sub-issues, link them to the parent as native
     sub-issues, each inheriting the root `type:` and getting `status:spec-ready` +
     `priority:P0/P1/P2`. Set the parent's `status:` to `split` (not `type:epic` — that
     label is reserved for a group of *stories*, not a story's own sub-tickets; see
     `docs/pilot-process.md` §2), leave it open and unassigned as a tracker.
   - Fresh `type:tech` need, single story: create it (`type:tech` + `status:backlog`),
     then claim and scope it inline the same as an existing story would be.
   - Fresh `type:tech` need, several stories: create the Epic if new (`type:epic` +
     `type:tech`, no `status:` label) or reuse the existing one, create each story
     (`type:tech` + `status:backlog`) linked as its sub-issue — leave each story to be
     scoped by its own later `/pilot:scope` run, don't scope them inline here.
   - Won't-do (clear-cut only): label `status:wont-do`, close the issue. If it's not
     clear-cut, add `needs-human` with the subagent's reasoning instead (keep
     `status:scoping`) — don't close it.
6. Report the outcome (ticket(s)/Epic created or updated, priorities set, or closed as
   won't-do) back to the human.
