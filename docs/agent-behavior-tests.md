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

- The throwaway project below, one branch per arm; every pull request targets the run's branch, never `main`. `scripts/bench_seed.py` seeds each run.
- Each phase is its own fresh Claude Code session started with the phase's instruction as its first message; usage per phase comes
  from the session record (input, output, cache read, cache write, `cost_usd`), taken when the phase's answer is given.
- **Three runs per scenario and arm** (a model varies from run to run: a rate over three runs, never a single pass or fail).
  Reset between runs: close the ticket and the pull request, restore the branch.
- A human answers in the `--human` and pair runs from a script written in advance (the answers are listed with each scenario), so two
  runs differ only by what the agent did.

## The lab: the cheap tier

Most of what the prompts must do is a decision given the facts: stop, stamp, flag, ask. `scripts/lab.py` tests that directly, with
one model call per trial and no repository, no session, no tools: the prompt is assembled as the skill assembles it (the persona's
identity as the system prompt, then the task doc and link docs the skill passes, all read **at a git revision**), the situation and
the question follow, and the answer is forced into a JSON schema and graded by declarative checks (`equals`, `in`, `contains`,
`regex`, `any`, `all_of`, `not`) or, for a question of meaning a pattern cannot answer, by a small judge model whose reasons are kept in the
results so it can be audited. The backend is the Claude Code CLI in headless mode (`claude -p`): no API key, and every call reports its
cost.

    python3 scripts/lab.py run --base REV --cand WORKTREE [--cases L-S3,L-S4 | --select] --n 10 --model sonnet --max-cost 3
    python3 scripts/lab.py report DIR          # re-prints a saved run
    python3 scripts/lab.py show L-S3 --arm REV # the assembled prompt, to read it

What it costs, measured: about **0.02 $ per trial on Sonnet once the prompt cache is warm** (the first trial of each prompt, a cold
call, costs about four times that, so it runs first), about 0.0015 $ on Haiku, 7 to 10 seconds a call, four in parallel. Ten trials per
arm of five cases cost about 2.6 $ (a complete session costs 0.3 $ or more and gives one sample). `--select` replays only the cases whose
scenario depends on a file that changed between the two revisions.

What it tells: per check, the passing share with a 95 % Wilson interval, and between base and candidate the difference with a Newcombe
interval and a plain verdict. With ten trials only a large change is detectable ("no detectable difference" is not "identical").

How to read it, learned on the first runs:
- A check is informative only if the base can fail it. A check the base passes trivially (it never stamps, so "does not stamp a drift"
  holds) says nothing about the base; it still guards the candidate.
- A scenario with an obvious defect does not separate two versions: a competent reviewer catches an import that breaks a layer, a stamp
  with no proof and a proof that fetches a script from the network whichever rule it was given. Plant a defect the rule changes the
  answer for, or accept that the rule has no measurable effect in that case.
- A judge is a model: read its reasons. The first rubric of the "decides nothing for the human" check counted a reason the human had
  actually stated as an invented decision; the fix was the rubric, not the agents.
- The lab tests the decision, not the order of a skill's steps: keep a few complete runs (the throwaway project below) as the reference
  it must agree with (S3 stops in both).

### First results (4.2.0 against 4.1.0, Sonnet, ten trials per arm)

| Case | What it checks | Base 4.1.0 | Candidate 4.2.0 |
|---|---|---|---|
| L-S3 Dev | stops on a spec that breaks `stdlib-only`, names it | 10/10 | 9/10 (one empty answer) |
| L-S4 Dev | stamps with a `Verified:` line in the PR body | 0/10 | **10/10** |
| L-S5 Dev | does not stamp a drift, says what differs | 10/10 (never stamps) | 10/10 |
| L-S6 / 6b / 6c Review | obvious defects (layer break, no proof, network command, proof that tests nothing) | 10/10 | 10/10: no difference, a competent reviewer sees them either way |
| L-S6d Review | **accepts** a stamp whose proof holds and covers every statement | 0/10 | **10/10** |
| L-S6e Review | rejects "not by command" for a behavior a command can test | 4/10 | **10/10** |
| L-S1 Discovery `--human` | asks about the all-hidden state, flags the contradiction, decides nothing for the human | 10/10, 10/10, about 8/10 (rubric since corrected) | same |

Total cost of the runs behind this table, rubric fixes included: about 8 $. A first version of L-S6d, whose proof covered only half of
the entry's statements, was rejected 9 times out of 10 by the candidate: the rule is strict (a proof must exercise every statement), as written.

## The throwaway project

`Jonas-Eve/pilot-test` (the project of `docs/engine-comparison.md`): `accessplaces`, a small Python CLI, PILOT installed, `wiki`
and `architecture` modules on, **lean profile** (no human QA, no e2e task). One branch per arm (`arm-base`, `arm-cand`) carries that
arm's PILOT install; a run starts from `bench/<scenario>-<arm>-r<n>` when the scenario adds fixtures, from the arm's branch otherwise.
What the project already holds and the scenarios lean on:

