# PILOT link — running a workflow

Read by the skill of every workflow, named as the workflow's id (`pilot-need`, `pilot-plan`, `pilot-build`, `pilot-accept`, `pilot-report`, `pilot-express`, `pilot-functional-frame`,
`pilot-technical-frame`, `pilot-design-system`, `pilot-proto`, `pilot-persona`, `pilot-user-flow`). A skill names its workflow; this file says how any workflow runs. Never read the whole
JSON: `pilot.py` serves one step at a time.

## Start (once per run)

1. `python3 .pilot/pilot.py doctor` once per session; stop on a failure and say which.
2. A workflow that works a ticket takes the number given, else `pilot.py pool <workflow>` and its `pick`; `pilot.py resolve <workflow> <issue>` says what to do with it
   (`claim-fresh`, `resume-cleared`, `ask-resume`, `descend`, or a `stop` reason: report it; a ticket `flagged` by an open question of its run is answered with `pilot.py run answer`). `pilot.py claim <workflow> <issue> --mode …` before any work.
3. `pilot.py run start <workflow> [--issue N] [--data '{"executant":"ai"}']` — or `pilot.py run resume <issue>` for a run that stopped. Both return the step to run; a resume of parked work returns `restore`: run it (`pilot.py run restore <run>`) before the step.

## The loop

For the step returned: `pilot.py workflow show <workflow> --step <id>` if you need it again. Run it by its `kind`, then `pilot.py run advance <run> --result …`, which returns the next
step (or `waiting-human` with its `waiting` reason, or `done`). Whenever it returns `waiting-human`, and at the end of a session, `pilot.py run park <run>` before anything else. Push every `event` a `pilot.py` call returns to the cockpit (`.pilot/pilot-link-dashboard.md`).

| kind | what you do | result to advance with |
|---|---|---|
| `human-start` | ask the human for the step's `in` (or take it from the call), write what `out` says | `ok` |
| `agent` | one `Agent` call per persona of `agents`, in order: persona `pilot-<persona>`, the task doc `.pilot/pilot-task-<task>.md`, `.pilot/pilot-link-agent-contract.md`, the documents of `in`, the step's `answers` when it has some, and the line "you may ask" when the step carries `ask` — nothing else | `ok`, or `blocked` with `--question TEXT` (only a step that carries `ask`) |
| `validator` | as an agent, given the deliverable alone (never the discussion or the producer's reasoning) | `ok` if it lists no defect, else `fail` |
| `judge` | two `Agent` calls without a persona: `.pilot/pilot-task-judge.md`, the contract, the step's `questions` and the documents; then `pilot.py judge <judge> --input FILE` | `ok` if `passed`, else `fail` |
| `check` | `pilot.py check <check> --arg key=value …` (the arguments are in the check's docstring, `pilot_checks.py`); a step flagged `action` is a script: run what its `out` says with `pilot.py` (claim, ticket, `pr open|ci|merge`, labels) | `ok` if `ok`, else `fail` |
| `human-optional` | `delta-not-empty` (the audit's delta is not empty): open it, else `skip`. `blocked`: never yours to open or skip, `run advance` skips it and `blocked` opens it: show the human the QUESTION card (`run show`), then `pilot.py run answer <run> --text …` | `ok` (continue), `loop` (the human revised: back to `loop_to`) or `skip` |
| `human-gate` | show the documents of `in`, the recorded assumptions (`pilot.py run show`) and the checks and judges' reports; the human validates or sends back | `ok` or `reject:<label>` among the step's `on_reject` |
| `wait` | evaluate the condition; if false, stop (`run resume` re-evaluates it) | `ok` |
| `end` | write what `out` says; `pilot.py run end <run> --result …` | — |

An alternative (`alt_of`) is chosen by the run's `executant`; the other is skipped. A challenge is a loop: each turn gives the auditor the delta and the messages since its last turn.

## What an agent returns, and what you do with it

- **Assumptions** (`ASSUMPTION:` lines): `pilot.py run note <run> --assumption TEXT`; the gate shows them.
- **A QUESTION**: `pilot.py run advance <run> --result blocked --question TEXT` (the card: point, options with effect and cost, recommendation), then `run park`. Ask the human now when one is live: `run answer` records the answer and the step re-runs with it. Nobody answers → stop; `needs-human` signals the question, and a later session resumes once `run answer` was given. A refusal `no-ask-here`: the step cannot ask, record the choice as an assumption.
- **A defect list or a verdict**: a validator's or reviewer's defects go back to the producer (`fail`); the producer corrects or contests with arguments, and a contested defect goes to the gate (or to the human where there is none).
- Outputs are files in the working tree; a document workflow ends by one docs PR (`pilot.py pr open`, then `pr merge` once the gate has passed; a docs-only PR has no CI).

## Finish

`pilot.py run end`, a `derive` of the parent ticket where a task or story changed (`pilot.py derive <parent>`), then one snapshot push to the cockpit. Report the outcome, what is unverified, and what only a human can do.

## Project commands

A check that reads the project's results (tests, rules, e2e, build, accessibility, a prototype's render, the deployed version) takes them from the commands of `.pilot/state.json`
(`pilot.py config get commands.test`; keys `test`, `rules`, `e2e`, `build`, `a11y`, `render`, `version`). Run the command, write the JSON its check lists. A command the project has not
declared: ask the human once, then `pilot.py config set commands.<key> "<command>"`. A check never guesses a result it could not obtain: it fails with the missing command named.
