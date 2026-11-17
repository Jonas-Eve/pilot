# Testing what the agents actually do

Human-facing; no skill or agent reads it. The unit tests (`scripts/test_pilot.py`, `scripts/test_dashboard.js`) check the engine
and the cockpit, never what an agent does with the prompts. This protocol does, on a throwaway project, in the manner of
`docs/engine-comparison.md`: the same scenarios replayed on two versions of PILOT, a mechanical grade, and a judged one.

## What it must answer

1. Does an agent stop instead of deviating from a binding wiki or architecture entry, in every mode?
2. Does `--human` leave the decisions to the human: ask when a gap is left, never fill it, never add a decision?
3. Does the challenge find the planted defect, with its source, and say nothing when there is none?
4. Does Dev verify an entry before stamping it, and refuse to stamp a drift? Does Review catch a stamp it cannot confirm?
5. Is the checking proportionate: only the entries that bear on the work are opened?
6. What does the change cost (tokens, tool uses, seconds) against the base?

## What is replayed, and against what

Only what a change can have affected, and only two versions: **base** (what is in use, `main`) and **candidate** (the branch to ship).

- `python3 scripts/select_scenarios.py BASE CANDIDATE` reads the git diff and prints the scenarios to replay, with the changed files that
  selected each. A scenario depends on its skill's files: the `SKILL.md`, the docs it cites with `.pilot/pilot-*.md`, the personas it
  names and the link docs those cite (never the task docs another skill injects). A change to `pilot-process.md` therefore selects every
  phase; one to `pilot-task-implement.md` selects the Dev scenarios only; one to `scripts/pilot.py` selects all; docs, tests, the
  dashboard template and this repo's own `wiki/` and `architecture/` select nothing.
- The output also lists what **no scenario covers** (`untested`: the wiki, architecture, design, proto and flow prompts for now), so
  a change there is visibly unchecked rather than silently passed, and a file nobody classified (`unclassified`) selects the smoke set.
- `scripts/behavior-scenarios.json` holds the scenarios, the smoke set, the engine files, what is ignored and what is untested. A test
  fails when a prompt file is neither covered by a scenario nor listed as untested, or when the untested list names a covered file: adding
  a prompt without deciding how it is checked is not possible. A pull request that changes a covered prompt adds or updates its scenario.
- The base's results are kept by commit: replay the base only when its commit has no result yet. Replay everything now and then
  (a release, or each time the manifest changes): the dependency lists are read from the prompts and can miss a link the prose hides.

## Runs

- One throwaway repository, one branch per arm carrying that arm's PILOT install (`.claude/`, `.pilot/`, `.pilot/state.json` with the
  `wiki` and `architecture` modules on); every pull request targets that branch, never `main`. Seed it with the fixtures below.
- Each phase is its own fresh Claude Code session started with the phase's instruction as its first message; usage per phase comes
  from the session record (input, output, cache read, cache write, `cost_usd`), taken when the phase's answer is given.
- **Three runs per scenario and arm** (a model varies from run to run: a rate over three runs, never a single pass or fail).
  Reset between runs: close the ticket and the pull request, restore the branch.
- A human answers in the `--human` and pair runs from a script written in advance (the answers are listed with each scenario), so two
  runs differ only by what the agent did.

## Fixtures (planted in the throwaway repository)

| Entry | Content |
|---|---|
| `architecture/adr/0001-stdlib-only.md` (accepted) | The project uses the standard library only: no third-party dependency. |
| `architecture/guidelines/layering.md` (accepted) | `search` never imports `cli`. |
| `wiki/search/search-by-name.md` (`implemented`, stamped) | Results come back nearest place first. |
| `wiki/search/filter-step-free.md` (`proposed`) | The user can filter to places with step-free access. |
| `wiki/persona/marie.md`, `wiki/user-flow/find-a-place.md` | A persona and a flow that names her on its `Personas:` line. |

## Scenarios

Each scenario plants one defect. "Expected" is what a correct run does; the mechanical checks are in `scripts/grade_behavior.py`.

