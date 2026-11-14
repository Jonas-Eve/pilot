---
name: pilot-discovery
description: "Phase 1 of PILOT: turns a raw type:feature idea into formalized GitHub stories. The PM frames the idea with the human into a validated brief and drafts the story; the architect validates it (anticipating architecture) and debates the PM on objection. Produces level:story tickets (plus a type:tech enabler when genuinely needed), under an epic when it does not fit one story, created as status:draft and refined with the human. Never splits into tasks or writes a spec (that is /pilot-spec). Always pair, never --auto. --from-proto <n> starts from an accepted prototype, --resume <issue> continues a draft, --with, --multi. A purely technical need or any bug goes to /pilot-spec --tech/--bug instead. Use to start a new product idea."
argument-hint: "<raw idea in free text> | --from-proto <accepted prototype number> [--with <persona>[,...]] [--multi [N]] | --resume <issue number>"
disable-model-invocation: true
---

# PILOT — Phase 1: Discovery

Read `.pilot/pilot-process.md` before running this if you haven't already — it's the
source of truth for labels, states, and the claim protocol; this skill only covers the
mechanics of running Discovery. Read `.pilot/pilot-link-ticket-tree.md` (where each ticket type originates, how epics, stories and tasks are built) and `.pilot/pilot-link-agent-dialogue.md` too — it covers
the PM/architect turn-taking mechanic this skill relies on whenever the architect objects. The
roster (`.pilot/pilot-link-roster.md` "Roster"): the PM leads, the architect validates, the
designer is summonable.

This phase is `type:feature` only. A standalone technical need with no product framing
(infra, CI, a migration, nothing a PM would have an opinion on) or a bug report never
comes through Discovery at all — point at `/pilot-spec --tech`/`--bug` instead (its own
no-ticket entry, `pilot-spec/SKILL.md`).

## Steps

1. Determine the input:
   - `--resume <issue>`: must be `status:draft`, assigned, **no** `needs-human`/`on-hold`
     — a draft left mid-pair (`.pilot/pilot-process.md` §4 "Resuming an orphaned
     claim"). Read the ticket and thread (`mcp__github__issue_read` `get_comments`) to
     reconstruct what's drafted, claim it (overwrite assignee), skip to step 4 with that
     state (call the agents in step 3 again first if revising the draft, passing the
     reconstructed context instead of a blank idea). A draft whose body carries `Prototype : #<n>` continues as
     `--from-proto <n>` (step 7 still updates and closes that prototype). If it doesn't match, report and stop.
   - `--from-proto <n>`: `python3 .pilot/pilot.py proto <n> from-proto` — it refuses anything but an
     **accepted** prototype (`reason: not-accepted`): relay it and say to accept it first
     (`/pilot-proto <n> --accept`), then stop. Otherwise read the ticket (its body is the validated brief)
     and, with `ArtifactData`, `protos/p<n>` and the mockup parts `protoHtml/<n>-<k>` joined; step 2a's raw
     idea is that brief and mockup. Continue with steps 2-4.
   - A raw idea (the argument, or ask if none given): continue with steps 2-4. Don't
     analyze it yourself — framing it is the PM's job in step 2a. If it reads as a
     standalone technical need or a bug report instead of a product idea, say so and
     point at `/pilot-spec --tech`/`--bug` rather than proceeding.
2. Fetch open `level:epic` issues (always `type:feature`, title + body only,
   `mcp__github__list_issues`/`search_issues`) as candidates the agents might reuse —
   cheap, deterministic bookkeeping, not the agents' job to search for itself.
2a. **Frame the idea with the human first** (with `--from-proto`, the PM starts from the prototype's brief and
    mockup and puts to the human only what the prototype did not settle — pass both into the round) — before the architect is called and before any
    ticket exists. The PM talks with the human alone, round by round
    (`.pilot/pilot-task-frame-idea.md`): call `Agent` for `pilot-pm` with it, passing the raw
    idea, step 2's Epic list and the framing conversation so far, the human's answers
    included — nothing else from this conversation. Each round, show the human the PM's
    challenges and restated brief as a natural conversation — questions only where useful, no
    set number or format (through whatever question tool you have, a provisional default as
    the recommended option, when one helps); feed the human's replies back and call the PM
    again. Stop when the PM says the brief is ready and the human has confirmed it (or says to
    go with the provisional defaults), or when the idea turns out to be out of scope or not a
    product idea (`/pilot-spec --tech`/`--bug`): report and create nothing. Only then does
    step 3's PM-led, architect-validated discussion start, from the validated brief. No ticket exists during
    this stage, so `--resume` has nothing to pick up: an interrupted framing is simply run
    again. Skipped with `--resume`.
3. The PM leads: call `Agent` for `pilot-pm` with `.pilot/pilot-task-write-story.md`, the
   human-validated brief (and the raw idea it came from), the candidate Epic list, and any
   `--with` persona's turns so far — nothing else from this conversation's history
   (`.pilot/pilot-process.md` §5). Once the PM's draft is ready, the architect validates it
   (`.pilot/pilot-link-roster.md` "Roster"): call `Agent` for `pilot-architect` with
   `.pilot/pilot-task-anticipate-architecture.md` and the draft only, not the PM's
   discussion (with the `architecture` module on, also `.pilot/pilot-link-knowledge.md` and `.pilot/pilot-link-architecture.md` in full: it checks the
   story against the guidelines and decisions that bear on it). An objection brings the architect into the debate with the PM and the human
   (`.pilot/pilot-link-agent-dialogue.md` turn-taking), then back on the revised draft
   alone. "The dialogue" below means this discussion, anyone `--with`/summoned included — read `.pilot/pilot-task-advise.md` and pass it into such a
   persona's call (the PM, architect and designer; the architect/PM keep their own duty docs above for
   their lead and validator turns). A
   question that needs the human — a constraint that contradicts something they decided, a
   choice that changes the story's shape — is put to them now, before step 4 creates anything,
   the same way step 2a does, and its answer fed back into the dialogue. Continue until they converge (`.pilot/pilot-link-agent-dialogue.md`)
   on: out of scope (per this project's vision (the wiki's `Vision` entry, else its functional-scope doc), if it has one — stop, report,
   create nothing); a single story (with or without a `type:tech` companion story for a
   technical enabler the PM and architect agree the same effort needs); or several stories
   plus an existing Epic to reuse or a new Epic to create.
