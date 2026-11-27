# PILOT — Process

PILOT runs **workflows**: sequences of steps where a human decides, agents execute and code checks. A workflow is data
(`.pilot/workflows/<id>.json`, `python3 .pilot/pilot.py workflow show <id> [--step N]`) run by its skill as
`.pilot/pilot-link-runner.md` says. This document holds what every workflow shares: where objects live (§1), statuses and flags
(§2), the run (§3), claim and resume (§4), isolation (§5), events (§6) and modules (§7). Nothing here describes a single
workflow: its contract (statuses it consumes, claims, produces) is `pilot.py contract <workflow>`.

## 1. Objects and where each lives

| Object | Lives in | Its status lives in | It moves by |
|---|---|---|---|
| Document: wiki entry, guideline, ADR, design-system entry, persona, user flow | a file under `wiki/`, `architecture/` | its frontmatter, stable statuses only (wiki: `proposed`, `specified`, `implemented`, `provisional`; architecture: `proposed`, `accepted`, `superseded`); in-flight ones (`rework`, recetted, in gap) are derived from tickets, runs and records (`pilot.py wiki status`) | the docs PR its workflow ends with, opened and merged by the script |
| Ticket: epic, story, task | a GitHub issue | a `status:` label | `pilot.py` only |
| Run | the ticket it works, else a `run` issue the script creates and closes | one JSON comment (`<!-- pilot:run -->`) | `pilot.py run` only |
| Prototype | the dashboard's `protos` documents (one HTML) | the closing comment of its run (accepted or rejected) | `pilot.py proto-pack` |
| Recette record | the closing comment of a Recette run, never edited | derived marks (`recetted`, `gap`) | `pilot.py` reads it |

Nobody needs GitHub's UI: `pilot.py` is the only reader and writer of tickets and runs, behind one tracker adapter (the
`gh` calls live in one module), and the cockpit shows them (§6). A docs-only PR needs no CI (`paths-ignore`).

## 2. Labels

- `run:<workflow>` marks a run issue. `level:epic|story|task`, set at creation, never recomputed; a story's tasks and an epic's stories are native GitHub sub-issues. Depth stops at three levels.
- `type:feature|tech`: who validates and reviews, and who runs the Recette (human F for feature, human T for tech). Never inherited.
- `status:`, one at a time, derived by script from the children, the entries and the merge — never set by hand except the two human closings (`pilot.py ticket close-forming`):

| Level | Statuses, in order |
|---|---|
| epic | `forming` → `to-plan` → `planning` → `planned` → `done` (or `wont-do`) |
| story | `forming` → `to-plan` → `planning` → `ready` (unsplit) or `planned` (split) → `building` → `reviewing` → `merged` → `done` (or `wont-do`) |
| task | `ready` → `building` → `reviewing` → `merged` → `done` |

  `forming`: still takes entries until a human closes it. `merged`: awaits the Recette (a split story is `merged` when all its tasks are). `done`: the Recette passed. `wont-do`: a human dropped an epic or story from `forming` or `to-plan`; a task has none.
- Flags, beside the status: `needs-human` (a blocking question, always with a comment saying why and what is needed; a human removes it), `on-hold` (paused for something larger), `can-resume` (a human's signal that an interrupted run is safe to continue), `express`, `fix` (a correction ticket made by a Recette), `gap` (depends on a ticket whose Recette is in gap).
- `priority:P0|P1|P2` orders the pool; never on an epic.
- A ticket carrying `needs-human` or `on-hold`, or with an open "Depends on #N" (one per line, one number), is in no pool; the gate is `pilot.py`'s, never an agent's.

## 3. The run

A step has a kind: human start, human gate, optional human, agent, validator, judge, code check, wait, end. The workflow's JSON says which, with typed
inputs and outputs, the agent and its task doc, the check or judge id and where a failure goes.

- **Agents.** The lead (the persona that understands the need) audits, then writes. A validator is another persona that receives the deliverable alone, never the discussion. A judge has no persona: closed yes/no questions, citation required, two passes that must agree. Which code check or judge exists is data: `pilot.py check <id>`, `pilot.py judge <id>`.
- **Code before judgment.** Whatever a check can decide is a check; a judge only asks what code cannot.
- **Loops.** A loop through code, a validator or a judge runs twice at most, then escalates (a gate opens with the failures; without a gate, a question goes to the human concerned). A loop through a human has no limit.
- **Challenge.** The script opens it only when the auditor's delta is not empty. It is a loop between the human and the auditor; each turn receives the delta and the messages since the auditor's last turn.
- **Blocking and assumptions.** A choice no decision or guideline covers, whose options differ in effect or cost, is a question to the human (`needs-human`). Every other choice becomes a recorded assumption with its default, shown at the gate.
- **Rework.** A workflow that finds a criterion impossible or an entry wrong does not edit it: it opens a need run carrying the question card; the entry is `rework` while that run is open.
- **Provisional.** An express writes provisional documents; `pilot.py` creates the catch-up item with its deadline.
- **Hierarchy.** The need workflow groups entries into stories and stories into an epic; the plan workflow splits a story into tasks only when the code checks say it does not fit. Documents and tickets are never copied into each other: a story points to its entries.

## 4. Claim, resume, pool

- A workflow that works a ticket **claims** it first: `pilot.py claim <workflow> <issue> --mode …` sets the assignee and the in-progress status in one write, then re-reads; a different assignee afterwards means another run won, so stand down. Optimistic, not a lock.
- `pilot.py pool <workflow>` lists claimable tickets: fresh (the workflow's pre-claim status, unassigned) and resumable (in-progress with `can-resume`); highest priority, then blocks, then oldest.
- **Resume.** `pilot.py run resume <issue>` reads the run comment and continues at the recorded step, with its loop counters and assumptions. An orphaned claim (assigned, in progress, no `needs-human`) resumes only by an explicit `--resume` or `can-resume`, because only a human can tell it is dead. A cleared `needs-human` resumes with the question's answer. A run waiting on a condition (a wait step) is paused: `run resume` re-evaluates it and refuses with the exact reason. A workflow with no ticket creates its `run` issue assigned to the current user.

## 5. Isolation

Every agent call is its own context. It receives only the typed documents its step lists (and, in a challenge, the thread since its last turn); no agent remembers an earlier step. Claim, labels, statuses, checks and records are script calls, never agent reasoning.

## 6. Events and the cockpit

Every `pilot.py` write returns an `event`, step transitions of a run included, which the skill pushes to the project's dashboard (`.pilot/pilot-link-dashboard.md`); best effort, never blocking. A run ends with a snapshot. What changes outside a skill (a label edited by hand, the merge workflow, a CI result) shows at the next snapshot.

## 7. Optional modules

`.pilot/state.json` turns a module on (`pilot.py module list|enable|disable`): `wiki` (what the product does), `architecture` (how it is built and why), `dashboard`, `design`, `proto`. A module that is off changes nothing; every step that names it is skipped. Every agent reads `wiki` and `architecture` the same way (`.pilot/pilot-link-knowledge.md`). **When the wiki and the code disagree, the wiki is right**, and a divergence is a human's call.