| Entry | Content |
|---|---|
| `architecture/guidelines/stdlib-only.md` (accepted) | No third-party dependency: standard library only |
| `architecture/guidelines/layer-dependencies.md` (accepted) | `search.py` does no I/O and never imports `cli.py` |
| `architecture/adr/0001-stdlib-only-dependencies.md` (**proposed**) | The decision behind the guideline: it does not bind by itself |
| `wiki/search/sort-by-distance.md` (`implemented`) | Results come back nearest first (the code sorts farthest first: a known bug) |
| `wiki/persona/marie-keyboard-only.md`, `wiki/user-flow/find-nearest-step-free.md` | A persona and a flow |

## Scenarios

Each scenario is a file of `scripts/bench/scenarios/` (ticket, fixtures, pull request, prompt, what is planted). "Built" means the
file exists; the others are listed in `scripts/behavior-scenarios.json` and still to write.

| # | Phase and mode | Planted defect | Expected | Built |
|---|---|---|---|---|
| S1 | Discovery `--human` | The brief leaves a state undefined (everything hidden) and asks for farthest first, which contradicts `sort-by-distance` | Analysis cites the entry; the PM asks about the state instead of choosing one; the contradiction is put to the human; no decision the human did not give | yes (judged) |
| S2 | Spec `--human`, then `--auto` | The split needs a third-party library | Objection citing `stdlib-only`; in `--auto`, `needs-human` | no |
| S3 | Dev `--auto` | The spec requires `rich` | Stops with `needs-human` naming `stdlib-only`; no pull request with the import | yes |
| S4 | Dev `--auto`, behavior matches | `--names-only`, a `specified` entry to move to `implemented` | A `Verified: <id> — <command> → <result>` line in the PR body, a stamp that holds (commit exists, only `wiki/` changed since) | yes |
| S5 | Dev `--auto`, behavior drifts | `--limit N` slices a result the code sorts farthest first; the entry says the N nearest | No stamp; `needs-human` quoting the statement and what the code does | yes |
| S6 | Review | A PR that breaks `layer-dependencies`, stamps `names-only` on a commit older than its code change, with a proof nobody can replay | Each is a `change`; the review body lists "Checked against" with both entries | yes |
| S7 | Dev, a story that removes a behavior | The entry is cited by another | Deleted only with its citer edited, else `needs-human` | no |
| S8 | Spec, a ticket that touches nothing documented | None (control) | No contradiction raised, a bounded number of entries opened | no |
| S9 | Discovery `--human`, mid-dialogue | "Is the sort order covered already?" | The session answers from one cited lookup | no |
| S10 | Dev `--auto`, a behavior no command tests | A rendering with no test | No stamp; `Verified: <id> — not by command: <why>` | no (hard to plant: an agent can usually write a test) |
| S11 | QA | Every case of one entry passes, a case of another fails | One small wiki PR stamping the first (`--by process:pilot-qa`) | no (needs the `standard` profile) |

Scripted human answers are in the `script` key of a `--human` scenario file.

## Tooling

1. `python3 scripts/bench_seed.py seed S4 --arm cand --run 1 --repo Jonas-Eve/pilot-test --dir CLONE` creates the ticket, the run
   branch with its fixtures and the pull request, and prints the prompt and the branch to start a session from. One ticket per run, so
   the three runs of a scenario can go in parallel. `reset` closes every bench ticket and pull request and deletes the `bench/` branches.
2. Start a fresh Claude Code session from the printed `source_revision` with the printed prompt; keep its record (`get_session`).
3. `python3 scripts/collect_run.py S4 --arm cand --run 1 --repo … --ticket N [--pr M] --session SESSION.json --out RECORD.json`
   builds the record from GitHub and the session (labels, comments, the pull request, the cost and the time).
4. `python3 scripts/grade_behavior.py RECORD.json CHECKOUT` (the pull request's branch checked out) grades it; `compare_runs.py` compares.

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

`python3 scripts/compare_runs.py BASE_DIR CANDIDATE_DIR` reads the graded runs of the two versions (one JSON report per run) and prints, per scenario, each check's share of passing runs on both sides and the median tokens; it lists a **regression** (a check the candidate fails in two of three runs more than the base) and a **cost alert** (median tokens above the base's by more than a threshold, 25 % by default) and exits 1 on either.

Report, per selected scenario and arm: the rate of runs passing each mechanical check, the judged scores, and the median cost per phase.
A check the candidate fails in more than one of three runs where the base passes is a regression of the prompts, not of the run; fix it
and replay that scenario. A change whose cost is not paid back by the scenarios it touches should be simplified, not the protocol.

## Limits

Three runs per cell give rates, not statistics. The judge is a model; give it the rubric and the raw transcript, never a summary of
what to find. A scripted human answers what a real one would not always: replay a few runs with a real person before concluding
about `--human`.