3a. **With `--multi <N>`**: run N independent instances of step 3's own dialogue instead
    of one, all starting from the same validated brief (step 2a runs once, not N times),
    converging on a single proposal with no fixed round cap
    (`.pilot/pilot-link-agent-dialogue.md`) before continuing to step 4. A genuinely
    irreconcilable disagreement surfaces to the human right there in this same pair
    session, differing proposals quoted verbatim (never a silent pick).
4. **Create the draft ticket(s)** (`mcp__github__issue_write`,
   `mcp__github__sub_issue_write`) once the dialogue has converged, before showing the
   drafts to the human — this is what makes `--resume` possible if the session ends before final approval
   (`.pilot/pilot-process.md` §3 `status:draft`, §4 "Resuming an orphaned claim"):
   - Single story: create it, `type:feature` + `level:story` + `status:draft` + the
     dialogue's initial `priority:P0/P1/P2` (`.pilot/pilot-process.md` §3), assigned to
     this session.
   - Several stories, reusing an existing Epic: create each story the same way
     (its own `type:` — `type:feature` or `type:tech`, `level:story`, `status:draft`, its
     own `priority:`, assigned), link each as that Epic's sub-issue.
   - Several stories, new Epic: create the Epic (`level:epic` + `type:feature`, no
     `status:` label, unassigned — an Epic is never itself a draft, and never carries a
     `priority:`) first, then each story linked as its sub-issue, its own `type:` +
     `level:story` + `status:draft` + its own `priority:` + assigned.
   Under `--from-proto`, each story's body also carries `Prototype : #<n>` and, when `dashboardUrl` is set,
   `Maquette : <dashboardUrl>#proto/<n> (dashboard › Prototypes › #<n>)`.
   Once every ticket is created and linked (the Epic included), their dashboard events come from
   one call: `python3 .pilot/pilot.py event <n> <n>... --action created --phase discovery`
   (best-effort, step 7a).
