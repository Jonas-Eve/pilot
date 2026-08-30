---
name: pilot-story
description: "Phase 1 of PILOT (see docs/pilot-process.md): turn a raw need into a formalized GitHub issue — a functional type:feature user story (PM agent) or a type:tech technical need (architect agent), auto-detected from the need itself, or grouped into a new/reused type:epic if it genuinely spans several. Pass --tech to declare a technical need upfront instead of relying on detection. Always runs in pair mode — drafts the story/need with a human live in the session before creating anything, so a wrong detection is never silent, it's corrected live; there's no --auto for this phase, so it's never driven by a scheduled Routine. This phase only formalizes what the need is — it never decides dependencies, prerequisites, or whether it needs splitting; that's entirely /pilot-scope's job, run separately afterward. Use whenever a human wants to start a new ticket from scratch, whatever kind of work it is."
argument-hint: "<raw need in free text> [--tech]"
disable-model-invocation: true
---

# PILOT — Phase 1: Plan

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 1.

## Steps

1. Take the raw need (the argument, or ask the human for one if none was given). Do not
   pre-analyze it yourself — phase 1's thinking belongs to whichever agent ends up
   drafting it, not to this skill's orchestration layer.
2. Decide which agent drafts it:
   - `--tech` given → `pilot-architect`, `type:tech`.
   - No flag → auto-detect from the need's content: product-facing/user-value work reads
     as `type:feature` (`pilot-pm`); infra/CI/security/deployment/migration/optimization
     work with no product framing reads as `type:tech` (`pilot-architect`). If it's
     genuinely ambiguous, ask the human which it is rather than guessing silently.
3. Fetch open `type:epic` issues of the matching `type:` (title + body only,
   `mcp__github__list_issues`/`search_issues`) as candidates the agent might reuse —
   cheap, deterministic bookkeeping, not the agent's job to search for itself.
4. Call the `Agent` tool with the subagent chosen in step 2, passing the raw need and the
   candidate Epic list — nothing else from this conversation's history — the subagent
   should get a clean, scoped context, not the running transcript
   (`docs/pilot-process.md` §5).
5. The subagent returns one of: out of scope (per this project's functional-scope doc, if
   it has one, `type:feature` only — stop and report that, create nothing); a single
   story; or several stories plus either an existing Epic number to reuse or a new Epic
   to create.
5a. This phase always runs paired (`docs/pilot-process.md` §4 "Interaction modes" —
    `/pilot-story` has no `--auto`): don't create anything yet. Show the human which
    agent picked this up and why, along with the drafted story/stories (and epic
    decision, if any), as a normal reply — this is also the point where the human
    corrects a wrong `--tech`/auto-detect call, before anything exists on GitHub. Wait
    for their response and feed it back to the agent — repeat until they approve,
    restarting from step 2 with the other agent if they correct the type. Requires a
    human live in this session; this phase is never run from a scheduled sweep. Once
    approved, continue to step 6 as normal.
6. Apply the result (`mcp__github__issue_write`, `mcp__github__sub_issue_write`):
   - Single story: create it, matching `type:` + `status:backlog`, unassigned.
   - Several stories, reusing an existing Epic: create each story the same way, link
     each as that Epic's sub-issue.
   - Several stories, new Epic: create the Epic (`type:epic` + matching `type:`, no
     `status:` label, unassigned), then each story linked as its sub-issue.
7. Report the issue number(s)/URL(s) back to the human.

Do not decide whether a story needs splitting, record any dependency, or start phase 2
as part of this skill — that's `/pilot-scope`'s job, run separately once per story.
