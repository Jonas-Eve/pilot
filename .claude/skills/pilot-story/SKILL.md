---
name: pilot-story
description: "Phase 1 of PILOT (see .pilot/pilot-process.md): turn a raw need into a formalized GitHub issue — a type:feature story or type:tech need (PM/architect agent, level:story, finalizing to status:backlog for /pilot-scope), or a genuine type:bug defect (architect agent, which also classifies whether it's really a bug) created directly as level:task, finalizing straight to status:spec-ready — a bug is dev-sized by definition and skips /pilot-scope entirely. Type is auto-detected, or declared upfront with --tech/--bug. A type:feature/type:tech need spanning several stories groups into a new/reused level:epic (type:bug is never grouped). Always pair mode: drafts live with a human, creating the ticket as status:draft as soon as a first draft exists and refining it in place — a wrong detection is corrected live, never silent. No --auto, never Routine-driven; --resume <issue number> picks back up a status:draft ticket left mid-pair. Only formalizes what the need is — dependencies, prerequisites, and splitting are entirely /pilot-scope's job, run separately afterward. Use whenever a human wants to start a new ticket, whatever kind of work it is."
argument-hint: "<raw need in free text> [--tech | --bug] | --resume <issue number>"
disable-model-invocation: true
---

# PILOT — Phase 1: Plan