5. This phase always runs paired (`.pilot/pilot-process.md` §4 "Interaction modes" —
   `/pilot-discovery` has no `--auto`): show the human the drafted story/stories (and epic
   decision, if any) and the architecture already anticipated — pointing at the real
   issue number(s) from step 4, not just conversation text. Put the PM's remaining open
   questions and challenges (`.pilot/pilot-task-write-story.md`) to the human too, the way
   step 2a does, and feed the answers back into the dialogue; an
   answer that opens new questions gets another round. A draft isn't approved while a
   question that changes its acceptance criteria is still open, unless the human says to
   go with the provisional defaults. For each `type:feature` draft
   involving user-facing UI — except under `--from-proto`, where the prototype is the mockup — also ask once whether the human has an existing mockup,
   wants to sketch one live (e.g. the `design` skill, if available), or is fine with the
   PM's own prose description. No tool here can upload an image to a GitHub comment the
   way the web UI's drag-and-drop does, so either way ask the human to attach it to the
   ticket themselves as a comment — not necessarily this same round; before each round
   from here on, check the ticket's comments (`mcp__github__issue_read` `get_comments`)
   and, once something's attached, pass a link to it into the dialogue so it references it
   instead of writing a competing description. Neither offered → the PM's own prose
   description stands. If the human corrects something (a story that should be `type:tech`
   instead of `type:feature`, a split that should be one story instead of two), feed it
   back into the dialogue and repeat until they approve. If the dialogue now decides the
   idea is out of scope: set `status:wont-do` and close the draft ticket(s) instead of
   leaving a closed issue still labeled `status:draft` (`.pilot/pilot-process.md` §3
   `status:wont-do`) — nothing proceeds to `status:backlog`. Otherwise, write each round's
   changes into the draft ticket(s) (`issue_write`) as agreed — repeat until approved.
   Requires a human live; never run from a scheduled sweep. Once approved, continue to
   step 6.
6. **Final consolidation pass** (`.pilot/pilot-process.md` §4 "Interaction modes"): before
   finalizing, have the dialogue re-read each draft ticket's body as a whole — not just the
   latest round's delta — and fix anything that no longer holds together across rounds
   (an out-of-scope note from an early round that no longer matches an acceptance
   criterion added later, an architecture assumption one round made that a later round's
   split contradicts).
7. Finalize (`mcp__github__issue_write`): flip each story from `status:draft` to
   `status:backlog`, unassigned. Under `--from-proto`: `update` `protos/p<n>` with `stories` (the numbers just
   finalized), comment on the prototype ticket with them, then `python3 .pilot/pilot.py set <n> --close` (the
   label stays). If the dialogue decides the idea is out of scope, ask the human whether to reject the
   prototype; if so, `python3 .pilot/pilot.py proto <n> reject --reason "<why>"` and `update` `protos/p<n>`
   with `decision: "rejected"`, `reason` and `decidedAt`.
7a. **Dashboard** (best-effort): per `.pilot/pilot-link-dashboard.md`, push, with `ArtifactData`
   (`ToolSearch` loads it if deferred), the `events` that `python3 .pilot/pilot.py event <n>
   <n>... --action approved --phase discovery` returns for the stories just finalized — and the
   `created` ones of step 4, and `--action closed` for a draft closed as `wont-do`. Skipped
   silently when `dashboardUrl` is absent from `.pilot/state.json`, or `.pilot/pilot.py` is
   missing: Discovery never stops for the dashboard.
7b. **Wiki** (only when the `wiki` module is enabled (`.pilot/pilot-process.md` §8); else skip): per `.pilot/pilot-link-wiki.md`, for
   each finalized `type:feature` story call `Agent` for `pilot-pm` with `.pilot/pilot-task-wiki-entries.md`
   (target status `proposed`), the project's language (`pilot.py module list`), `.pilot/pilot-link-knowledge.md`, `.pilot/pilot-link-wiki.md`, the story as finalized and the
   domains it touches (the PM reads their existing entries itself). Put each
   `conflicts` question to the human and settle it first. Then apply on branch `wiki/discovery-<first story n>`:
   `add` → `python3 .pilot/pilot.py wiki add <domain>/<id>.md --title … --description … --status proposed --ticket
   <story> --body …`; `update` → edit that entry's prose below its frontmatter, then `wiki set <id> --status
   proposed --add-ticket <story> --clear-stamp` (`--description` when it changed); `deprecate` → `wiki set <id> --status deprecated --add-ticket <story>`. The script refreshes the `index.md` files. Check
   with `wiki lint`, commit (`docs(wiki): …`, indexes included), push, open one PR (`mcp__github__create_pull_request`) listing the
   entries and their status, and give the human its link to merge — never merge it here.
8. Report the issue number(s)/URL(s) back to the human, and the wiki PR if step 7b opened one.

Do not decide whether a story needs splitting into tasks, record a dependency, or write a
spec as part of this skill — that's `/pilot-spec`'s job, run separately once per story.
