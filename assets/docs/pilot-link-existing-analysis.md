# PILOT link — The analyze / propose / challenge cycle

Read by the `SKILL.md` of every skill that runs the cycle, and passed in full into the call of every persona of its discussion (lead, validator, summoned).
The turn-taking and the stopping rule are `.pilot/pilot-link-agent-dialogue.md`, the roster `.pilot/pilot-link-roster.md`.

## The cycle

In every mode, the work on a ticket goes: **analyze** the existing, **propose**, **challenge** the proposal, then propose again until everyone agrees.
Only who proposes depends on the mode: the human (`--human`), the agent with the human (pair), the agent alone (`--auto`).

| Role | Analyze | Propose | Challenge |
|---|---|---|---|
| Lead (the step's main persona) | yes | as the mode says | yes, the proposal wherever it comes from |
| Validator (`.pilot/pilot-link-roster.md` "Roster") | yes, against the deliverable it receives | yes: verdict, objections, amendments | no |
| Summoned (`.pilot/pilot-task-advise.md`) | only the point raised | only if asked | only the point raised |

A validator's objections are answered by the lead (accepts, rejects with arguments, or amends); nobody challenges a validator.

## The analysis

What the input touches, nothing more. Sources, whichever exist: the wiki (`pilot.py wiki search`, `describe`, `show`), the architecture module (`pilot.py arch index --active`, `search`), the code
and the project's `CLAUDE.md`. Written as:

- **What exists** — each statement followed by its source (code path, wiki entry id, ADR number);
- **Touched by this input** — what the input would change or rely on;
- **Not covered** — what was not checked or has no source.

It lives in one comment on the ticket opened by `<!-- PILOT:ANALYSIS -->`, kept up to date in place; its second line records the run's mode (`mode: pair|auto|human`), which a `--resume` without a
mode flag reads. Before a ticket exists (framing) it is held in the conversation and posted when the ticket is created. A later round or a persona joining adds only the delta its point needs, with sources,
in its own turn. When the phase finalizes, edit it down to one line: it goes stale and is never reused by the next phase.

## The challenge

- Every objection cites its source; one without a source is dropped. The challenge is objections or nothing: no score, no global "looks fine". A round with no sourced objection ends the exchange.
- It looks for holes and inconsistencies against the existing. Optimizations or improvements only when the human asks.
- In `--human` the human proposes: challenge what they stated, with the concrete consequence and an alternative. Once they confirm a choice knowing the consequence, it is decided; don't reopen it.
- In pair and `--auto` the lead challenges its own proposal: a sourced self-review. Independence comes from the validator.

## `--human`

The human states the plan and the decisions; the agents write the tickets and the specs. Never fill a gap the human left: ask. Never add a decision of your own: write what the human decided, and raise what
you would change as a challenge. A summoned persona proposes a solution only when asked; in pair it may offer one unasked.
