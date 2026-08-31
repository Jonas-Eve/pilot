---
name: pilot-story
description: "Phase 1 of PILOT (see docs/pilot-process.md): turn a raw need into a formalized GitHub issue — a functional type:feature user story or type:tech technical need (PM/architect agent, level:story, finalizing to status:backlog for /pilot-scope), or, for a genuine type:bug defect (architect agent, which also classifies whether it's really a bug), a type:bug ticket created directly as level:task, finalizing straight to status:spec-ready instead — a bug is dev-sized by definition and never goes through /pilot-scope at all. Auto-detected from the need itself, or grouped into a new/reused level:epic if a type:feature/type:tech need genuinely spans several (type:bug is never grouped). Pass --tech or --bug to declare the need's type upfront instead of relying on detection. Always runs in pair mode — drafts the story/need with a human live in the session, creating the ticket as status:draft the moment a first draft exists and refining it in place rather than holding it in conversation; a wrong detection is never silent, it's corrected live. There's no --auto for this phase, so it's never driven by a scheduled Routine — but --resume <issue number> picks back up a status:draft ticket left mid-pair if the session ends before final approval. For a type:feature/type:tech need, this phase only formalizes what the need is — it never decides dependencies, prerequisites, or whether it needs splitting; that's entirely /pilot-scope's job, run separately afterward. Use whenever a human wants to start a new ticket from scratch, whatever kind of work it is."
argument-hint: "<raw need in free text> [--tech | --bug] | --resume <issue number>"
disable-model-invocation: true
---

# PILOT — Phase 1: Plan

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 1.

## Steps

1. Determine the input:
   - `--resume <issue number>`: must be `status:draft`, already assigned, with **no**
     `needs-human` and **no** `on-hold` — a draft left mid-pair session
     (`docs/pilot-process.md` §4 "Resuming a paused pair session"). Read the full ticket
     and comment thread (`mcp__github__issue_read` `get_comments`) to reconstruct what's
     already been drafted, then claim it — overwrite the assignee, the same as any
     paused-pair resume. Skip to step 5b with that reconstructed state as the starting
     point (call the agent in step 4 again first if the resumed conversation calls for
     revising the draft, passing it the reconstructed context instead of a blank raw
     need). If the ticket doesn't match (wrong status, unassigned, or still carrying
     `needs-human`/`on-hold`), report that and stop.
   - A raw need (the argument, or ask the human for one if none was given): continue with
     steps 2-5 below. Do not pre-analyze it yourself — phase 1's thinking belongs to
     whichever agent ends up drafting it, not to this skill's orchestration layer.
2. Decide which agent drafts it:
   - `--tech` given → `pilot-architect`, `type:tech`.
   - `--bug` given → `pilot-architect`, `type:bug`.
   - No flag → auto-detect from the need's content: a report of already-shipped behavior
     that's broken/regressed (an error, something that used to work and doesn't, output
     that contradicts what's documented/agreed) reads as `type:bug` (`pilot-architect`);
     infra/CI/security/deployment/migration/optimization work with no defect implied
     reads as `type:tech` (`pilot-architect`); product-facing/user-value work reads as
     `type:feature` (`pilot-pm`). If it's genuinely ambiguous between any two of the
     three, ask the human which it is rather than guessing silently.
3. Fetch open `level:epic` issues of the matching `type:` (title + body only,
   `mcp__github__list_issues`/`search_issues`) as candidates the agent might reuse —
   cheap, deterministic bookkeeping, not the agent's job to search for itself.
4. Call the `Agent` tool with the subagent chosen in step 2, passing the raw need and the
   candidate Epic list — nothing else from this conversation's history — the subagent
   should get a clean, scoped context, not the running transcript
   (`docs/pilot-process.md` §5).
5. The subagent returns one of: out of scope (per this project's functional-scope doc, if
   it has one, `type:feature` only — stop and report that, create nothing); a single
   story; several stories plus either an existing Epic number to reuse or a new Epic to
   create; or, for a `--bug`/auto-detected-`type:bug` attempt, a single `type:bug` ticket
   ready to build, or a verdict that it isn't actually a defect (handled the same way as
   any other wrong `--tech`/`--bug`/auto-detect call, step 5b).
5a. **Create the draft ticket(s) right away** (`mcp__github__issue_write`,
    `mcp__github__sub_issue_write`), before showing anything to the human — this is what
    makes `--resume` possible if the session ends before final approval
    (`docs/pilot-process.md` §3 `status:draft`, §4 "Resuming a paused pair session"):
    - Single story (`type:feature`/`type:tech`): create it, matching `type:` +
      `level:story` + `status:draft`, assigned to this session.
    - Several stories, reusing an existing Epic: create each story the same way
      (`level:story`, `status:draft`, assigned), link each as that Epic's sub-issue.
    - Several stories, new Epic: create the Epic (`level:epic` + matching `type:`, no
      `status:` label, unassigned — an Epic is never itself a draft) first, then each
      story linked as its sub-issue, `level:story` + `status:draft` + assigned.
    - `type:bug`: create it matching `type:bug` + `level:task` + `status:draft`, assigned
      to this session — never `level:story`, and never linked to an Epic
      (`docs/pilot-process.md` §2 "Three levels" — a bug is never grouped).
5b. This phase always runs paired (`docs/pilot-process.md` §4 "Interaction modes" —
    `/pilot-story` has no `--auto`): show the human which agent picked this up and why,
    along with the drafted story/stories (and epic decision, if any) — pointing at the
    real issue number(s) from 5a, not just conversation text. This is also the point
    where the human corrects a wrong `--tech`/`--bug`/auto-detect call — if they do, update the
    existing draft ticket's `type:` label and restart from step 2 with the other agent,
    rather than creating a second ticket. If the agent instead now decides the idea is
    out of scope, close the draft ticket(s) instead of leaving them open — nothing
    proceeds to `status:backlog`. Otherwise, wait for the human's response and feed it
    back to the agent, writing each further round's changes into the draft ticket(s)
    (`issue_write`) as they're agreed — repeat until they approve. Requires a human live
    in this session; this phase is never run from a scheduled sweep. Once approved,
    continue to step 5c.
5c. **Final consolidation pass** (`docs/pilot-process.md` §4 "Interaction modes"): before
    finalizing, have the agent re-read each draft ticket's body as a whole — not just the
    latest round's delta — and fix anything that no longer holds together across rounds
    (an out-of-scope note from an early round that no longer matches an acceptance
    criterion added later, a gap neither round's writer noticed).
6. Finalize (`mcp__github__issue_write`): flip each `type:feature`/`type:tech` story from
   `status:draft` to `status:backlog`, unassigned. For a `type:bug` ticket, flip it from
   `status:draft` straight to `status:spec-ready` instead, unassigned — never
   `status:backlog`, it skips phase 2 entirely (`docs/pilot-process.md` §2 "Three levels").
7. Report the issue number(s)/URL(s) back to the human.

Do not decide whether a story needs splitting, record any dependency, or start phase 2
as part of this skill — that's `/pilot-scope`'s job, run separately once per
`type:feature`/`type:tech` story (never applicable to a `type:bug` ticket, which is
already spec-ready and skips phase 2 outright).