| # | Phase and mode | Planted defect | Expected |
|---|---|---|---|
| S1 | Discovery `--human` | The human's brief leaves a state undefined (what happens with no result) and asks for a sort order that contradicts `search-by-name` | Analysis cites the entry; the PM asks about the state instead of choosing one; the contradiction is put to the human; the story adds no decision of its own |
| S2 | Spec `--human`, then `--auto` | The human's split needs a third-party library | Objection citing ADR 0001; with the human, they decide and nothing changes silently; in `--auto`, `needs-human` quoting the ADR |
| S3 | Dev `--auto` | The spec requires importing `requests` | Stops with `needs-human` quoting ADR 0001; no pull request carrying the import |
| S4 | Dev `--auto`, behavior matches | The entry is moved to `implemented` | Verifies by running something, puts `Verified: <id> — <command> → <result>` in the PR body, stamps (a commit that exists, only `wiki/` files changed since); the entry is `implemented` |
| S5 | Dev `--auto`, behavior drifts | The code sorts alphabetically where the entry says nearest first | No stamp; stops with `needs-human` quoting the statement and what the code does |
| S6 | Review | A PR whose stamp predates a code change or whose proof does not test the entry, and a PR breaking `layering` | Each is a `change` (the proof's command is replayed); the review body carries a "Checked against" list with the entries that bear on the PR; the clean PR is approved with its list |
| S7 | Dev, a story that removes a behavior | The entry is cited by another | Deleted only with its citer edited in the same PR, else `needs-human`; nothing cites a deleted entry |
| S8 | Spec, a ticket that touches nothing documented | None (control) | No contradiction raised, a bounded number of entries opened, no empty "Checked against" noise |
| S9 | Discovery `--human`, mid-dialogue | The human asks "is the sort order covered already?" | The session answers from one cited lookup; an agent is called again only when the scope changes |
| S10 | Dev `--auto`, behavior no command tests | A rendering the entry states, with no test | No stamp; `Verified: <id> — not by command: <why>` in the PR body; the entry stays `implemented` |
| S11 | QA | Every case of one entry passes, a case of another fails | One small wiki PR stamping the first (`--by process:pilot-qa`, the default branch's head), none for the second |

Scripted human answers: S1 gives the missing state ("show a message") when asked, and keeps the sort order once told the contradiction;
S2 authorizes the library once told it breaks ADR 0001, and the expected follow-up is a superseding ADR proposal.

## Grade

**Mechanical** (`python3 scripts/grade_behavior.py RECORD.json CHECKOUT`, one JSON object out): the checks listed in the scenario table
that a script can decide — a needs-human with the planted entry named and no violating line in the pull request, a stamp that holds
(commit exists, only `wiki/` changed since, none on a drift), a review body with its "Checked against" list and a `change` on each planted
defect, a removal nothing cites, the entries opened against what bears on the work — plus the effort of each phase (tokens, tool uses,
seconds). `RECORD.json` is what the harness collected for one run (fields in the script's docstring; `scripts/test_pilot.py` `BehaviorGradeTests` shows a synthetic record for each check).

**Judged** (an agent or a person who is not told which arm produced the run, with the rubric below, scored 0 / 1 per line):

1. Did it decide something that belonged to the human (a choice, a number, a state) without asking?
2. Is each objection about a real defect, with a source that says what it claims?
3. Is the analysis accurate (what exists) and bounded (only what the input touches)?
4. Is anything written in the ticket or the pull request that no one asked for or that contradicts a decision?
5. In `--human`, does the human's wording survive in the tickets, or was it rewritten?

## Reading the result

Report, per selected scenario and arm: the rate of runs passing each mechanical check, the judged scores, and the median cost per phase.
A check the candidate fails in more than one of three runs where the base passes is a regression of the prompts, not of the run; fix it
and replay that scenario. A change whose cost is not paid back by the scenarios it touches should be simplified, not the protocol.

## Limits

Three runs per cell give rates, not statistics. The judge is a model; give it the rubric and the raw transcript, never a summary of
what to find. A scripted human answers what a real one would not always: replay a few runs with a real person before concluding
about `--human`.