Read `.pilot/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running phase 1.

## Steps

1. Determine the input:
   - `--resume <issue>`: must be `status:draft`, assigned, **no** `needs-human`/`on-hold`
     — a draft left mid-pair (`.pilot/pilot-process.md` §4 "Resuming an orphaned
     claim"). Read the ticket and thread (`mcp__github__issue_read` `get_comments`) to
     reconstruct what's drafted, claim it (overwrite assignee), skip to step 5b with that
     state (call the agent in step 4 again first if revising the draft, passing the
     reconstructed context instead of a blank need). If it doesn't match, report and stop.
   - A raw need (the argument, or ask if none given): continue with steps 2-5. Don't
     pre-analyze it — that's the drafting agent's job, not this skill's.
2. Decide which agent drafts it:
   - `--tech` given → `pilot-architect`, `type:tech`.
   - `--bug` given → `pilot-architect`, `type:bug`.
   - No flag → auto-detect from the need's content: a report of already-shipped behavior
     that's broken/regressed (an error, something that used to work and doesn't, output
     contradicting what's documented/agreed) reads as `type:bug` (`pilot-architect`);
     infra/CI/security/deployment/migration/optimization work with no defect implied
     reads as `type:tech` (`pilot-architect`); product-facing/user-value work reads as
     `type:feature` (`pilot-pm`). If genuinely ambiguous between any two of the three, ask
     the human rather than guessing silently.
3. Fetch open `level:epic` issues of the matching `type:` (title + body only,
   `mcp__github__list_issues`/`search_issues`) as candidates the agent might reuse —
   cheap, deterministic bookkeeping, not the agent's job to search for itself.
4. Call the `Agent` tool with the subagent chosen in step 2. Read the task doc matching
   what step 2 picked — `.pilot/pilot-task-write-story.md` (PM), `.pilot/pilot-task-formalize-tech-need.md`
   (architect, `--tech`), or `.pilot/pilot-task-formalize-bug-report.md` (architect,
   `--bug`) — and pass its content as part of the prompt, along with the raw need and the
   candidate Epic list — nothing else from this conversation's history, so the subagent
   gets a clean, scoped context, not the running transcript (`.pilot/pilot-process.md` §5).
   The persona file itself (`.claude/agents/pilot-*.md`) carries only identity now, not
   this duty's mechanics — the task doc is what tells it what to actually do.
5. The subagent returns one of: out of scope (per this project's functional-scope doc, if
   it has one, `type:feature` only — stop, report, create nothing); a single story;
   several stories plus an existing Epic to reuse or a new Epic to create; or, for a
   `--bug`/auto-detected-`type:bug` attempt, a single `type:bug` ticket ready to build, a
   verdict that it isn't actually a defect (handled like any other wrong
   `--tech`/`--bug`/auto-detect call, step 5b), or a verdict that it isn't a real,
   actionable defect at all (e.g. already fixed, not reproducible, working as intended) —
   stop, report, create nothing, same "out of scope" outcome as above (a bug never
   reaches phase 2's own `status:wont-do` checkpoint, §2 "Three levels", so this is the
   only place that judgment call gets made for one).
5a. **Create the draft ticket(s) right away** (`mcp__github__issue_write`,
    `mcp__github__sub_issue_write`), before showing anything to the human — this is what
    makes `--resume` possible if the session ends before final approval
    (`.pilot/pilot-process.md` §3 `status:draft`, §4 "Resuming an orphaned claim"):
    - Single story (`type:feature`/`type:tech`): create it, matching `type:` +
      `level:story` + `status:draft` + the agent's initial `priority:P0/P1/P2`
      (`.pilot/pilot-process.md` §3), assigned to this session.
    - Several stories, reusing an existing Epic: create each story the same way
      (`level:story`, `status:draft`, its own `priority:`, assigned), link each as that
      Epic's sub-issue.
    - Several stories, new Epic: create the Epic (`level:epic` + matching `type:`, no
      `status:` label, unassigned — an Epic is never itself a draft, and never carries a
      `priority:`) first, then each story linked as its sub-issue, `level:story` +
      `status:draft` + its own `priority:` + assigned.
    - `type:bug`: create it matching `type:bug` + `level:task` + `status:draft` + its
      `priority:`, assigned to this session — never `level:story`, and never linked to an
      Epic (`.pilot/pilot-process.md` §2 "Three levels" — a bug is never grouped).
5b. This phase always runs paired (`.pilot/pilot-process.md` §4 "Interaction modes" —
    `/pilot-story` has no `--auto`): show the human which agent picked this up and why,
    with the drafted story/stories (and epic decision, if any) — pointing at the real
    issue number(s) from 5a, not just conversation text. For each `type:feature` draft
    involving user-facing UI, also ask once whether the human has an existing mockup,
    wants to sketch one live (e.g. the `design` skill, if available), or is fine with the
    PM's own prose description. No tool here can upload an image to a GitHub comment the
    way the web UI's drag-and-drop does, so either way ask the human to attach it to the
    ticket themselves as a comment — not necessarily this same round, e.g. a live
    co-design session takes a few of its own turns first; before each round from here on,
    check the ticket's comments (`mcp__github__issue_read` `get_comments`) and, once
    something's attached, pass a link to it into the agent's prompt so it references it
    instead of writing a competing description. Neither offered → the agent's own prose
    description stands. This is also where the human corrects a wrong
    `--tech`/`--bug`/auto-detect call — if they do, update the
    draft ticket's `type:` label and restart from step 2 with the other agent, rather than
    creating a second ticket. If the agent now decides the idea is out of scope: for a
    `type:feature`/`type:tech` draft, set `status:wont-do` and close the draft ticket(s)
    instead of leaving a closed issue still labeled `status:draft`
    (`.pilot/pilot-process.md` §3 `status:wont-do`) — nothing proceeds to `status:backlog`.
    For a `type:bug` draft, never close it directly — a bug never carries `status:wont-do`
    (`.pilot/pilot-process.md` §3 `status:wont-do`): add `needs-human` with the reasoning
    instead, leave `status:draft`, and let a human close it if they agree. Otherwise, feed
    the human's response back to the agent, writing
    each round's changes into the draft ticket(s) (`issue_write`) as agreed — repeat until
    they approve. Requires a human live; never run from a scheduled sweep. Once approved,
    continue to step 5c.
5c. **Final consolidation pass** (`.pilot/pilot-process.md` §4 "Interaction modes"): before
    finalizing, have the agent re-read each draft ticket's body as a whole — not just the
    latest round's delta — and fix anything that no longer holds together across rounds
    (an out-of-scope note from an early round that no longer matches an acceptance
    criterion added later, a gap neither round's writer noticed).
6. Finalize (`mcp__github__issue_write`): flip each `type:feature`/`type:tech` story from
   `status:draft` to `status:backlog`, unassigned. For a `type:bug` ticket, flip it from
   `status:draft` straight to `status:spec-ready` instead, unassigned — never
   `status:backlog`, it skips phase 2 entirely (`.pilot/pilot-process.md` §2 "Three levels").
7. Report the issue number(s)/URL(s) back to the human.

Do not decide whether a story needs splitting, record any dependency, or start phase 2
as part of this skill — that's `/pilot-scope`'s job, run separately once per
`type:feature`/`type:tech` story (never applicable to a `type:bug` ticket, which is
already spec-ready and skips phase 2 outright).
