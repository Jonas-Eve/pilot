---
name: story
description: "Phase 1 of PILOT (see docs/pilot-process.md): turn a raw idea into a functional user story, opened as a type:feature GitHub issue by the PM agent — or, if the idea genuinely needs several stories, into a new or reused type:epic grouping them. Always runs in pair mode — brainstorms the draft story with a human live in the session before creating anything; there's no --auto for this phase, so it's never driven by a scheduled Routine. Use when a human wants to start a new functional feature/ticket from scratch. Not for purely technical work (CI, security, deployment, migration, optimization) — that starts at /pilot:scope instead."
argument-hint: "<raw idea in free text>"
disable-model-invocation: true
---

# PILOT — Phase 1: Plan

Read `docs/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 1.

## Steps

1. Take the raw idea (the argument, or ask the human for one if none was given). Do not
   pre-analyze it yourself — phase 1's thinking belongs to the PM agent, not to this
   skill's orchestration layer.
2. Fetch open `type:epic` + `type:feature` issues (title + body only,
   `mcp__github__list_issues`/`search_issues`) as candidates the PM might reuse — cheap,
   deterministic bookkeeping, not the agent's job to search for itself.
3. Call the `Agent` tool with `subagent_type: "pilot-pm"` (if that bare name isn't found —
   this persona ships via the `pilot` plugin — retry as `"pilot:pilot-pm"`), passing the
   raw idea and the candidate Epic list — nothing else from this conversation's history —
   the subagent should get a clean, scoped context, not the running transcript
   (`docs/pilot-process.md` §5).
4. The subagent returns one of: out of scope (per this project's functional-scope doc, if
   it has one — stop and report that, create nothing); a single story; or several stories
   plus either an existing Epic number to reuse or a new Epic to create.
4a. This phase always runs paired (`docs/pilot-process.md` §4 "Interaction modes" —
    `/pilot:story` has no `--auto`): don't create anything yet. Show the human the
    drafted story/stories (and epic decision, if any) as a normal reply, wait for their
    response, and feed it back to the agent — repeat until they approve. Requires a human
    live in this session; this phase is never run from a scheduled sweep. Once approved,
    continue to step 5 as normal.
5. Apply the result (`mcp__github__issue_write`, `mcp__github__sub_issue_write`):
   - Single story: create it, `type:feature` + `status:backlog`, unassigned.
   - Several stories, reusing an existing Epic: create each story the same way, link each
     as that Epic's sub-issue.
   - Several stories, new Epic: create the Epic (`type:epic` + `type:feature`, no
     `status:` label, unassigned), then each story linked as its sub-issue.
6. Report the issue number(s)/URL(s) back to the human.

Do not decompose a story into sub-tickets, assign a priority, or start phase 2 as part of
this skill — that's `/pilot:scope`'s job, run separately once per story.
