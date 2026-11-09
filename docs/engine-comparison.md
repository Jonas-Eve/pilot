# Comparing PILOT's ways of running a phase

Human-facing; no skill or agent reads it. How the engine (`scripts/pilot.py`) was compared with the protocol that
preceded it (an agent doing the mechanics itself from the skills' prose), and with an engine that left GitHub to the
agent's own tools, so the comparison can be replayed on a later version.

## Arms
- **pre-engine**: the skills and docs of `597711f^` (before `pilot.py`).
- **gh engine**: `pilot.py` reaching GitHub with `gh api` itself (what `main` shipped, plus the pool resolving its pick).
- **tools engine**: `pilot.py` asking the agent for what it lacks, to be fetched with the GitHub MCP tools (a short-lived
  alternative, not kept).

## Protocol
One tiny ticket per run, the same each time: a `type:tech` need, "add a `--version` flag to the CLI", created from its raw
description by `/pilot-spec --tech`, then `/pilot-dev`, then `/pilot-review`, on the lean profile. The run stops at
`status:approved`; the human merges.
- One branch of pilot-test per arm carries that arm's PILOT install (`.claude/`, `.pilot/`, the state with
  `workflow.profile: lean`); every pull request targets that branch, never `main`. The `workflow:lean` and
  `workflow:standard` labels must exist (the gh engine's `doctor` requires them).
- Each phase is its own fresh Claude Code session created with the phase's instruction as its first message (a session does
  not act on a message another session sends it), so the real personas run and a session's usage is exactly one phase's.
- Usage per phase comes from the session record (`external_metadata.usage`: input, output, cache read, cache write,
  `cost_usd`), taken when the phase's answer is given: later turns (CI check, notifications on the pull request) are not
  the phase.
- Grading: `python3 scripts/grade_run.py RECORD.json CHECKOUT` on the pull request's branch. Orchestration (one status
  label, statuses in chain order, no flag left, `Closes #N`, a review submitted, ticket `approved` with the PR open),
  respect of the project's docs (stdlib only, layers, tests offline, an e2e test per story, conventional commits and title,
  PR template, docs updated), mechanical quality (the flag works, existing behaviour kept, tests pass and one covers the
  change, a small diff, nothing outside the scope). What needs judgment (Spec, code, review relevance) is read by a person
  or an agent not told which arm produced it. GitHub refuses to approve one's own PR: the review lands as a comment and the
  ticket's label carries the verdict.
- Reset between runs: close the ticket and the pull request.

## Result, run 1 (2026-11-09, one run per arm)
| | pre-engine | gh engine | tools engine |
|---|---|---|---|
| Spec | 1.08 $ | 0.95 $ | 1.32 $ |
| Dev | ~0.77 $ | ~0.60 $ | 0.66 $ |
| Review | 0.59 $ | 0.53 $ | 0.62 $ |
| Total | ~2.44 $ | ~2.09 $ | 2.60 $ |
| Cache read | 6.26 M | 5.64 M | 8.41 M |
| Seconds, all phases | ~360 | ~357 | ~352 |
| Grid: orchestration / docs / quality | 7/7, 8/8, 6/6 | 7/7, 8/8, 6/6 | 7/7, 7/8, 6/6 |

The tools engine's missed point was the e2e test per story (it followed the lean profile, which has no e2e task, against
the project's guideline). Static context of a phase (skill + process doc): 87 kB pre-engine, 37 kB with an engine.
A first measurement of choosing and claiming a ticket (3 runs per arm): pre-engine 118 k tokens / 30 s, tools engine
109 k tokens / 48 s; the gh engine does that in one script call.

Limits: one run per arm (differences of a few percent are noise), a Dev figure of the pre-engine and gh arms estimated by
removing the CI-check turn (~0.03 $), the `gh` use allowed explicitly in the gh arm's prompts.
